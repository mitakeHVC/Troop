// BOPIS_Lou/frontend/js/pages/picker/order-detail-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, getAccessToken, logout } from '../../auth.js';
import { decodeJWT, redirectTo } from '../../utils.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['picker'], 'login.html')) { // Redirect to picker login if not picker
        return;
    }

    const token = getAccessToken();
    const payload = decodeJWT(token);
    let tenantId = payload ? payload.tenant_id : null;

    const urlParams = new URLSearchParams(window.location.search);
    const orderId = urlParams.get('orderId');

    // Header elements
    const pickerNameEl = document.getElementById('picker-name');
    const pickerTenantNameEl = document.getElementById('picker-tenant-name');
    const logoutButton = document.getElementById('picker-logout-button');

    // Page content elements
    const orderIdDisplayEl = document.getElementById('order-id-display');
    const customerNameDisplayEl = document.getElementById('customer-name-display'); // If available
    const pickupSlotDisplayEl = document.getElementById('pickup-slot-display');
    const orderStatusDisplayEl = document.getElementById('order-status-display');
    const orderItemsTbodyEl = document.getElementById('order-items-tbody');
    const orderActionsContainerEl = document.getElementById('order-actions-container');
    const pageErrorEl = document.getElementById('page-error-message');


    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => { e.preventDefault(); logout('login.html'); });
    }

    // Display Picker Name & Tenant Name in header
    if (pickerNameEl && payload && payload.sub) { // sub is user_id
        try {
            const userInfo = await apiRequest('/users/me', 'GET', null, true);
            pickerNameEl.textContent = userInfo.username || 'ピッカー様';
        } catch (e) { console.warn("Failed to fetch picker user info:", e); pickerNameEl.textContent = 'ピッカー様'; }
    }
    if (pickerTenantNameEl && tenantId) {
        try {
            const tenantInfo = await apiRequest(`/tenants/${tenantId}`, 'GET', null, true);
            pickerTenantNameEl.textContent = tenantInfo.name || `テナントID: ${tenantId}`;
        } catch (e) { pickerTenantNameEl.textContent = `テナントID: ${tenantId}`; console.warn("Failed to fetch tenant name for picker:", e); }
    } else if (pickerTenantNameEl) {
         pickerTenantNameEl.textContent = "テナント情報なし";
    }

    if (!orderId) {
        if(pageErrorEl) pageErrorEl.textContent = '注文IDが指定されていません。';
        else document.body.innerHTML = '<p>注文IDが指定されていません。</p>';
        return;
    }

    if (!tenantId && payload && payload.role !== 'super_admin') { // Picker must have tenant context
        if(pageErrorEl) pageErrorEl.textContent = 'エラー: テナント情報が不完全です。';
        else document.body.innerHTML = '<p>エラー: テナント情報が不完全です。</p>';
        return;
    }


    async function fetchAndRenderOrderDetail() {
        if (!orderItemsTbodyEl || !orderIdDisplayEl || !orderStatusDisplayEl || !pickupSlotDisplayEl || !orderActionsContainerEl) {
            console.error("One or more required page elements are missing for order detail.");
            if(pageErrorEl) pageErrorEl.textContent = "ページの初期化に失敗しました。";
            return;
        }

        orderItemsTbodyEl.innerHTML = '<tr><td colspan="5" class="text-center">注文詳細を読み込み中...</td></tr>';

        try {
            // API: GET /picker/orders/{order_id}
            const order = await apiRequest(`/picker/orders/${orderId}`, 'GET', null, true);

            orderIdDisplayEl.textContent = order.id;
            // Customer info might be in order.customer object if populated by API
            if(customerNameDisplayEl) customerNameDisplayEl.textContent = order.customer ? order.customer.username : 'N/A';
            // Pickup slot details might need another fetch or be part of order details
            if(pickupSlotDisplayEl) pickupSlotDisplayEl.textContent = order.pickup_slot_id ? `スロットID: ${order.pickup_slot_id}` : '未指定';
            orderStatusDisplayEl.textContent = order.status; // TODO: Localize status

            orderItemsTbodyEl.innerHTML = ''; // Clear loading row
            if (order.order_items && order.order_items.length > 0) {
                order.order_items.forEach(item => {
                    const product = item.product || {}; // Product details should be nested
                    orderItemsTbodyEl.innerHTML += `
                        <tr>
                            <td>
                                <img src="${product.image_url || 'https://via.placeholder.com/60x60.png?text=NoImg'}" alt="${product.name || '商品画像'}" style="width:60px; height:60px; object-fit:cover; border-radius:var(--radius-sm);">
                            </td>
                            <td>${product.name || 'N/A'}</td>
                            <td>${product.sku || 'N/A'}</td>
                            <td class="text-center">${item.quantity}</td>
                            <!-- Optional: Placeholder for picked quantity or notes -->
                            <!-- <td><input type="number" class="form-control form-control-sm" value="${item.quantity}" style="width:70px;"></td> -->
                        </tr>
                    `;
                });
            } else {
                orderItemsTbodyEl.innerHTML = '<tr><td colspan="4" class="text-center">この注文には商品がありません。</td></tr>';
            }

            // Update Action Buttons based on order status
            orderActionsContainerEl.innerHTML = ''; // Clear previous buttons
            if (order.status === 'ORDER_CONFIRMED') {
                orderActionsContainerEl.innerHTML = `<button class="btn btn-primary start-picking-action-btn" data-order-id="${order.id}">ピッキング開始</button>`;
            } else if (order.status === 'PROCESSING') {
                orderActionsContainerEl.innerHTML = `<button class="btn btn-success mark-ready-action-btn" data-order-id="${order.id}">ピッキング完了報告</button>`;
            } else {
                 orderActionsContainerEl.innerHTML = `<p class="text-muted">この注文ステータス (${order.status}) では操作できません。</p>`;
            }
            addOrderActionListenersOnDetailPage();

        } catch (error) {
            console.error(`Failed to load order detail for ID ${orderId}:`, error);
             if(pageErrorEl) pageErrorEl.textContent = `注文詳細の読み込みに失敗: ${error.message}`;
            else orderItemsTbodyEl.innerHTML = `<tr><td colspan="4" class="text-danger text-center">注文詳細の読み込みに失敗: ${error.message}</td></tr>`;
        }
    }

    function addOrderActionListenersOnDetailPage() {
        const startBtn = document.querySelector('.start-picking-action-btn');
        if (startBtn) {
            startBtn.addEventListener('click', async (e) => {
                const oId = e.target.dataset.orderId;
                try {
                    await apiRequest(`/picker/orders/${oId}/start-picking`, 'POST', null, true);
                    alert(`注文ID: ${oId} のピッキングを開始しました。`);
                    fetchAndRenderOrderDetail(); // Refresh detail view
                } catch (error) {
                    alert(`注文ID: ${oId} の処理開始に失敗: ${error.message}`);
                }
            });
        }

        const readyBtn = document.querySelector('.mark-ready-action-btn');
        if (readyBtn) {
            readyBtn.addEventListener('click', async (e) => {
                const oId = e.target.dataset.orderId;
                if (!confirm(`注文ID: ${oId} のピッキング完了を報告しますか？`)) return;
                try {
                    await apiRequest(`/picker/orders/${oId}/ready-for-pickup`, 'POST', { notes: "Picker completed from detail page" }, true);
                    alert(`注文ID: ${oId} を受渡準備完了として報告しました。`);
                    fetchAndRenderOrderDetail(); // Refresh detail view
                } catch (error) {
                    alert(`注文ID: ${oId} の完了報告に失敗: ${error.message}`);
                }
            });
        }
    }

    await fetchAndRenderOrderDetail(); // Initial fetch
});

// BOPIS_Lou/frontend/js/pages/picker/dashboard-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, getAccessToken, logout } from '../../auth.js';
import { decodeJWT } from '../../utils.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['picker'], 'login.html')) {
        return;
    }

    const token = getAccessToken();
    const payload = decodeJWT(token);
    let tenantId = payload ? payload.tenant_id : null;
    let pickerUserId = payload ? payload.sub : null;

    const pickerNameEl = document.getElementById('picker-name');
    const pickerTenantNameEl = document.getElementById('picker-tenant-name');
    const newOrdersTbodyEl = document.getElementById('new-orders-tbody');
    const processingOrdersTbodyEl = document.getElementById('processing-orders-tbody');
    const pendingOrdersStatEl = document.getElementById('stat-pending-orders');
    const completedTodayStatEl = document.getElementById('stat-completed-today');
    const logoutButton = document.getElementById('picker-logout-button');

    const pickerSyncButton = document.getElementById('picker-sync-button');
    const pickerOfflineIndicator = document.getElementById('picker-offline-indicator');

    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => { e.preventDefault(); logout('login.html'); });
    }
    if (pickerNameEl && pickerUserId) {
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
    } else if (pickerTenantNameEl) { pickerTenantNameEl.textContent = "テナント情報なし"; }

    if (!tenantId) {
        if(newOrdersTbodyEl) newOrdersTbodyEl.innerHTML = '<tr><td colspan="5" class="text-danger text-center">エラー: テナント情報が不完全です。</td></tr>';
        if(processingOrdersTbodyEl) processingOrdersTbodyEl.innerHTML = '<tr><td colspan="5" class="text-danger text-center">エラー: テナント情報が不完全です。</td></tr>';
        return;
    }

    async function fetchAndRenderOrders() {
        // Fetch New Orders (ORDER_CONFIRMED)
        if (newOrdersTbodyEl) {
            newOrdersTbodyEl.innerHTML = '<tr><td colspan="5" class="text-center">新規注文を読み込み中...</td></tr>';
            try {
                const newOrdersData = await apiRequest('/picker/orders?status=ORDER_CONFIRMED&size=20', 'GET', null, true);
                newOrdersTbodyEl.innerHTML = '';
                if (newOrdersData && newOrdersData.items && newOrdersData.items.length > 0) {
                    newOrdersData.items.forEach(order => {
                         const itemCount = order.order_items ? order.order_items.reduce((sum, item) => sum + item.quantity, 0) : 'N/A';
                        newOrdersTbodyEl.innerHTML += `
                            <tr style="background-color: var(--warning-light);">
                                <td><a href="order-detail.html?orderId=${order.id}">${order.id}</a></td>
                                <td>${order.pickup_slot_id || '未指定'}</td>
                                <td>${itemCount}点</td>
                                <td>${new Date(order.created_at).toLocaleTimeString('ja-JP')}</td>
                                <td>
                                    <button class="btn btn-sm btn-primary start-picking-btn" data-order-id="${order.id}">処理開始</button>
                                </td>
                            </tr>`;
                    });
                } else { newOrdersTbodyEl.innerHTML = '<tr><td colspan="5" class="text-center">新規注文はありません。</td></tr>'; }
            } catch (error) { console.error("Failed to load new orders:", error); newOrdersTbodyEl.innerHTML = '<tr><td colspan="5" class="text-danger text-center">新規注文の読み込みに失敗。</td></tr>';}
        }

        // Fetch Processing Orders (PROCESSING)
        if (processingOrdersTbodyEl) {
            processingOrdersTbodyEl.innerHTML = '<tr><td colspan="5" class="text-center">処理中注文を読み込み中...</td></tr>';
            try {
                const processingOrdersData = await apiRequest('/picker/orders?status=PROCESSING&size=20', 'GET', null, true);
                processingOrdersTbodyEl.innerHTML = '';
                if (processingOrdersData && processingOrdersData.items && processingOrdersData.items.length > 0) {
                    processingOrdersData.items.forEach(order => {
                         const itemCount = order.order_items ? order.order_items.reduce((sum, item) => sum + item.quantity, 0) : 'N/A';
                        processingOrdersTbodyEl.innerHTML += `
                            <tr>
                                <td><a href="order-detail.html?orderId=${order.id}">${order.id}</a></td>
                                <td>${order.pickup_slot_id || '未指定'}</td>
                                <td>${itemCount}点</td>
                                <td><span class="badge badge-warning">処理中</span></td>
                                <td>
                                    <a href="order-detail.html?orderId=${order.id}" class="btn btn-sm btn-outline mr-1">詳細</a>
                                    <button class="btn btn-sm btn-success mark-ready-btn" data-order-id="${order.id}">完了報告</button>
                                </td>
                            </tr>`;
                    });
                } else { processingOrdersTbodyEl.innerHTML = '<tr><td colspan="5" class="text-center">現在処理中の注文はありません。</td></tr>';}
            } catch (error) { console.error("Failed to load processing orders:", error); processingOrdersTbodyEl.innerHTML = '<tr><td colspan="5" class="text-danger text-center">処理中注文の読み込みに失敗。</td></tr>';}
        }
        addOrderActionListeners();
    }

    function addOrderActionListeners() {
        document.querySelectorAll('.start-picking-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                const orderId = e.target.dataset.orderId;
                try {
                    await apiRequest(`/picker/orders/${orderId}/start-picking`, 'POST', null, true);
                    alert(`注文ID: ${orderId} のピッキングを開始しました。`);
                    fetchAndRenderOrders();
                } catch (error) { alert(`注文ID: ${orderId} の処理開始に失敗: ${error.message}`); }
            });
        });
        document.querySelectorAll('.mark-ready-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                const orderId = e.target.dataset.orderId;
                 if (!confirm(`注文ID: ${orderId} のピッキング完了を報告しますか？`)) return;
                try {
                    await apiRequest(`/picker/orders/${orderId}/ready-for-pickup`, 'POST', { notes: "Picker completed" }, true);
                    alert(`注文ID: ${orderId} を受渡準備完了として報告しました。`);
                    fetchAndRenderOrders();
                } catch (error) { alert(`注文ID: ${orderId} の完了報告に失敗: ${error.message}`);}
            });
        });
    }

    if(pendingOrdersStatEl) pendingOrdersStatEl.textContent = "N/A";
    if(completedTodayStatEl) completedTodayStatEl.textContent = "N/A";

    if (pickerSyncButton) {
        pickerSyncButton.addEventListener('click', () => {
            alert('ピッカーデータの同期機能は現在準備中です。');
            console.log('Picker Data Sync clicked - not implemented yet.');
        });
    }

    function updateOnlineStatusPicker() {
        if (pickerOfflineIndicator) {
            if (navigator.onLine) {
                pickerOfflineIndicator.style.display = 'none';
            } else {
                pickerOfflineIndicator.style.display = 'inline-flex';
                console.warn("Picker dashboard is now offline.");
            }
        }
    }
    window.addEventListener('online', updateOnlineStatusPicker);
    window.addEventListener('offline', updateOnlineStatusPicker);
    updateOnlineStatusPicker();

    await fetchAndRenderOrders();
});

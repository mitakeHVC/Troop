// BOPIS_Lou/frontend/js/pages/picker/order-detail-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, logout, getAccessToken } from '../../auth.js'; // Assuming getAccessToken might be used for picker info
import { decodeJWT } from '../../utils.js'; // Assuming decodeJWT might be used

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['picker'], '../picker/login.html')) {
        return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const orderId = urlParams.get('id');

    // Header elements (if they exist on this page like on dashboard)
    const pickerNameDisplay = document.getElementById('picker-name-display'); // Assuming ID exists
    const pickerTenantDisplay = document.getElementById('picker-tenant-display'); // Assuming ID exists
    const logoutButton = document.getElementById('picker-logout-button'); // Assuming ID from dashboard is reused or new one

   if (logoutButton) {
       logoutButton.addEventListener('click', (e) => {
           e.preventDefault();
           logout('../picker/login.html');
       });
   }

    // Populate picker info from JWT (similar to dashboard)
    const token = getAccessToken();
    const payload = token ? decodeJWT(token) : null;
    if (pickerNameDisplay && payload) {
        pickerNameDisplay.textContent = payload.name || payload.sub || 'Picker';
    }
    if (pickerTenantDisplay && payload) {
        pickerTenantDisplay.textContent = payload.tenant_name || (payload.tenant_id ? `Tenant ID: ${payload.tenant_id}` : 'N/A');
    }


    // Main content elements
    const orderIdMainEl = document.getElementById('order-id-main');
    const orderStatusBadgeEl = document.getElementById('order-status-badge');

    // Order Info table cells
    const orderInfoIdEl = document.getElementById('order-info-id');
    const orderInfoTimestampEl = document.getElementById('order-info-timestamp');
    const orderInfoPickupSlotEl = document.getElementById('order-info-pickup-slot');
    const orderInfoTotalAmountEl = document.getElementById('order-info-total-amount');

    // Picking Info table cells/selects
    const pickingInfoStatusSelect = document.getElementById('picking-info-status-select');
    const pickingInfoStartTimeEl = document.getElementById('picking-info-start-time');
    const pickingInfoLaneEl = document.getElementById('picking-info-lane');
    const pickingInfoPriorityEl = document.getElementById('picking-info-priority');

    const pickingListTbody = document.getElementById('picking-list-tbody');
    const readyForPickupBtn = document.getElementById('ready-for-pickup-btn');

    if (!orderId) {
        document.querySelector('.container').innerHTML = '<p class="text-danger">Order ID is missing.</p>';
        return;
    }

    if (orderIdMainEl) orderIdMainEl.textContent = orderId; // Show ID early

    try {
        const orderDetails = await apiRequest(`/picker/orders/${orderId}`, 'GET', null, true);

        // Populate Order Info
        if (orderInfoIdEl) orderInfoIdEl.textContent = orderDetails.id;
        if (orderInfoTimestampEl) orderInfoTimestampEl.textContent = new Date(orderDetails.created_at).toLocaleString('ja-JP');
        if (orderInfoPickupSlotEl && orderDetails.pickup_slot) {
            const slotDate = new Date(orderDetails.pickup_slot.date).toLocaleDateString('ja-JP');
            orderInfoPickupSlotEl.innerHTML = `<strong>${slotDate} ${orderDetails.pickup_slot.start_time.substring(0,5)} - ${orderDetails.pickup_slot.end_time.substring(0,5)}</strong>`;
        }
        if (orderInfoTotalAmountEl) orderInfoTotalAmountEl.textContent = `¥${Number(orderDetails.total_amount).toLocaleString()} (税込)`;
        if (orderStatusBadgeEl) {
           orderStatusBadgeEl.textContent = orderDetails.status_display || orderDetails.status; // Assuming API provides status_display
           // TODO: Update badge class based on status
        }

        // Populate Picking Info
        if (pickingInfoStatusSelect) pickingInfoStatusSelect.value = orderDetails.picking_status || '未処理'; // API should provide picking_status
        if (pickingInfoStartTimeEl) pickingInfoStartTimeEl.textContent = orderDetails.picking_started_at ? new Date(orderDetails.picking_started_at).toLocaleString('ja-JP') : 'N/A';
        if (pickingInfoLaneEl) pickingInfoLaneEl.textContent = orderDetails.assigned_lane || 'N/A';
        if (pickingInfoPriorityEl) pickingInfoPriorityEl.innerHTML = `<span class="badge badge-${orderDetails.is_priority ? 'danger' : 'secondary'}">${orderDetails.is_priority ? '高' : '通常'}</span>`;


        // Populate Picking List
        if (pickingListTbody) {
            pickingListTbody.innerHTML = ''; // Clear static rows
            if (orderDetails.order_items && orderDetails.order_items.length > 0) {
                orderDetails.order_items.forEach(item => {
                    const row = pickingListTbody.insertRow();
                    const product = item.product || {};
                    row.innerHTML = `
                        <td><img src="${product.image_url || '../images/product_placeholder.png'}" alt="${product.name || 'N/A'}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 4px;"></td>
                        <td>
                            <h4 style="margin: 0 0 5px 0;">${product.name || 'N/A'}</h4>
                            <p style="margin: 0; font-size: 14px; color: #666;">${product.variant_info || ''}</p>
                            <p style="margin: 0; font-size: 14px; color: #666;">商品ID: ${product.sku || product.id || 'N/A'}</p>
                        </td>
                        <td>¥${Number(item.price_at_purchase).toLocaleString()}</td>
                        <td>${item.quantity}</td>
                        <td>${item.stock_location || 'N/A'}</td>
                        <td>
                            <select class="form-control item-picking-status" data-item-id="${item.id}" style="padding: 5px; height: auto;">
                                <option value="PENDING" ${item.picking_status === 'PENDING' ? 'selected' : ''}>未ピッキング</option>
                                <option value="PICKED" ${item.picking_status === 'PICKED' ? 'selected' : ''}>ピッキング済</option>
                                <option value="OUT_OF_STOCK" ${item.picking_status === 'OUT_OF_STOCK' ? 'selected' : ''}>在庫なし</option>
                            </select>
                        </td>
                    `;
                });
            } else {
                pickingListTbody.innerHTML = '<tr><td colspan="6" class="text-center">この注文に商品情報がありません。</td></tr>';
            }
        }

        // TODO: Add event listeners for item status changes, out-of-stock handling, packaging, label print, ready for pickup.
        if(readyForPickupBtn) {
           readyForPickupBtn.addEventListener('click', () => {
               // Placeholder for actual "Ready for Pickup" logic
               alert('準備完了処理 (APIコールなど) は未実装です。');
               // Example: window.location.href = `complete.html?id=${orderId}`;
           });
        }

    } catch (error) {
        console.error('Failed to load order details for picker:', error);
        document.querySelector('.container').innerHTML = `<p class="text-danger text-center">注文詳細の読み込みに失敗しました: ${error.message}</p><a href="dashboard.html" class="btn">ダッシュボードへ戻る</a>`;
    }
});

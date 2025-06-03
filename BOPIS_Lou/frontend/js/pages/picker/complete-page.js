// BOPIS_Lou/frontend/js/pages/picker/complete-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, logout, getAccessToken } from '../../auth.js';
import { decodeJWT } from '../../utils.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['picker'], '../picker/login.html')) {
        return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const orderId = urlParams.get('id');

    // Header elements
    const pickerNameDisplay = document.getElementById('picker-name-display-header'); // Ensure unique ID if header is different
    const pickerTenantDisplay = document.getElementById('picker-tenant-display-header');
    const logoutButton = document.getElementById('picker-logout-button-header');

    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('../picker/login.html');
        });
    }

    const token = getAccessToken();
    const payload = token ? decodeJWT(token) : null;
    if (pickerNameDisplay && payload) pickerNameDisplay.textContent = payload.name || payload.sub || 'Picker';
    if (pickerTenantDisplay && payload) pickerTenantDisplay.textContent = payload.tenant_name || (payload.tenant_id ? `Tenant ID: ${payload.tenant_id}` : 'N/A');

    // Main content elements
    const orderIdConfirmationMsg = document.getElementById('order-id-confirmation-message');

    // Order Summary Table 1
    const orderSummaryId = document.getElementById('order-summary-id');
    const orderSummaryPickupSlot = document.getElementById('order-summary-pickup-slot');
    const orderSummaryItemCount = document.getElementById('order-summary-item-count');
    const orderSummaryTotalAmount = document.getElementById('order-summary-total-amount');

    // Order Summary Table 2 (Processing Info)
    const orderSummaryStatus = document.getElementById('order-summary-status');
    const orderSummaryStartTime = document.getElementById('order-summary-start-time');
    const orderSummaryCompletionTime = document.getElementById('order-summary-completion-time');
    const orderSummaryProcessingTime = document.getElementById('order-summary-processing-time');

    const preparedItemsTbody = document.getElementById('prepared-items-tbody');

    // Packaging Info
    const packagingTypeEl = document.getElementById('packaging-type');
    const packagingNotesEl = document.getElementById('packaging-notes');
    const packagingAssignedLaneEl = document.getElementById('packaging-assigned-lane');

    // Label Info (example, assuming it's part of order data)
    const labelOrderId = document.getElementById('label-order-id');
    const labelPickupSlot = document.getElementById('label-pickup-slot');
    const labelLane = document.getElementById('label-lane');
    const labelItemCountDisplay = document.getElementById('label-item-count'); // New ID for item count on label
    const labelPickerName = document.getElementById('label-picker-name');


    // Handover Info
    const handoverNotesTextarea = document.getElementById('handover-note');
    const handoverLocationSelect = document.getElementById('handover-location');


    if (!orderId) {
        document.querySelector('.container').innerHTML = '<p class="text-danger">Order ID is missing.</p>';
        return;
    }

    if (orderIdConfirmationMsg) orderIdConfirmationMsg.textContent = `注文 ${orderId} の商品準備が完了しました。`;


    try {
        const orderDetails = await apiRequest(`/picker/orders/${orderId}`, 'GET', null, true); // Assuming full details are here

        // Populate Order Summary Table 1
        if (orderSummaryId) orderSummaryId.textContent = orderDetails.id;
        if (orderSummaryPickupSlot && orderDetails.pickup_slot) {
            const slotDate = new Date(orderDetails.pickup_slot.date).toLocaleDateString('ja-JP');
            orderSummaryPickupSlot.textContent = `${slotDate} ${orderDetails.pickup_slot.start_time.substring(0,5)} - ${orderDetails.pickup_slot.end_time.substring(0,5)}`;
        }
        if (orderSummaryItemCount) orderSummaryItemCount.textContent = `${orderDetails.item_count_summary || (orderDetails.order_items ? orderDetails.order_items.length : 0)}種類 ${orderDetails.total_quantity || 0}点`;
        if (orderSummaryTotalAmount) orderSummaryTotalAmount.textContent = `¥${Number(orderDetails.total_amount).toLocaleString()} (税込)`;

        // Populate Order Summary Table 2
        if (orderSummaryStatus) orderSummaryStatus.innerHTML = `<span class="badge badge-success">${orderDetails.status_display || '準備完了'}</span>`;
        if (orderSummaryStartTime) orderSummaryStartTime.textContent = orderDetails.picking_started_at ? new Date(orderDetails.picking_started_at).toLocaleString('ja-JP') : 'N/A';
        if (orderSummaryCompletionTime) orderSummaryCompletionTime.textContent = orderDetails.picking_completed_at ? new Date(orderDetails.picking_completed_at).toLocaleString('ja-JP') : 'N/A';
        if (orderSummaryProcessingTime) orderSummaryProcessingTime.textContent = orderDetails.processing_duration_display || 'N/A'; // e.g., "7分"

        // Populate Prepared Items
        if (preparedItemsTbody) {
            preparedItemsTbody.innerHTML = ''; // Clear static
            if (orderDetails.order_items && orderDetails.order_items.length > 0) {
                orderDetails.order_items.forEach(item => {
                    const product = item.product || {};
                    const row = preparedItemsTbody.insertRow();
                    row.innerHTML = `
                        <td><img src="${product.image_url || '../images/product_placeholder.png'}" alt="${product.name || 'N/A'}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 4px;"></td>
                        <td>
                            <h4 style="margin: 0 0 5px 0;">${product.name || 'N/A'}</h4>
                            <p style="margin: 0; font-size: 14px; color: #666;">${item.notes || product.variant_info || ''}</p>
                        </td>
                        <td>${item.quantity}</td>
                        <td><span class="badge badge-${item.picking_status === 'PICKED' ? 'success' : (item.picking_status === 'SUBSTITUTED' ? 'warning' : 'secondary')}">${item.picking_status_display || item.picking_status}</span></td>
                    `;
                });
            } else {
                preparedItemsTbody.innerHTML = '<tr><td colspan="4" class="text-center">商品情報がありません。</td></tr>';
            }
        }

        // Populate Packaging Info
        if (packagingTypeEl) packagingTypeEl.textContent = orderDetails.packaging_info?.type || 'N/A';
        if (packagingNotesEl) packagingNotesEl.textContent = orderDetails.packaging_info?.notes || 'N/A';
        if (packagingAssignedLaneEl) packagingAssignedLaneEl.textContent = orderDetails.assigned_lane || 'N/A';

        // Populate Label Info
        if(labelOrderId) labelOrderId.textContent = orderDetails.id;
        if(labelPickupSlot && orderDetails.pickup_slot) labelPickupSlot.textContent = `受取時間枠: ${new Date(orderDetails.pickup_slot.date).toLocaleDateString('ja-JP')} ${orderDetails.pickup_slot.start_time.substring(0,5)} - ${orderDetails.pickup_slot.end_time.substring(0,5)}`;
        if(labelLane) labelLane.textContent = `レーン: ${orderDetails.assigned_lane || 'N/A'}`;
        if(labelItemCountDisplay) labelItemCountDisplay.textContent = `商品点数: ${orderDetails.item_count_summary || (orderDetails.order_items ? orderDetails.order_items.length : 0)}種類 ${orderDetails.total_quantity || 0}点`;
        if(labelPickerName && payload) labelPickerName.textContent = `ピッカー: ${payload.name || payload.sub || 'N/A'}`;


        // Populate Handover Info (display only for now)
        if (handoverNotesTextarea) handoverNotesTextarea.value = orderDetails.handover_info?.notes || '';
        if (handoverLocationSelect) handoverLocationSelect.value = orderDetails.handover_info?.location || '';

        // TODO: Add event listeners for reprint label, saving handover info if editable.

    } catch (error) {
        console.error('Failed to load order completion details:', error);
        document.querySelector('.container').innerHTML = `<p class="text-danger text-center">注文完了詳細の読み込みに失敗しました: ${error.message}</p><a href="dashboard.html" class="btn">ダッシュボードへ戻る</a>`;
    }
});

// BOPIS_Lou/frontend/js/pages/counter/complete-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, logout, getAccessToken } from '../../auth.js';
import { decodeJWT, redirectTo } from '../../utils.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['counter'], '../counter/login.html')) {
        return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const orderId = urlParams.get('orderId');

    // Header elements
    const counterNameDisplay = document.getElementById('counter-name-display-header');
    const counterTenantDisplay = document.getElementById('counter-tenant-display-header');
    const counterLaneDisplay = document.getElementById('counter-lane-display-header');
    const logoutButton = document.getElementById('counter-logout-button-header');

    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('../counter/login.html');
        });
    }

    const token = getAccessToken();
    const payload = token ? decodeJWT(token) : null;
    let currentLaneId = null;
    if (payload) {
        if (counterNameDisplay) counterNameDisplay.textContent = `ようこそ、${payload.name || payload.sub || '受付担当'}様`;
        if (counterTenantDisplay) counterTenantDisplay.textContent = `テナント: ${payload.tenant_name || (payload.tenant_id ? `ID ${payload.tenant_id}` : 'N/A')}`;
        if (counterLaneDisplay) {
           counterLaneDisplay.textContent = `担当レーン: ${payload.assigned_lane || 'N/A'}`;
           currentLaneId = payload.assigned_lane_id || payload.assigned_lane; // Assuming lane ID is available
        }
    }

    // Page-specific elements
    const orderIdCompletionMsg = document.getElementById('order-id-completion-message');

    // Handover Info Table 1
    const handoverInfoOrderId = document.getElementById('handover-info-order-id');
    const handoverInfoCustomerName = document.getElementById('handover-info-customer-name');
    const handoverInfoPickupSlot = document.getElementById('handover-info-pickup-slot');
    const handoverInfoItemCount = document.getElementById('handover-info-item-count');
    const handoverInfoTotalAmount = document.getElementById('handover-info-total-amount');

    // Handover Info Table 2 (Timestamps & Status)
    const handoverInfoStatus = document.getElementById('handover-info-status');
    const handoverInfoPrepTime = document.getElementById('handover-info-prep-time');
    const handoverInfoVerifyTime = document.getElementById('handover-info-verify-time');
    const handoverInfoCompletionTime = document.getElementById('handover-info-completion-time');
    const handoverInfoProcessingDuration = document.getElementById('handover-info-processing-duration');

    const completedItemsTbody = document.getElementById('completed-items-tbody');

    // Handover Feedback (display only for now)
    const handoverNotesTextareaRead = document.getElementById('handover-note-read'); // Using existing ID from verify page: handover-note
    const customerSatisfactionSelectRead = document.getElementById('customer-satisfaction-read'); // Using existing ID: customer-satisfaction
    const issueReportSelectRead = document.getElementById('issue-report-read'); // Using existing ID: issue-report

    const nextCustomersTbody = document.getElementById('next-customers-tbody');
    const nextCustomersMessage = document.getElementById('next-customers-message');

    const mainContainer = document.querySelector('.container');

    if (!orderId) {
        if(mainContainer) mainContainer.innerHTML = '<p class="text-danger text-center">注文IDが指定されていません。</p><a href="dashboard.html" class="btn">ダッシュボードへ戻る</a>';
        return;
    }

    if (orderIdCompletionMsg) orderIdCompletionMsg.textContent = `注文 ${orderId} の商品受け渡しが完了しました。`;

    try {
        const details = await apiRequest(`/counter/orders/${orderId}/completion-summary`, 'GET', null, true);

        // Populate Handover Info Table 1
        if (handoverInfoOrderId) handoverInfoOrderId.textContent = details.order.id;
        if (handoverInfoCustomerName) handoverInfoCustomerName.textContent = details.customer?.name || 'N/A';
        if (handoverInfoPickupSlot && details.order.pickup_slot) {
            const slotDate = new Date(details.order.pickup_slot.date).toLocaleDateString('ja-JP');
            handoverInfoPickupSlot.textContent = `${slotDate} ${details.order.pickup_slot.start_time.substring(0,5)} - ${details.order.pickup_slot.end_time.substring(0,5)}`;
        }
        if (handoverInfoItemCount) handoverInfoItemCount.textContent = `${details.order.item_count_summary || 0}種類 ${details.order.total_quantity || 0}点`;
        if (handoverInfoTotalAmount) handoverInfoTotalAmount.textContent = `¥${Number(details.order.total_amount).toLocaleString()} (税込)`;

        // Populate Handover Info Table 2
        if (handoverInfoStatus) handoverInfoStatus.innerHTML = `<span class="badge badge-success">${details.order.status_display || '受け渡し完了'}</span>`;
        if (handoverInfoPrepTime) handoverInfoPrepTime.textContent = details.order.picking_completed_at ? new Date(details.order.picking_completed_at).toLocaleString('ja-JP') : 'N/A';
        if (handoverInfoVerifyTime) handoverInfoVerifyTime.textContent = details.order.verification_timestamp ? new Date(details.order.verification_timestamp).toLocaleString('ja-JP') : 'N/A';
        if (handoverInfoCompletionTime) handoverInfoCompletionTime.textContent = details.order.completed_at ? new Date(details.order.completed_at).toLocaleString('ja-JP') : 'N/A';
        if (handoverInfoProcessingDuration) handoverInfoProcessingDuration.textContent = details.order.counter_processing_duration_display || 'N/A';


        // Populate Completed Items
        if (completedItemsTbody) {
            completedItemsTbody.innerHTML = '';
            if (details.order.order_items && details.order.order_items.length > 0) {
                details.order.order_items.forEach(item => {
                    const product = item.product || {};
                    const row = completedItemsTbody.insertRow();
                    row.innerHTML = `
                        <td><img src="${product.image_url || '../images/product_placeholder.png'}" alt="${product.name || 'N/A'}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 4px;"></td>
                        <td>
                            <h4 style="margin: 0 0 5px 0;">${product.name || 'N/A'}</h4>
                            <p style="margin: 0; font-size: 14px; color: #666;">${product.variant_info || ''}</p>
                        </td>
                        <td>${item.quantity}</td>
                        <td>${item.notes ? `<span class="badge badge-warning">${item.notes}</span>` : ''}</td>
                    `;
                });
            }
        }

        // Populate Handover Feedback (display only)
        // Note: Using the IDs from the verify page for these elements as they are likely the same structure
        // For read-only display, these should ideally be <p> tags or disabled. For now, populating value.
        const feedbackNotesEl = document.getElementById('handover-note'); // ID from verify.html
        const feedbackSatisfactionEl = document.getElementById('customer-satisfaction'); // ID from verify.html
        const feedbackIssueEl = document.getElementById('issue-report'); // ID from verify.html

        if (feedbackNotesEl) feedbackNotesEl.value = details.handover_feedback?.notes || '';
        if (feedbackSatisfactionEl) feedbackSatisfactionEl.value = details.handover_feedback?.satisfaction || '';
        if (feedbackIssueEl) feedbackIssueEl.value = details.handover_feedback?.issue_type || 'なし';

        // If these elements should be strictly read-only:
        if (feedbackNotesEl) feedbackNotesEl.disabled = true;
        if (feedbackSatisfactionEl) feedbackSatisfactionEl.disabled = true;
        if (feedbackIssueEl) feedbackIssueEl.disabled = true;


    } catch (error) {
        console.error('Failed to load order completion summary:', error);
        if(mainContainer) mainContainer.innerHTML = `<p class="text-danger text-center">完了情報の読み込みに失敗しました: ${error.message}</p><a href="dashboard.html" class="btn">ダッシュボードへ戻る</a>`;
    }

    // Fetch next customers for the lane
    if (currentLaneId && nextCustomersTbody && nextCustomersMessage) {
       nextCustomersTbody.innerHTML = '<tr><td colspan="5" class="text-center">読み込み中...</td></tr>';
       try {
           const nextOrdersData = await apiRequest(`/counter/orders?status=READY_FOR_PICKUP&lane_id=${currentLaneId}&limit=2&exclude_order_id=${orderId}`, 'GET', null, true);
           if (nextOrdersData && nextOrdersData.items && nextOrdersData.items.length > 0) {
               nextCustomersMessage.textContent = `レーン${currentLaneId}には、あと${nextOrdersData.total_count || nextOrdersData.items.length}件の準備完了注文があります。`;
               nextCustomersTbody.innerHTML = '';
               nextOrdersData.items.forEach(nextOrder => {
                   const row = nextCustomersTbody.insertRow();
                   row.innerHTML = `
                       <td>${nextOrder.id}</td>
                       <td>${nextOrder.pickup_slot?.display_time || 'N/A'}</td>
                       <td>${nextOrder.item_count_summary || 'N/A'}</td>
                       <td>${nextOrder.ready_at ? new Date(nextOrder.ready_at).toLocaleTimeString('ja-JP') : 'N/A'}</td>
                       <td><a href="verify.html?orderId=${nextOrder.id}" class="btn btn-primary btn-sm">受け取り処理</a></td>
                   `;
               });
           } else {
               nextCustomersMessage.textContent = `レーン${currentLaneId}には、他に準備完了の注文はありません。`;
               nextCustomersTbody.innerHTML = '<tr><td colspan="5" class="text-center">次の注文はありません。</td></tr>';
           }
       } catch (error) {
            console.error('Failed to load next customers:', error);
            nextCustomersMessage.textContent = '次の顧客情報の読み込みに失敗しました。';
            nextCustomersTbody.innerHTML = '<tr><td colspan="5" class="text-danger text-center">エラー</td></tr>';
       }
    } else if (nextCustomersMessage) {
       nextCustomersMessage.textContent = '担当レーン情報が不明なため、次の顧客情報を表示できません。';
    }

});

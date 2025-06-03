// BOPIS_Lou/frontend/js/pages/counter/verify-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, logout, getAccessToken } from '../../auth.js';
import { decodeJWT, redirectTo } from '../../utils.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['counter'], '../counter/login.html')) {
        return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const orderId = urlParams.get('orderId'); // Or from a QR scan result

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
    if (payload) {
        if (counterNameDisplay) counterNameDisplay.textContent = `ようこそ、${payload.name || payload.sub || '受付担当'}様`;
        if (counterTenantDisplay) counterTenantDisplay.textContent = `テナント: ${payload.tenant_name || (payload.tenant_id ? `ID ${payload.tenant_id}` : 'N/A')}`;
        if (counterLaneDisplay) counterLaneDisplay.textContent = `担当レーン: ${payload.assigned_lane || 'N/A'}`;
    }

    // Page-specific elements
    const orderIdScannedInfo = document.getElementById('order-id-scanned-info');
    const assignedLaneInfo = document.getElementById('assigned-lane-info');

    // Customer Info Table
    const customerNameEl = document.getElementById('customer-name');
    const customerEmailEl = document.getElementById('customer-email');
    const customerPhoneEl = document.getElementById('customer-phone');
    const customerOrderTimestampEl = document.getElementById('customer-order-timestamp');
    const customerPickupSlotEl = document.getElementById('customer-pickup-slot');

    // Order Info Table
    const orderInfoIdEl = document.getElementById('order-info-id');
    const orderInfoItemCountEl = document.getElementById('order-info-item-count');
    const orderInfoTotalAmountEl = document.getElementById('order-info-total-amount');
    const orderInfoPrepStatusEl = document.getElementById('order-info-prep-status');
    const orderInfoPrepCompletionTimeEl = document.getElementById('order-info-prep-completion-time');

    // Verification Questions (example for dynamic answer part)
    const verificationQ1Answer = document.getElementById('verification-q1-answer');
    const verificationQ2Answer = document.getElementById('verification-q2-answer');

    const orderItemsTbody = document.getElementById('order-items-tbody');
    const orderItemsSubtotal = document.getElementById('order-items-subtotal');
    const orderItemsSystemFee = document.getElementById('order-items-system-fee');
    const orderItemsTotal = document.getElementById('order-items-total');

    const pickerHandoverNotesEl = document.getElementById('picker-handover-notes');
    const handoverCompleteButton = document.getElementById('handover-complete-button');

    const mainContainer = document.querySelector('.container');


    if (!orderId) {
        if(mainContainer) mainContainer.innerHTML = '<p class="text-danger text-center">注文IDが指定されていません。ダッシュボードから再度操作してください。</p><a href="dashboard.html" class="btn">ダッシュボードへ戻る</a>';
        return;
    }

    if (orderIdScannedInfo) orderIdScannedInfo.textContent = `注文番号: ${orderId}`;
    // Assigned Lane for this transaction could also be dynamic if needed
    if (assignedLaneInfo && payload && payload.assigned_lane) assignedLaneInfo.textContent = `レーン${payload.assigned_lane}`;


    try {
        const details = await apiRequest(`/counter/orders/${orderId}/verification-details`, 'GET', null, true);

        // Populate Customer Info
        if (customerNameEl) customerNameEl.textContent = details.customer?.name || 'N/A';
        if (customerEmailEl) customerEmailEl.textContent = details.customer?.email || 'N/A';
        if (customerPhoneEl) customerPhoneEl.textContent = details.customer?.phone || 'N/A';
        if (customerOrderTimestampEl) customerOrderTimestampEl.textContent = new Date(details.order.created_at).toLocaleString('ja-JP');
        if (customerPickupSlotEl && details.order.pickup_slot) {
            const slotDate = new Date(details.order.pickup_slot.date).toLocaleDateString('ja-JP');
            customerPickupSlotEl.textContent = `${slotDate} ${details.order.pickup_slot.start_time.substring(0,5)} - ${details.order.pickup_slot.end_time.substring(0,5)}`;
        }

        // Populate Order Info
        if (orderInfoIdEl) orderInfoIdEl.textContent = details.order.id;
        if (orderInfoItemCountEl) orderInfoItemCountEl.textContent = `${details.order.item_count_summary || 0}種類 ${details.order.total_quantity || 0}点`;
        if (orderInfoTotalAmountEl) orderInfoTotalAmountEl.textContent = `¥${Number(details.order.total_amount).toLocaleString()} (税込)`;
        if (orderInfoPrepStatusEl) orderInfoPrepStatusEl.innerHTML = `<span class="badge badge-${details.order.status === 'READY_FOR_PICKUP' ? 'success' : 'warning'}">${details.order.status_display || 'N/A'}</span>`;
        if (orderInfoPrepCompletionTimeEl) orderInfoPrepCompletionTimeEl.textContent = details.order.picking_completed_at ? new Date(details.order.picking_completed_at).toLocaleString('ja-JP') : 'N/A';

        // Populate Verification Question Answers (example)
        if (verificationQ1Answer) verificationQ1Answer.textContent = details.customer?.name || 'N/A'; // For "お客様のお名前を教えてください。"
        // For "ご注文いただいた「ツアータオル」は何点ですか？" - this requires finding a specific item.
        // This part needs more complex logic based on how verification questions are structured/generated.
        // For now, if `details.verification_questions` is an array:
        if (details.verification_questions && details.verification_questions.length > 0) {
           if (verificationQ1Answer && details.verification_questions[0]) verificationQ1Answer.textContent = details.verification_questions[0].answer;
           if (verificationQ2Answer && details.verification_questions[1]) verificationQ2Answer.textContent = details.verification_questions[1].answer;
        }


        // Populate Order Items Table
        if (orderItemsTbody) {
            orderItemsTbody.innerHTML = '';
            if (details.order.order_items && details.order.order_items.length > 0) {
                details.order.order_items.forEach(item => {
                    const product = item.product || {};
                    const row = orderItemsTbody.insertRow();
                    row.innerHTML = `
                        <td><img src="${product.image_url || '../images/product_placeholder.png'}" alt="${product.name || 'N/A'}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 4px;"></td>
                        <td>
                            <h4 style="margin: 0 0 5px 0;">${product.name || 'N/A'}</h4>
                            <p style="margin: 0; font-size: 14px; color: #666;">${product.variant_info || ''}</p>
                        </td>
                        <td>${item.quantity}</td>
                        <td>¥${Number(item.price_at_purchase * item.quantity).toLocaleString()}</td>
                        <td>${item.notes ? `<span class="badge badge-warning">${item.notes}</span>` : ''}</td>
                    `;
                });
            }
            // Populate tfoot totals
            if (orderItemsSubtotal) orderItemsSubtotal.textContent = `¥${Number(details.order.subtotal_amount || 0).toLocaleString()}`;
            if (orderItemsSystemFee) orderItemsSystemFee.textContent = `¥${Number(details.order.system_fee_amount || 0).toLocaleString()}`;
            if (orderItemsTotal) orderItemsTotal.textContent = `¥${Number(details.order.total_amount).toLocaleString()}`;
        }

        // Populate Picker's Handover Notes
        if (pickerHandoverNotesEl && details.order.picker_handover_notes) {
            pickerHandoverNotesEl.textContent = details.order.picker_handover_notes;
        } else if (pickerHandoverNotesEl) {
            pickerHandoverNotesEl.textContent = '特記事項なし';
        }


        // Event listener for "Handover Complete" button
        if (handoverCompleteButton) {
            handoverCompleteButton.addEventListener('click', async () => {
                // const verificationNote = document.getElementById('verification-note').value;
                // const customerExplanation = document.getElementById('customer-explanation').value;
                // Include these notes and verification question results in the API call if needed.
                try {
                    await apiRequest(`/counter/orders/${orderId}/complete-handover`, 'POST', {
                        // verification_notes: verificationNote,
                        // customer_explanation_notes: customerExplanation,
                        // verification_checks: [...] // Pass results of checks
                    }, true);
                    redirectTo(`complete.html?orderId=${orderId}`); // Redirect to counter complete page
                } catch (error) {
                    alert(`受け渡し完了処理に失敗しました: ${error.message}`);
                    console.error('Handover completion failed:', error);
                }
            });
        }

    } catch (error) {
        console.error('Failed to load order verification details:', error);
        if(mainContainer) mainContainer.innerHTML = `<p class="text-danger text-center">注文詳細の読み込みに失敗しました: ${error.message}</p><a href="dashboard.html" class="btn">ダッシュボードへ戻る</a>`;
    }
});

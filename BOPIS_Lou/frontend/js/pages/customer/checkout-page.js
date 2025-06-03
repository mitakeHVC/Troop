// BOPIS_Lou/frontend/js/pages/customer/checkout-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, getAccessToken, logout } from '../../auth.js';
import { decodeJWT, updateCartBadgeCount, redirectTo } from '../../utils.js';

const SELECTED_TENANT_ID_KEY = 'selectedTenantId';
// const SELECTED_TENANT_NAME_KEY = 'selectedTenantName'; // Not strictly needed on this page display

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['customer'], 'login.html')) {
        return;
    }

    let tenantId = localStorage.getItem(SELECTED_TENANT_ID_KEY);
    if (!tenantId) {
        const token = getAccessToken();
        if (token) {
            const payload = decodeJWT(token);
            if (payload && payload.tenant_id) {
                tenantId = payload.tenant_id.toString();
                localStorage.setItem(SELECTED_TENANT_ID_KEY, tenantId);
                // If tenant name available in JWT, could store it too
            }
        }
        if (!tenantId) {
            // alert("表示するテナントが選択されていません。テナント選択ページに移動します。");
            redirectTo('tenants.html');
            return;
        }
    }

    const checkoutCartSummaryEl = document.getElementById('checkout-cart-summary');
    const timeslotSelectionContainerEl = document.getElementById('timeslot-selection-container');
    const checkoutForm = document.getElementById('checkout-form');
    const errorMessageEl = document.getElementById('checkout-error-message');

    let currentCart = null;

    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('login.html');
        });
    }
    await updateCartBadgeCount();

    try {
        currentCart = await apiRequest('/orders/cart', 'GET', null, true);
        if (checkoutCartSummaryEl && currentCart && currentCart.order_items && currentCart.order_items.length > 0) { // check if order_items exist and has items
            const totalItems = currentCart.order_items.reduce((sum, item) => sum + item.quantity, 0);
            checkoutCartSummaryEl.innerHTML = `
                <p>合計商品数: ${totalItems}点</p>
                <p>お支払い総額: ¥${Number(currentCart.total_amount).toLocaleString()}</p>
            `;
            if (totalItems === 0) {
                 if(checkoutForm) checkoutForm.querySelector('button[type="submit"]').disabled = true;
                 if(errorMessageEl) {
                     errorMessageEl.textContent = 'カートが空です。商品を追加してください。';
                     errorMessageEl.style.display = 'block';
                 }
            }
        } else if (checkoutCartSummaryEl) { // Cart is empty or failed to load
            checkoutCartSummaryEl.innerHTML = '<p>カートが空です。チェックアウトに進むには商品を追加してください。</p>';
            if(checkoutForm) {
                checkoutForm.style.display = 'none'; // Hide form itself
            }
        }
    } catch (error) {
        console.error("Failed to load cart summary:", error);
        if (checkoutCartSummaryEl) checkoutCartSummaryEl.innerHTML = '<p class="text-danger">カート概要の読み込みに失敗しました。</p>';
        if(checkoutForm) checkoutForm.style.display = 'none';
    }

    try {
        const timeslotsData = await apiRequest(`/timeslots/tenant/${tenantId}/available`, 'GET', null, true);
        if (timeslotSelectionContainerEl && timeslotsData && timeslotsData.items && timeslotsData.items.length > 0) {
            let slotsHTML = '<p class="font-medium mb-2">受取時間を選択してください:</p>';
            timeslotsData.items.forEach(slot => {
                const slotDate = new Date(slot.date).toLocaleDateString('ja-JP', { year: 'numeric', month: 'long', day: 'numeric' });
                slotsHTML += `
                    <div class="form-check mb-2">
                        <input class="form-check-input" type="radio" name="pickup_slot_id" id="slot-${slot.id}" value="${slot.id}" required>
                        <label class="form-check-label" for="slot-${slot.id}">
                            ${slotDate} ${slot.start_time.substring(0,5)} - ${slot.end_time.substring(0,5)} (残り: ${slot.capacity - slot.current_orders})
                        </label>
                    </div>`;
            });
            timeslotSelectionContainerEl.innerHTML = slotsHTML;
        } else if (timeslotSelectionContainerEl) {
            timeslotSelectionContainerEl.innerHTML = '<p class="text-warning">現在利用可能な受取時間がありません。</p>';
             if(checkoutForm && checkoutForm.querySelector('button[type="submit"]')) checkoutForm.querySelector('button[type="submit"]').disabled = true;
        }
    } catch (error) {
        console.error("Failed to load time slots:", error);
        if (timeslotSelectionContainerEl) timeslotSelectionContainerEl.innerHTML = '<p class="text-danger">受取時間の読み込みに失敗しました。</p>';
    }

    if (checkoutForm) {
        checkoutForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if(errorMessageEl) {
                errorMessageEl.style.display = 'none';
                errorMessageEl.textContent = '';
            }

            if (!currentCart || !currentCart.id || !currentCart.order_items || currentCart.order_items.length === 0) {
                if(errorMessageEl) {
                    errorMessageEl.textContent = 'カートが空か、カート情報が見つかりません。';
                    errorMessageEl.style.display = 'block';
                }
                return;
            }
            const selectedSlot = checkoutForm.querySelector('input[name="pickup_slot_id"]:checked');
            if (!selectedSlot) {
                if(errorMessageEl) {
                    errorMessageEl.textContent = '受取時間を選択してください。';
                    errorMessageEl.style.display = 'block';
                }
                return;
            }
            const cartOrderId = currentCart.id;
            const selectedSlotId = parseInt(selectedSlot.value);

            const submitButton = checkoutForm.querySelector('button[type="submit"]');
            if(submitButton) submitButton.disabled = true;

            try {
                const orderResult = await apiRequest(`/orders/${cartOrderId}/checkout`, 'POST', { pickup_slot_id: selectedSlotId }, true);
                if (orderResult && orderResult.id) {
                    redirectTo(`order-confirmation.html?orderId=${orderResult.id}&tenantId=${tenantId}`);
                } else {
                    if(errorMessageEl) {
                         errorMessageEl.textContent = 'チェックアウトに失敗しました。予期せぬ応答。';
                         errorMessageEl.style.display = 'block';
                    }
                    if(submitButton) submitButton.disabled = false;
                }
            } catch (error) {
                console.error('Checkout failed:', error);
                if(errorMessageEl) {
                    errorMessageEl.textContent = `チェックアウトエラー: ${error.message.includes('400') ? '選択した時間枠の予約数が上限に達したか、カートの内容に問題があります。時間枠を選び直すかカートを確認してください。' : error.message}`;
                    errorMessageEl.style.display = 'block';
                }
                if(submitButton) submitButton.disabled = false;
            }
        });
    }
});

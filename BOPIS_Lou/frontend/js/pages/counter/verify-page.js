// BOPIS_Lou/frontend/js/pages/counter/verify-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, getAccessToken, logout } from '../../auth.js';
import { decodeJWT, redirectTo } from '../../utils.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['counter'], 'login.html')) { return; }

    const token = getAccessToken();
    const payload = decodeJWT(token);
    // let tenantId = payload ? payload.tenant_id : null; // Not directly used for verify/complete logic but for header
    // let counterUserId = payload ? payload.sub : null;

    const urlParams = new URLSearchParams(window.location.search);
    const orderIdFromUrl = urlParams.get('orderId');
    const pickupTokenFromUrl = urlParams.get('token'); // Pickup token from dashboard link

    // Header elements
    const counterNameEl = document.getElementById('counter-name');
    const counterTenantNameEl = document.getElementById('counter-tenant-name');
    const logoutButton = document.getElementById('counter-logout-button');

    // Page elements
    const orderIdDisplayEl = document.getElementById('verify-order-id');
    const pickupTokenInputEl = document.getElementById('pickup-token-input');
    const verifyTokenForm = document.getElementById('verify-token-form');
    const verificationResultEl = document.getElementById('verification-result');
    const completeOrderButtonEl = document.getElementById('complete-order-button');
    const pageErrorMessageEl = document.getElementById('page-error-message');

    let verifiedOrderId = orderIdFromUrl; // Store the order ID from successful verification or URL

    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => { e.preventDefault(); logout('login.html'); });
    }

    // Display Counter Name & Tenant Name (from JWT payload)
    if (counterNameEl && payload && payload.sub) {
        try {
            const userInfo = await apiRequest('/users/me', 'GET', null, true);
            counterNameEl.textContent = userInfo.username || 'カウンター様';
        } catch (e) { console.warn("Failed to fetch counter user info:", e); counterNameEl.textContent = 'カウンター様'; }
    }
    if (counterTenantNameEl && payload && payload.tenant_id) {
        try {
            const tenantInfo = await apiRequest(`/tenants/${payload.tenant_id}`, 'GET', null, true);
            counterTenantNameEl.textContent = tenantInfo.name || `テナントID: ${payload.tenant_id}`;
        } catch (e) { counterTenantNameEl.textContent = `テナントID: ${payload.tenant_id}`; }
    } else if(counterTenantNameEl) {
         counterTenantNameEl.textContent = "テナント情報なし";
    }


    if (orderIdDisplayEl && orderIdFromUrl) {
        orderIdDisplayEl.textContent = orderIdFromUrl;
    }
    if (pickupTokenInputEl && pickupTokenFromUrl) {
        pickupTokenInputEl.value = pickupTokenFromUrl;
    }
    if (completeOrderButtonEl) completeOrderButtonEl.style.display = 'none'; // Hide initially

    if (verifyTokenForm) {
        verifyTokenForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if(pageErrorMessageEl) { pageErrorMessageEl.textContent = ''; pageErrorMessageEl.style.display = 'none'; }
            if(verificationResultEl) verificationResultEl.innerHTML = '';
            if(completeOrderButtonEl) completeOrderButtonEl.style.display = 'none';

            const tokenToVerify = pickupTokenInputEl ? pickupTokenInputEl.value : null;
            if (!tokenToVerify) {
                if(pageErrorMessageEl) { pageErrorMessageEl.textContent = '受取トークンを入力してください。'; pageErrorMessageEl.style.display = 'block'; }
                return;
            }

            try {
                // API: POST /orders/verify-pickup with { pickup_token: "string" }
                const verificationInfo = await apiRequest('/orders/verify-pickup', 'POST', { pickup_token: tokenToVerify }, true);

                if (verificationResultEl && verificationInfo) {
                    verifiedOrderId = verificationInfo.order_id; // Update order ID from verified response
                    if (orderIdDisplayEl) orderIdDisplayEl.textContent = verifiedOrderId; // Update display if different

                    let verificationHtml = `
                        <h4 class="text-lg font-semibold text-success mb-2">認証成功</h4>
                        <p><strong>注文ID:</strong> ${verificationInfo.order_id}</p>
                        <p><strong>顧客名:</strong> ${verificationInfo.customer_username}</p>`;
                    if (verificationInfo.identity_verification_product_name) {
                        verificationHtml += `
                            <p class="mt-2 text-primary"><strong>確認項目:</strong></p>
                            <p>"${verificationInfo.identity_verification_product_name}" を購入されましたか？</p>
                            ${verificationInfo.identity_verification_product_quantity ? `<p>(数量: ${verificationInfo.identity_verification_product_quantity}点)</p>` : ''}
                        `;
                    } else {
                        verificationHtml += `<p class="mt-2 text-muted">追加の確認項目はありません。</p>`;
                    }
                    verificationResultEl.innerHTML = verificationHtml;
                    if (completeOrderButtonEl) completeOrderButtonEl.style.display = 'block';
                } else if (verificationResultEl) {
                    verificationResultEl.innerHTML = '<p class="text-warning">認証情報を取得できませんでした。</p>';
                }

            } catch (error) {
                console.error('Token verification failed:', error);
                if(verificationResultEl) verificationResultEl.innerHTML = `<p class="text-danger">トークン認証失敗: ${error.message}</p>`;
            }
        });
    }

    if (completeOrderButtonEl) {
        completeOrderButtonEl.addEventListener('click', async () => {
            if (!verifiedOrderId) {
                alert('認証済みの注文IDがありません。再度トークンを認証してください。');
                return;
            }
             if (!confirm(`注文ID: ${verifiedOrderId} の受渡を完了しますか？`)) return;

            try {
                // API: POST /orders/{order_id}/complete-pickup
                await apiRequest(`/orders/${verifiedOrderId}/complete-pickup`, 'POST', { notes: "Counter staff completed pickup." }, true);
                // Redirect to a completion page or back to dashboard
                redirectTo(`complete.html?orderId=${verifiedOrderId}`);
            } catch (error) {
                console.error('Order completion failed:', error);
                if(pageErrorMessageEl) { pageErrorMessageEl.textContent = `注文完了処理失敗: ${error.message}`; pageErrorMessageEl.style.display = 'block';}
                else alert(`注文完了処理失敗: ${error.message}`);
            }
        });
    }

    // If token is passed in URL, trigger verification automatically
    if (pickupTokenInputEl && pickupTokenInputEl.value && verifyTokenForm) {
        verifyTokenForm.dispatchEvent(new Event('submit'));
    }

});

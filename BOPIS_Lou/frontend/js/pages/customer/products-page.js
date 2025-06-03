// BOPIS_Lou/frontend/js/pages/customer/products-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, getAccessToken, logout } from '../../auth.js';
import { decodeJWT, updateCartBadgeCount, redirectTo } from '../../utils.js';
import { createProductCard } from '../../components/productCard.js';

const SELECTED_TENANT_ID_KEY = 'selectedTenantId';
const SELECTED_TENANT_NAME_KEY = 'selectedTenantName';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['customer'], 'login.html')) {
        return;
    }

    let tenantId = localStorage.getItem(SELECTED_TENANT_ID_KEY);
    let tenantName = localStorage.getItem(SELECTED_TENANT_NAME_KEY);

    if (!tenantId) {
        const token = getAccessToken();
        if (token) {
            const payload = decodeJWT(token);
            if (payload && payload.tenant_id) {
                tenantId = payload.tenant_id.toString();
                localStorage.setItem(SELECTED_TENANT_ID_KEY, tenantId);
                // Note: tenantName might not be in JWT.
            }
        }
        if (!tenantId) {
            redirectTo('tenants.html');
            return;
        }
    }

    tenantName = localStorage.getItem(SELECTED_TENANT_NAME_KEY);

    const productListContainer = document.getElementById('product-list-container');
    const tenantNameHeaderEl = document.getElementById('tenant-name-header');
    const pickupTimeSlotElement = document.getElementById('pickup-time-slot');

    if (tenantNameHeaderEl) {
        tenantNameHeaderEl.textContent = tenantName || `テナント ${tenantId}`;
    }

    const logoutButton = document.getElementById('logout-button');
    if(logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('login.html');
        });
    }
    await updateCartBadgeCount();

    if (!productListContainer) { console.error('Product list container not found.'); return; }
    if (pickupTimeSlotElement) pickupTimeSlotElement.textContent = '未選択';
    productListContainer.innerHTML = '<p class="col" style="width:100%; text-align:center;">商品を読み込み中です...</p>';

    try {
        const productsData = await apiRequest(`/products?tenantId=${tenantId}&size=20&page=1`, 'GET', null, true);
        if (productsData && productsData.items && productsData.items.length > 0) {
            productListContainer.innerHTML = '';
            productsData.items.forEach(product => {
                productListContainer.insertAdjacentHTML('beforeend', createProductCard(product, tenantId));
            });
        } else {
            productListContainer.innerHTML = '<p class="col" style="width:100%; text-align:center;">このテナントには現在商品がありません。</p>';
        }

        document.querySelectorAll('.add-to-cart-btn').forEach(button => {
            button.addEventListener('click', async (event) => {
                const productId = event.target.dataset.productId;
                const pName = event.target.dataset.productName || '選択された商品';
                if (productId) {
                    try {
                        await apiRequest('/orders/cart/items', 'POST', { product_id: parseInt(productId), quantity: 1 }, true);
                        alert(`${pName} がカートに追加されました。`);
                        await updateCartBadgeCount();
                    } catch (error) {
                        console.error('Failed to add item to cart:', error);
                        alert('カートへの追加に失敗しました。');
                    }
                }
            });
        });
    } catch (error) {
        console.error('Failed to fetch products:', error);
        productListContainer.innerHTML = '<p class="col text-danger" style="width:100%; text-align:center;">商品の読み込みに失敗しました。</p>';
    }

    const searchInput = document.getElementById('product-search-input');
    const searchButton = document.getElementById('product-search-button');
    if (searchButton && searchInput) {
        searchButton.addEventListener('click', () => {
            const searchTerm = searchInput.value.toLowerCase();
            document.querySelectorAll('#product-list-container .col').forEach(colDiv => {
                const card = colDiv.querySelector('.product-card');
                if (card) {
                    const productName = card.querySelector('h3.card-title').textContent.toLowerCase();
                    if (productName.includes(searchTerm)) {
                        colDiv.style.display = '';
                    } else {
                        colDiv.style.display = 'none';
                    }
                }
            });
        });
    }
});

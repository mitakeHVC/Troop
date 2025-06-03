// BOPIS_Lou/frontend/js/pages/customer/product-detail-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, getAccessToken, logout } from '../../auth.js';
import { decodeJWT, updateCartBadgeCount, redirectTo } from '../../utils.js';

const SELECTED_TENANT_ID_KEY = 'selectedTenantId';
const SELECTED_TENANT_NAME_KEY = 'selectedTenantName';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['customer'], 'login.html')) {
        return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const productId = urlParams.get('id');
    let tenantId = urlParams.get('tenantId');

    if (!tenantId) {
        tenantId = localStorage.getItem(SELECTED_TENANT_ID_KEY);
    }
    if (!tenantId) {
        const token = getAccessToken();
        if (token) {
            const payload = decodeJWT(token);
            if (payload && payload.tenant_id) tenantId = payload.tenant_id.toString();
        }
    }
    if (!tenantId) {
        redirectTo('tenants.html');
        return;
    }

    const productDetailContainer = document.getElementById('product-detail-container');
    const productNameEl = document.getElementById('product-name');
    const productImageEl = document.getElementById('product-image');
    const productPriceEl = document.getElementById('product-price');
    const productDescriptionEl = document.getElementById('product-description');
    const addToCartButton = document.getElementById('add-to-cart-button');
    const quantityInput = document.getElementById('quantity');
    const tenantNameHeaderEl = document.getElementById('tenant-name-header');

    const logoutButton = document.getElementById('logout-button');
    if(logoutButton) {
         logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('login.html');
        });
    }
    await updateCartBadgeCount();

    let tenantName = localStorage.getItem(SELECTED_TENANT_NAME_KEY);
    if (tenantNameHeaderEl) {
        tenantNameHeaderEl.textContent = tenantName || `テナント ${tenantId}`;
    }

    if (!productId) { productDetailContainer.innerHTML = '<p>Product ID is missing.</p>'; return; }
    if (!productDetailContainer){ return; }

    try {
        const product = await apiRequest(`/products/${productId}?tenantId=${tenantId}`, 'GET', null, true);
        if (productNameEl) productNameEl.textContent = product.name;
        if (productPriceEl) productPriceEl.textContent = `¥${Number(product.price).toLocaleString()}`;
        if (productDescriptionEl) productDescriptionEl.textContent = product.description || 'No description available.';
        if (productImageEl) {
            let pName = product.name || 'Product';
            productImageEl.src = product.image_url || ('https://via.placeholder.com/400x300.png?text=' + encodeURIComponent(pName));
            productImageEl.alt = pName;
        }

        // Update header tenant name more accurately if product details include it
        // For now, it uses what was in localStorage or the ID.

        if (addToCartButton) {
            addToCartButton.dataset.productId = product.id;
            addToCartButton.dataset.productName = product.name;
            addToCartButton.addEventListener('click', async () => {
                const quantity = quantityInput ? parseInt(quantityInput.value) : 1;
                if (quantity < 1) {
                    alert("数量は1以上で入力してください。");
                    return;
                }
                try {
                    await apiRequest('/orders/cart/items', 'POST', { product_id: parseInt(product.id), quantity: quantity }, true);
                    alert(`${product.name} (数量: ${quantity}) がカートに追加されました。`);
                    await updateCartBadgeCount();
                } catch (error) {
                    console.error('Failed to add item to cart:', error);
                    alert('カートへの追加に失敗しました。');
                }
            });
        }
    } catch (error) {
        productDetailContainer.innerHTML = '<p class="text-danger text-center">商品の読み込みに失敗しました。</p>';
    }
});

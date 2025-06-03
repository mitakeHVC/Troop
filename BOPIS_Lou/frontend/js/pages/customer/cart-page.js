// BOPIS_Lou/frontend/js/pages/customer/cart-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, logout } from '../../auth.js';
import { updateCartBadgeCount } from '../../utils.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['customer'], 'login.html')) {
        return;
    }

    const cartItemsContainer = document.getElementById('cart-items-container');
    const cartTotalElement = document.getElementById('cart-total');
    const emptyCartMessageEl = document.getElementById('empty-cart-message');
    const cartSummaryContainerEl = document.getElementById('cart-summary-container');

    const logoutButton = document.getElementById('logout-button');
    if(logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('login.html');
        });
    }

    if(cartItemsContainer) cartItemsContainer.innerHTML = '<p>カートを読み込み中です...</p>';
    if(emptyCartMessageEl) emptyCartMessageEl.style.display = 'none';
    if(cartSummaryContainerEl) cartSummaryContainerEl.style.display = 'none';

    await updateCartBadgeCount();
    await renderCart();

    async function renderCart() {
        try {
            const cart = await apiRequest('/orders/cart', 'GET', null, true);
            await updateCartBadgeCount();

            if (cart && cart.order_items && cart.order_items.length > 0) {
                if(emptyCartMessageEl) emptyCartMessageEl.style.display = 'none';
                if(cartSummaryContainerEl) cartSummaryContainerEl.style.display = 'block';
                if(cartItemsContainer) cartItemsContainer.innerHTML = '';

                let totalAmount = 0;

                cart.order_items.forEach(item => {
                    const itemTotal = item.price_at_purchase * item.quantity;
                    totalAmount += itemTotal;
                    const product = item.product || { name: 'N/A', image_url: '' };
                    let pName = product.name || 'Item';
                    const imageUrl = product.image_url || ('https://via.placeholder.com/100x100.png?text=' + encodeURIComponent(pName));

                    const itemHTML = `
                        <div class="card mb-3 cart-item" data-item-id="${item.id}">
                            <div class="row" style="gap: 15px; display:flex; align-items: center;">
                                <div class="col" style="flex: 0 0 100px;">
                                    <img src="${imageUrl}" alt="${pName}" style="width: 100px; height: 100px; object-fit: cover; border-radius: var(--radius-sm);">
                                </div>
                                <div class="col" style="flex-grow: 1;">
                                    <h5 class="font-semibold">${pName}</h5>
                                    <p class="text-sm text-muted">単価: ¥${Number(item.price_at_purchase).toLocaleString()}</p>
                                </div>
                                <div class="col" style="flex: 0 0 120px; display: flex; align-items: center; gap: 5px;">
                                    <label for="quantity-${item.id}" class="text-sm sr-only">数量:</label>
                                    <input type="number" id="quantity-${item.id}" class="form-control item-quantity-input" value="${item.quantity}" min="1" data-item-id="${item.id}" style="width: 70px; padding: var(--spacing-xs); text-align:center;">
                                </div>
                                <div class="col text-right" style="flex: 0 0 100px;">
                                    <p class="font-semibold">¥${Number(itemTotal).toLocaleString()}</p>
                                </div>
                                <div class="col" style="flex: 0 0 50px;">
                                    <button class="btn btn-danger btn-sm remove-item-btn" data-item-id="${item.id}" title="削除">&times;</button>
                                </div>
                            </div>
                        </div>
                    `;
                    if(cartItemsContainer) cartItemsContainer.insertAdjacentHTML('beforeend', itemHTML);
                });
                if (cartTotalElement) cartTotalElement.textContent = `¥${Number(totalAmount).toLocaleString()}`;
                addCartEventListeners();
            } else {
                if(cartItemsContainer) cartItemsContainer.innerHTML = '';
                if(emptyCartMessageEl) emptyCartMessageEl.style.display = 'block';
                if(cartSummaryContainerEl) cartSummaryContainerEl.style.display = 'none';
                if (cartTotalElement) cartTotalElement.textContent = '¥0';
            }
        } catch (error) {
            console.error('Failed to render cart:', error);
            if(cartItemsContainer) cartItemsContainer.innerHTML = '<p class="text-danger text-center">カートの読み込みに失敗しました。</p>';
            if(emptyCartMessageEl) emptyCartMessageEl.style.display = 'none';
            if(cartSummaryContainerEl) cartSummaryContainerEl.style.display = 'none';
        }
    }

    function addCartEventListeners() {
        document.querySelectorAll('.item-quantity-input').forEach(input => {
            input.addEventListener('change', async (event) => {
                const itemId = event.target.dataset.itemId;
                let newQuantity = parseInt(event.target.value);
                if (isNaN(newQuantity) || newQuantity < 1) {
                    newQuantity = 1;
                    event.target.value = 1;
                }

                try {
                    await apiRequest(`/orders/cart/items/${itemId}`, 'PUT', { quantity: newQuantity }, true);
                    await renderCart();
                } catch (error) {
                    alert('数量の更新に失敗しました。');
                    console.error('Failed to update quantity:', error);
                    await renderCart();
                }
            });
        });

        document.querySelectorAll('.remove-item-btn').forEach(button => {
            button.addEventListener('click', async (event) => {
                const itemId = event.target.dataset.itemId;
                if (confirm('この商品をカートから削除しますか？')) {
                    try {
                        await apiRequest(`/orders/cart/items/${itemId}`, 'DELETE', null, true);
                        await renderCart();
                    } catch (error) {
                        alert('商品の削除に失敗しました。');
                        console.error('Failed to remove item:', error);
                    }
                }
            });
        });
    }
});

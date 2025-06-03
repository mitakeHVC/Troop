// BOPIS_Lou/frontend/js/utils.js
'use strict';
import { apiRequest } from './api.js';
import { isAuthenticated } from './auth.js';

// redirectTo and decodeJWT functions (ensure they are here from previous steps)
export function redirectTo(relativePath) {
    window.location.href = relativePath;
}

export function decodeJWT(token) {
    try {
        const base64Url = token.split('.')[1];
        if (!base64Url) {
            console.warn('Invalid JWT: Missing payload part.');
            return null;
        }
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) {
        console.warn("Failed to decode JWT:", e);
        return null;
    }
}

export async function updateCartBadgeCount() {
    const cartNotificationBadge = document.querySelector('.notification-badge');
    if (!cartNotificationBadge) return;

    try {
        if (isAuthenticated()) {
            const cart = await apiRequest('/orders/cart', 'GET', null, true);
            if (cart && cart.order_items && Array.isArray(cart.order_items)) {
                const count = cart.order_items.reduce((sum, item) => sum + item.quantity, 0);
                cartNotificationBadge.textContent = count;
                cartNotificationBadge.style.display = count > 0 ? 'inline-block' : 'none';
            } else {
                cartNotificationBadge.textContent = '0';
                cartNotificationBadge.style.display = 'none';
            }
        } else {
             cartNotificationBadge.textContent = '0';
             cartNotificationBadge.style.display = 'none';
        }
    } catch (error) {
        console.warn('Could not update cart badge count:', error);
        cartNotificationBadge.textContent = '0';
        cartNotificationBadge.style.display = 'none';
    }
}

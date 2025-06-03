// BOPIS_Lou/frontend/js/pages/customer/orders-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, logout } from '../../auth.js';
import { updateCartBadgeCount } from '../../utils.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['customer'], 'login.html')) {
        return;
    }

    const orderHistoryContainerEl = document.getElementById('order-history-container');
    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('login.html');
        });
    }
    await updateCartBadgeCount();

    if (!orderHistoryContainerEl) {
        console.error("Order history container not found.");
        return;
    }

    try {
        // API: GET /orders (for customer, lists their own orders)
        const ordersData = await apiRequest('/orders?size=50&page=1', 'GET', null, true); // Fetch up to 50 orders
        if (ordersData && ordersData.items && ordersData.items.length > 0) {
            orderHistoryContainerEl.innerHTML = ''; // Clear loading message
            ordersData.items.forEach(order => {
                const orderDate = new Date(order.created_at).toLocaleDateString('ja-JP', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
                // Determine status display based on API doc enums
                let statusText = order.status;
                switch(order.status.toUpperCase()) {
                    case 'ORDER_CONFIRMED': statusText = '注文確定'; break;
                    case 'PROCESSING': statusText = '準備中'; break;
                    case 'READY_FOR_PICKUP': statusText = '準備完了'; break;
                    case 'COMPLETED': statusText = '受取済'; break;
                    case 'CANCELLED': statusText = 'キャンセル済'; break;
                    default: statusText = order.status;
                }

                orderHistoryContainerEl.innerHTML += `
                    <div class="card mb-4">
                        <div class="card-body">
                            <div class="flex justify-between items-center mb-2">
                                <h4 class="font-semibold text-lg">注文ID: ${order.id}</h4>
                                <span class="badge ${order.status === 'COMPLETED' ? 'badge-success' : 'badge-primary'}">${statusText}</span>
                            </div>
                            <p class="text-sm text-muted">注文日時: ${orderDate}</p>
                            <p class="text-lg font-medium mt-1">合計金額: ¥${Number(order.total_amount).toLocaleString()}</p>
                            ${order.pickup_token ? `<p class="text-sm mt-1">受取トークン: <strong class="text-primary">${order.pickup_token}</strong></p>` : ''}
                            <!-- Add link to a customer-facing order detail page if one exists -->
                            <!-- <a href="order-detail-view.html?orderId=${order.id}" class="btn btn-sm btn-outline mt-3">詳細を見る</a> -->
                        </div>
                    </div>
                `;
            });
        } else {
            orderHistoryContainerEl.innerHTML = '<p>注文履歴はありません。</p>';
        }
    } catch (error) {
        console.error('Failed to load order history:', error);
        orderHistoryContainerEl.innerHTML = '<p class="text-danger">注文履歴の読み込みに失敗しました。</p>';
    }
});

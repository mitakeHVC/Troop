// BOPIS_Lou/frontend/js/pages/picker/dashboard-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, logout, getAccessToken } from '../../auth.js';
import { decodeJWT, redirectTo } from '../../utils.js'; // Assuming redirectTo is needed

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['picker'], '../picker/login.html')) {
        return;
    }

    const token = getAccessToken();
    const payload = token ? decodeJWT(token) : null;

    // Target elements for dynamic content
    const pickerNameDisplay = document.getElementById('picker-name-display');
    const pickerTenantDisplay = document.getElementById('picker-tenant-display');
    const logoutButton = document.getElementById('picker-logout-button');
    const pendingCountSpan = document.getElementById('pending-count');
    const newOrdersTbody = document.getElementById('new-orders-tbody');
    // More elements will be targeted later: completedTodaySpan, processingOrdersTbody, etc.

    // Populate picker info (name and tenant might come from JWT or another API call)
    if (pickerNameDisplay && payload) {
        pickerNameDisplay.textContent = payload.name || payload.sub || 'Picker'; // Assuming name or sub is in JWT
    }
    if (pickerTenantDisplay && payload) {
       // Assuming tenant_name or tenant_id is in JWT. If only ID, might need mapping or another call.
        pickerTenantDisplay.textContent = payload.tenant_name || (payload.tenant_id ? `Tenant ID: ${payload.tenant_id}` : 'N/A');
    }

    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('../picker/login.html'); // Redirect to picker login
        });
    }

    async function fetchAndDisplayNewOrders() {
        if (!newOrdersTbody) {
            console.error('New orders table body not found');
            return;
        }
        newOrdersTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Loading new orders...</td></tr>';
        try {
            // API endpoint for picker's new orders. This is a placeholder.
            // The actual endpoint might depend on tenant_id from JWT or picker's profile.
            const newOrdersData = await apiRequest(`/picker/orders?status=NEW&sort=createdAt:desc`, 'GET', null, true);

            if (newOrdersData && newOrdersData.items && newOrdersData.items.length > 0) {
                newOrdersTbody.innerHTML = ''; // Clear loading message
                newOrdersData.items.forEach(order => {
                    const row = newOrdersTbody.insertRow();
                    row.innerHTML = `
                        <td>${order.order_number || order.id}</td>
                        <td>${order.pickup_slot || 'N/A'}</td>
                        <td>${order.item_count || 'N/A'} items</td>
                        <td>${new Date(order.created_at || Date.now()).toLocaleTimeString()}</td>
                        <td><a href="order-detail.html?id=${order.id}" class="btn btn-primary btn-sm">処理開始</a></td>
                    `;
                    // Highlight if needed, e.g. based on order.is_priority
                    if (order.is_priority) {
                       row.style.backgroundColor = '#fff3cd';
                    }
                });
                if (pendingCountSpan) {
                    pendingCountSpan.textContent = newOrdersData.total_count || newOrdersData.items.length;
                }
            } else {
                newOrdersTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No new orders at the moment.</td></tr>';
                if (pendingCountSpan) {
                    pendingCountSpan.textContent = '0';
                }
            }
        } catch (error) {
            console.error('Failed to fetch new orders:', error);
            newOrdersTbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:red;">Failed to load new orders.</td></tr>';
            if (pendingCountSpan) {
               pendingCountSpan.textContent = 'N/A';
            }
        }
    }

    // Initial load
    await fetchAndDisplayNewOrders();

    // TODO: Add listeners for sync button, status changes, etc.
    // TODO: Fetch and display other sections (processing, completed, stats)
});

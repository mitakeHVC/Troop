// BOPIS_Lou/frontend/js/pages/admin/dashboard-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, getAccessToken, logout } from '../../auth.js';
import { decodeJWT } from '../../utils.js';

async function loadDashboardStats(tenantIdForStats, userRoleForStats, todayOrdersCountEl, readyOrdersCountEl, completedOrdersCountEl, totalSalesEl) {
    if (todayOrdersCountEl) todayOrdersCountEl.textContent = '...';
    if (readyOrdersCountEl) readyOrdersCountEl.textContent = '...';
    if (completedOrdersCountEl) completedOrdersCountEl.textContent = '...';
    if (totalSalesEl) totalSalesEl.textContent = '...';

    if (!tenantIdForStats && userRoleForStats === 'admin') {
        // Admin needs a tenantId to fetch specific stats normally
        // Or the API /admin/stats must handle admin without tenant_id by using their assigned tenant
        console.warn("Admin user may need tenantId for specific stats or API needs to infer it.");
        // Display N/A or specific message if stats cannot be loaded for tenant admin without ID
        if (todayOrdersCountEl) todayOrdersCountEl.textContent = 'N/A';
        if (readyOrdersCountEl) readyOrdersCountEl.textContent = 'N/A';
        if (completedOrdersCountEl) completedOrdersCountEl.textContent = 'N/A';
        if (totalSalesEl) totalSalesEl.textContent = '¥N/A';
        return;
    }

    try {
        let statsEndpoint = '/admin/stats'; // General endpoint for super_admin
        if (tenantIdForStats && userRoleForStats === 'admin') {
            statsEndpoint = `/admin/stats?tenant_id=${tenantIdForStats}`; // Tenant-specific for admin
        }
        // For super_admin, the API might aggregate across all tenants or require no tenant_id param.
        // The current logic assumes /admin/stats handles both cases based on presence/absence of tenant_id or user role.

        const statsData = await apiRequest(statsEndpoint, 'GET', null, true);

        if (statsData) {
            if (todayOrdersCountEl) todayOrdersCountEl.textContent = statsData.today_orders_count !== undefined ? statsData.today_orders_count : 'N/A';
            if (readyOrdersCountEl) readyOrdersCountEl.textContent = statsData.ready_orders_count !== undefined ? statsData.ready_orders_count : 'N/A';
            if (completedOrdersCountEl) completedOrdersCountEl.textContent = statsData.completed_orders_count !== undefined ? statsData.completed_orders_count : 'N/A';
            if (totalSalesEl) totalSalesEl.textContent = statsData.total_sales_today !== undefined ? `¥${Number(statsData.total_sales_today).toLocaleString()}` : '¥N/A';
        }
    } catch (error) {
        console.error("Failed to load dashboard stats:", error);
        if (todayOrdersCountEl) todayOrdersCountEl.textContent = 'Error';
        if (readyOrdersCountEl) readyOrdersCountEl.textContent = 'Error';
        if (completedOrdersCountEl) completedOrdersCountEl.textContent = 'Error';
        if (totalSalesEl) totalSalesEl.textContent = '¥Error';
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['admin', 'super_admin'], 'login.html')) {
        return;
    }

    const token = getAccessToken();
    const payload = decodeJWT(token);
    let tenantId = payload ? payload.tenant_id : null;
    let userRole = payload ? payload.role : null;

    const adminTenantNameEl = document.getElementById('admin-tenant-name');
    const recentOrdersTbodyEl = document.getElementById('recent-orders-tbody');
    const stockAlertsUlEl = document.getElementById('stock-alerts-ul');
    const todayOrdersCountEl = document.getElementById('stats-today-orders-count');
    const readyOrdersCountEl = document.getElementById('stats-ready-orders-count');
    const completedOrdersCountEl = document.getElementById('stats-completed-orders-count');
    const totalSalesEl = document.getElementById('stats-total-sales');

    const logoutButton = document.getElementById('admin-logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('login.html');
        });
    }

    if (adminTenantNameEl) {
        if (tenantId) {
            try {
                const tenantInfo = await apiRequest(`/tenants/${tenantId}`, 'GET', null, true);
                adminTenantNameEl.textContent = tenantInfo.name || `テナントID: ${tenantId}`;
            } catch (e) {
                console.warn("Failed to fetch tenant details for admin:", e);
                adminTenantNameEl.textContent = `テナントID: ${tenantId}`;
            }
        } else if (userRole === 'super_admin') {
            adminTenantNameEl.textContent = "スーパー管理者 (全テナント)";
        } else {
            adminTenantNameEl.textContent = "テナント情報なし";
        }
    }

    if (!tenantId && userRole === 'admin') { // Changed from tenant_admin to admin
        console.error("Admin user does not have a tenant_id in token.");
        if(recentOrdersTbodyEl) recentOrdersTbodyEl.innerHTML = '<tr><td colspan="7" class="text-danger">エラー: テナント情報が不完全です。</td></tr>';
        if(stockAlertsUlEl) stockAlertsUlEl.innerHTML = '<li class="text-danger">エラー: テナント情報が不完全です。</li>';
        return;
    }

    if (recentOrdersTbodyEl) {
        if (tenantId || userRole === 'super_admin') {
            try {
                const ordersEndpoint = tenantId ? `/orders?tenant_id_filter=${tenantId}&size=5&page=1&sort_by=created_at&order=desc` : '/orders?size=5&page=1&sort_by=created_at&order=desc';
                const ordersData = await apiRequest(ordersEndpoint, 'GET', null, true);
                if (ordersData && ordersData.items && ordersData.items.length > 0) {
                    recentOrdersTbodyEl.innerHTML = '';
                    ordersData.items.forEach(order => {
                        const orderDate = new Date(order.created_at).toLocaleDateString('ja-JP', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
                        let itemQuantity = 0;
                        if (order.order_items && Array.isArray(order.order_items)) {
                            itemQuantity = order.order_items.reduce((sum, item) => sum + item.quantity, 0);
                        }
                        recentOrdersTbodyEl.innerHTML += `
                            <tr>
                                <td>${order.id}</td>
                                <td>${orderDate}</td>
                                <td>${order.pickup_slot_id || 'N/A'}</td>
                                <td>${itemQuantity}点</td>
                                <td>&yen;${Number(order.total_amount).toLocaleString()}</td>
                                <td><span class="badge badge-primary">${order.status}</span></td>
                                <td><a href="#" class="btn btn-sm btn-outline" data-order-id="${order.id}">詳細</a></td>
                            </tr>
                        `;
                    });
                } else {
                    recentOrdersTbodyEl.innerHTML = '<tr><td colspan="7" class="text-center">最近の注文はありません。</td></tr>';
                }
            } catch (error) {
                console.error("Failed to load recent orders:", error);
                recentOrdersTbodyEl.innerHTML = '<tr><td colspan="7" class="text-danger text-center">注文の読み込みに失敗。</td></tr>';
            }
        } else {
             recentOrdersTbodyEl.innerHTML = '<tr><td colspan="7" class="text-center">テナントを選択してください（スーパー管理者）。</td></tr>';
        }
    }

    if (stockAlertsUlEl) {
         if (tenantId || userRole === 'super_admin') {
            try {
                const productsEndpoint = tenantId ? `/products?tenantId=${tenantId}&stock_quantity_lt=10&size=5` : `/products?stock_quantity_lt=10&size=5`;
                const lowStockProducts = await apiRequest(productsEndpoint, 'GET', null, true);
                if (lowStockProducts && lowStockProducts.items && lowStockProducts.items.length > 0) {
                    stockAlertsUlEl.innerHTML = '';
                    lowStockProducts.items.forEach(product => {
                        stockAlertsUlEl.innerHTML += `
                            <li class="mb-1 p-2 border-b border-gray-200">
                                ${product.name} (SKU: ${product.sku}) - <strong>残り: ${product.stock_quantity}点</strong>
                            </li>
                        `;
                    });
                } else {
                    stockAlertsUlEl.innerHTML = '<li class="p-2">在庫アラートはありません。</li>';
                }
            } catch (error) {
                console.error("Failed to load stock alerts:", error);
                stockAlertsUlEl.innerHTML = '<li class="text-danger p-2">在庫アラートの読み込みに失敗。</li>';
            }
        } else {
             stockAlertsUlEl.innerHTML = '<li class="p-2">テナントを選択してください（スーパー管理者）。</li>';
        }
    }

    }

    // Load summary stats
    await loadDashboardStats(tenantId, userRole, todayOrdersCountEl, readyOrdersCountEl, completedOrdersCountEl, totalSalesEl);
});

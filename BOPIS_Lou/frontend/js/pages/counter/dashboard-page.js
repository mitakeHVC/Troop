// BOPIS_Lou/frontend/js/pages/counter/dashboard-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, getAccessToken, logout } from '../../auth.js';
import { decodeJWT } from '../../utils.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['counter'], 'login.html')) {
        return;
    }

    const token = getAccessToken();
    const payload = decodeJWT(token);
    let tenantId = payload ? payload.tenant_id : null;
    let counterUserId = payload ? payload.sub : null;

    // Header elements
    const counterNameEl = document.getElementById('counter-name');
    const counterTenantNameEl = document.getElementById('counter-tenant-name');
    const logoutButton = document.getElementById('counter-logout-button');

    // Page content elements
    const readyOrdersTbodyEl = document.getElementById('ready-orders-tbody');
    const lanesContainerEl = document.getElementById('lanes-status-container');
    // Stats placeholders
    const awaitingPickupStatEl = document.getElementById('stat-awaiting-pickup');
    const completedTodayCounterStatEl = document.getElementById('stat-completed-today-counter');


    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => { e.preventDefault(); logout('login.html'); });
    }

    // Display Counter Name & Tenant Name
    if (counterNameEl && counterUserId) {
        try {
            const userInfo = await apiRequest('/users/me', 'GET', null, true);
            counterNameEl.textContent = userInfo.username || 'カウンター様';
        } catch (e) { console.warn("Failed to fetch counter user info:", e); counterNameEl.textContent = 'カウンター様'; }
    }
    if (counterTenantNameEl && tenantId) {
        try {
            const tenantInfo = await apiRequest(`/tenants/${tenantId}`, 'GET', null, true);
            counterTenantNameEl.textContent = tenantInfo.name || `テナントID: ${tenantId}`;
        } catch (e) { counterTenantNameEl.textContent = `テナントID: ${tenantId}`; console.warn("Failed to fetch tenant name for counter:", e); }
    } else if (counterTenantNameEl) {
         counterTenantNameEl.textContent = "テナント情報なし";
    }

    if (!tenantId && payload && payload.role !== 'super_admin') { // Counter role must have tenant context
        if(readyOrdersTbodyEl) readyOrdersTbodyEl.innerHTML = '<tr><td colspan="5" class="text-danger text-center">エラー: テナント情報が不完全です。</td></tr>';
        if(lanesContainerEl) lanesContainerEl.innerHTML = '<p class="text-danger text-center">エラー: テナント情報が不完全です。</p>';
        return;
    }

    async function fetchAndRenderReadyOrders() {
        if (!readyOrdersTbodyEl) return;
        readyOrdersTbodyEl.innerHTML = '<tr><td colspan="6" class="text-center">準備完了注文を読み込み中...</td></tr>';
        try {
            // API: GET /counter/orders (or /orders?status=READY_FOR_PICKUP)
            // Assuming API is tenant-aware via JWT for counter role
            const ordersData = await apiRequest('/counter/orders?status=READY_FOR_PICKUP&size=50', 'GET', null, true);
            readyOrdersTbodyEl.innerHTML = '';
            if (ordersData && ordersData.items && ordersData.items.length > 0) {
                let count = 0;
                ordersData.items.forEach(order => {
                    count++;
                    const customerName = order.customer ? order.customer.username : 'N/A';
                    const itemCount = order.order_items ? order.order_items.reduce((sum, item) => sum + item.quantity, 0) : 'N/A';
                    readyOrdersTbodyEl.innerHTML += `
                        <tr>
                            <td><a href="verify.html?orderId=${order.id}&token=${order.pickup_token || ''}">${order.id}</a></td>
                            <td>${customerName}</td>
                            <td>${order.pickup_slot_id || '未指定'}</td>
                            <td>${itemCount}点</td>
                            <td>${order.assigned_lane_id || '未割当'}</td>
                            <td>
                                <a href="verify.html?orderId=${order.id}&token=${order.pickup_token || ''}" class="btn btn-sm btn-primary">認証・受渡</a>
                                <!-- Future: Assign to lane button -->
                            </td>
                        </tr>
                    `;
                });
                if(awaitingPickupStatEl) awaitingPickupStatEl.textContent = count;
            } else {
                if(awaitingPickupStatEl) awaitingPickupStatEl.textContent = "0";
                readyOrdersTbodyEl.innerHTML = '<tr><td colspan="6" class="text-center">現在、受渡準備完了の注文はありません。</td></tr>';
            }
        } catch (error) {
            console.error("Failed to load ready orders:", error);
            if(awaitingPickupStatEl) awaitingPickupStatEl.textContent = "エラー";
            readyOrdersTbodyEl.innerHTML = '<tr><td colspan="6" class="text-danger text-center">注文の読み込みに失敗。</td></tr>';
        }
    }

    async function fetchAndRenderLanes() {
        if (!lanesContainerEl) return;
        lanesContainerEl.innerHTML = '<p class="text-center">レーン状況を読み込み中...</p>';
        try {
            // API: GET /lanes/ (tenant-aware by JWT for counter)
            const lanesData = await apiRequest('/lanes/', 'GET', null, true);
            lanesContainerEl.innerHTML = '';
            if (lanesData && lanesData.items && lanesData.items.length > 0) {
                const list = document.createElement('ul');
                list.className = 'list-none p-0 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3';
                lanesData.items.forEach(lane => {
                    let statusClass = 'badge-secondary';
                    if (lane.status === 'OPEN') statusClass = 'badge-success';
                    else if (lane.status === 'BUSY') statusClass = 'badge-warning';
                    list.innerHTML += `
                        <li class="card p-3 text-sm">
                            <div class="font-semibold text-md mb-1">${lane.name}</div>
                            <div>ステータス: <span class="badge ${statusClass}">${lane.status}</span></div>
                            <div class="text-xs text-gray-600">現在対応中: ${lane.current_order_id || 'なし'}</div>
                        </li>
                    `;
                });
                lanesContainerEl.appendChild(list);
            } else {
                lanesContainerEl.innerHTML = '<p class="text-center">利用可能なレーンがありません。</p>';
            }
        } catch (error) {
            console.error("Failed to load lanes status:", error);
            lanesContainerEl.innerHTML = '<p class="text-danger text-center">レーン状況の読み込みに失敗。</p>';
        }
    }

    // Stats - placeholders
    if(completedTodayCounterStatEl) completedTodayCounterStatEl.textContent = "N/A";


    await fetchAndRenderReadyOrders();
    await fetchAndRenderLanes();

    // Auto-refresh data every 30 seconds (optional)
    // setInterval(async () => {
    // await fetchAndRenderReadyOrders();
    // await fetchAndRenderLanes();
    // }, 30000);
});

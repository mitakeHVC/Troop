// BOPIS_Lou/frontend/js/pages/counter/dashboard-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, logout, getAccessToken } from '../../auth.js';
import { decodeJWT, redirectTo } from '../../utils.js'; // redirectTo might be used by QR scan button

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['counter'], '../counter/login.html')) {
        return;
    }

    // Header elements
    const counterNameDisplay = document.getElementById('counter-name-display');
    const counterTenantDisplay = document.getElementById('counter-tenant-display');
    const counterLaneDisplay = document.getElementById('counter-lane-display');
    const logoutButton = document.getElementById('counter-logout-button');

    // Summary Stats
    const readyForPickupCountEl = document.getElementById('ready-for-pickup-count');
    const completedTodayCountEl = document.getElementById('completed-today-count');

    // Table for orders ready for pickup
    const readyOrdersTbody = document.getElementById('ready-orders-tbody');

    // QR Scan button (optional navigation)
    const qrScanButton = document.getElementById('qr-scan-nav-button');
    if(qrScanButton) {
        qrScanButton.addEventListener('click', () => {
            redirectTo('verify.html'); // Or wherever QR scanning is primarily handled
        });
    }

    // Data sync button
    const syncButton = document.getElementById('sync-button');
    if (syncButton) {
        syncButton.addEventListener('click', async () => {
            await loadDashboardData();
        });
    }


    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('../counter/login.html');
        });
    }

    const token = getAccessToken();
    const payload = token ? decodeJWT(token) : null;
    if (payload) {
        if (counterNameDisplay) counterNameDisplay.textContent = `ようこそ、${payload.name || payload.sub || '受付担当'}様`;
        if (counterTenantDisplay) counterTenantDisplay.textContent = `テナント: ${payload.tenant_name || (payload.tenant_id ? `ID ${payload.tenant_id}` : 'N/A')}`;
        if (counterLaneDisplay) counterLaneDisplay.textContent = `担当レーン: ${payload.assigned_lane || 'N/A'}`;
    }

    async function loadDashboardData() {
       // Fetch and display orders ready for pickup
       if (readyOrdersTbody) {
           readyOrdersTbody.innerHTML = '<tr><td colspan="6" class="text-center">読み込み中...</td></tr>';
       }
       try {
           // API: GET /counter/orders?status=READY_FOR_PICKUP&tenant_id={payload.tenant_id}
           // The tenant_id might be implicit based on user's session or needs to be passed.
           const params = new URLSearchParams({ status: 'READY_FOR_PICKUP' });
           if (payload && payload.tenant_id) {
               params.append('tenant_id', payload.tenant_id);
           }

           const ordersData = await apiRequest(`/counter/orders?${params.toString()}`, 'GET', null, true);
           if (readyOrdersTbody) {
               readyOrdersTbody.innerHTML = ''; // Clear loading
               if (ordersData && ordersData.items && ordersData.items.length > 0) {
                   ordersData.items.forEach(order => {
                       const row = readyOrdersTbody.insertRow();
                       row.innerHTML = `
                           <td>${order.id}</td>
                           <td>${order.pickup_slot?.display_time || 'N/A'}</td>
                           <td>${order.item_count_summary || 'N/A'}</td>
                           <td>${order.ready_at ? new Date(order.ready_at).toLocaleTimeString('ja-JP') : 'N/A'}</td>
                           <td>${order.assigned_lane || 'N/A'}</td>
                           <td>
                               <a href="verify.html?orderId=${order.id}" class="btn btn-primary btn-sm">受け取り処理</a>
                           </td>
                       `;
                   });
               } else {
                   readyOrdersTbody.innerHTML = '<tr><td colspan="6" class="text-center">現在、準備完了の注文はありません。</td></tr>';
               }
           }
           if (readyForPickupCountEl) {
                readyForPickupCountEl.textContent = (ordersData && ordersData.total_count !== undefined) ? ordersData.total_count : (ordersData?.items?.length || 0);
           }

       } catch (error) {
           console.error('Failed to load orders ready for pickup:', error);
           if (readyOrdersTbody) readyOrdersTbody.innerHTML = '<tr><td colspan="6" class="text-danger text-center">注文の読み込みに失敗しました。</td></tr>';
           if (readyForPickupCountEl) readyForPickupCountEl.textContent = 'N/A';
       }

       // Fetch and display other stats (e.g., completed today)
       try {
           // API: GET /counter/stats?tenant_id={payload.tenant_id}
           const statsParams = new URLSearchParams();
           if (payload && payload.tenant_id) {
               statsParams.append('tenant_id', payload.tenant_id);
           }
           const statsData = await apiRequest(`/counter/stats?${statsParams.toString()}`, 'GET', null, true);
           if (completedTodayCountEl && statsData) {
               completedTodayCountEl.textContent = statsData.completed_today_count || 0;
           }
       } catch (error) {
           console.error('Failed to load counter stats:', error);
           if (completedTodayCountEl) completedTodayCountEl.textContent = 'N/A';
       }
    }

    await loadDashboardData(); // Initial load
});

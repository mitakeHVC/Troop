// BOPIS_Lou/frontend/js/pages/customer/tenants-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, logout } from '../../auth.js';
import { updateCartBadgeCount, redirectTo } from '../../utils.js';

const SELECTED_TENANT_ID_KEY = 'selectedTenantId';
const SELECTED_TENANT_NAME_KEY = 'selectedTenantName';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['customer'], 'login.html')) {
        return;
    }

    const tenantListContainerEl = document.getElementById('tenant-list-container');
    const logoutButton = document.getElementById('logout-button');

    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            logout('login.html');
        });
    }
    await updateCartBadgeCount();

    if (!tenantListContainerEl) {
        console.error("Tenant list container not found.");
        return;
    }
    tenantListContainerEl.innerHTML = '<p>テナント情報を読み込み中です...</p>';

    try {
        const tenantsData = await apiRequest('/tenants', 'GET', null, true);

        if (tenantsData && tenantsData.items && tenantsData.items.length > 0) {
            tenantListContainerEl.innerHTML = '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"></div>';
            const gridContainer = tenantListContainerEl.querySelector('.grid');
            if (!gridContainer) {
                 tenantListContainerEl.innerHTML = '<p>表示エリアの準備に失敗しました。</p>'; return;
            }
            tenantsData.items.forEach(tenant => {
                const tenantCardHTML = `
                    <div class="card tenant-selection-card cursor-pointer hover:shadow-lg transition-shadow duration-200" data-tenant-id="${tenant.id}" data-tenant-name="${tenant.name}" style="cursor:pointer;">
                        <div class="card-body text-center p-4">
                            <img src="https://via.placeholder.com/80x80.png?text=${encodeURIComponent(tenant.name.substring(0,1))}" alt="${tenant.name}" class="mx-auto mb-3 rounded-full" style="width:80px; height:80px; object-fit:cover; border: 2px solid var(--gray-200);">
                            <h4 class="font-semibold text-lg mb-1">${tenant.name}</h4>
                            <p class="text-sm text-muted">ID: ${tenant.id}</p>
                        </div>
                    </div>
                `;
                gridContainer.insertAdjacentHTML('beforeend', tenantCardHTML);
            });

            document.querySelectorAll('.tenant-selection-card').forEach(card => {
                card.addEventListener('click', () => {
                    const tenantId = card.dataset.tenantId;
                    const tenantName = card.dataset.tenantName;
                    localStorage.setItem(SELECTED_TENANT_ID_KEY, tenantId);
                    localStorage.setItem(SELECTED_TENANT_NAME_KEY, tenantName);
                    redirectTo('products.html');
                });
            });

        } else {
            tenantListContainerEl.innerHTML = '<p>現在利用可能なテナントはありません。</p>';
        }
    } catch (error) {
        console.error('Failed to load tenant list:', error);
        tenantListContainerEl.innerHTML = '<p class="text-danger text-center">テナント一覧の読み込みに失敗しました。</p>';
    }
});

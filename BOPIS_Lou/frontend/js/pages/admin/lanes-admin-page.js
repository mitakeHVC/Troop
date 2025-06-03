// BOPIS_Lou/frontend/js/pages/admin/lanes-admin-page.js
'use strict';
import { apiRequest } from '../../api.js';
import { requireAuth, getAccessToken, logout } from '../../auth.js';
import { decodeJWT } from '../../utils.js';

document.addEventListener('DOMContentLoaded', async () => {
    if (!requireAuth(['admin', 'super_admin'], 'login.html')) {
        return;
    }

    const token = getAccessToken();
    const payload = decodeJWT(token);
    let tenantId = payload ? payload.tenant_id : null;
    const userRole = payload ? payload.role : null;

    const adminTenantNameEl = document.getElementById('admin-tenant-name');
    const lanesContainerEl = document.getElementById('lanes-container');
    const addLaneButton = document.getElementById('add-lane-button');
    const laneFormModal = document.getElementById('lane-form-modal');
    const laneForm = document.getElementById('lane-form');
    const laneFormTitle = document.getElementById('lane-form-title');
    const cancelFormButton = document.getElementById('cancel-lane-form-button');
    const formErrorMessageEl = document.getElementById('lane-form-error');
    const laneIdInput = document.getElementById('lane-id-input');

    const logoutButton = document.getElementById('admin-logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => { e.preventDefault(); logout('login.html'); });
    }

    if (adminTenantNameEl) {
        if (tenantId) {
            try {
                const tenantInfo = await apiRequest(`/tenants/${tenantId}`, 'GET', null, true);
                adminTenantNameEl.textContent = tenantInfo.name || `テナントID: ${tenantId}`;
            } catch (e) { adminTenantNameEl.textContent = `テナントID: ${tenantId}`; console.warn('Failed to fetch tenant name for admin header'); }
        } else if (userRole === 'super_admin') {
            adminTenantNameEl.textContent = "スーパー管理者 (テナント選択)";
            if(addLaneButton) addLaneButton.disabled = true;
            if(lanesContainerEl) lanesContainerEl.innerHTML = '<p class="text-center py-4">レーンを管理するテナントを選択してください。</p>';
            return;
        } else {
            adminTenantNameEl.textContent = "エラー: テナント情報なし";
            if(addLaneButton) addLaneButton.disabled = true;
            if(lanesContainerEl) lanesContainerEl.innerHTML = '<p class="text-center py-4 text-danger">管理者アカウントにテナント情報が関連付けられていません。</p>';
            return;
        }
    }
    if (!tenantId && userRole !== 'super_admin') {
         if(lanesContainerEl) lanesContainerEl.innerHTML = '<p class="text-center py-4 text-danger">テナントIDが見つかりません。</p>';
         if(addLaneButton) addLaneButton.disabled = true;
        return;
    }

    async function fetchAndRenderLanes() {
        if (!lanesContainerEl) return;
        lanesContainerEl.innerHTML = '<p class="text-center py-4">レーン情報を読み込み中...</p>';
        try {
            let endpoint = '/lanes/';
            // API Doc: GET /lanes/ - query params: status, target_tenant_id (for SA)
            // For tenant_admin, API should filter by the tenant_id from the JWT.
            if (userRole === 'super_admin' && tenantId) {
                endpoint = `/lanes/?target_tenant_id=${tenantId}`;
            }

            const lanesData = await apiRequest(endpoint, 'GET', null, true);

            lanesContainerEl.innerHTML = '';
            if (lanesData && lanesData.items && lanesData.items.length > 0) {
                const grid = document.createElement('div');
                grid.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6';
                lanesData.items.forEach(lane => {
                    let statusClass = 'badge-secondary';
                    if (lane.status === 'OPEN') statusClass = 'badge-success';
                    else if (lane.status === 'BUSY') statusClass = 'badge-warning';

                    grid.innerHTML += `
                        <div class="card lane-card shadow-md hover:shadow-lg transition-shadow" data-lane-id="${lane.id}">
                            <div class="card-body p-5">
                                <div class="flex justify-between items-start mb-3">
                                    <h4 class="font-semibold text-xl text-gray-800">${lane.name}</h4>
                                    <span class="badge ${statusClass}">${lane.status}</span>
                                </div>
                                <p class="text-sm text-gray-600 mb-1">現在の注文ID: ${lane.current_order_id || 'なし'}</p>
                                <p class="text-sm text-gray-600">担当スタッフ: <span id="lane-staff-${lane.id}">取得中...</span></p>
                                <div class="mt-4 flex gap-2 justify-end">
                                    <button class="btn btn-sm btn-outline edit-lane-btn" data-id="${lane.id}" data-name="${lane.name}" data-status="${lane.status}">編集</button>
                                    <button class="btn btn-sm btn-danger delete-lane-btn" data-id="${lane.id}" data-name="${lane.name}">削除</button>
                                </div>
                            </div>
                        </div>
                    `;
                    fetchLaneStaffAssignments(lane.id);
                });
                lanesContainerEl.appendChild(grid);
            } else {
                lanesContainerEl.innerHTML = '<p class="text-center py-4">登録されているレーンはありません。</p>';
            }
            addLaneActionListeners();
        } catch (error) {
            console.error("Failed to fetch lanes:", error);
            lanesContainerEl.innerHTML = '<p class="text-danger text-center py-4">レーン一覧の読み込みに失敗しました。</p>';
        }
    }

    async function fetchLaneStaffAssignments(laneIdForStaff) {
        const staffDisplayEl = document.getElementById(`lane-staff-${laneIdForStaff}`);
        if (!staffDisplayEl) return;
        try {
            const assignments = await apiRequest(`/lanes/${laneIdForStaff}/staff-assignments?active=true`, 'GET', null, true);
            if (assignments && assignments.length > 0) {
                const staffNames = assignments.map(a => a.user.username).join(', ');
                staffDisplayEl.textContent = staffNames || 'なし';
            } else {
                staffDisplayEl.textContent = 'なし';
            }
        } catch (e) {
            console.warn(`Could not fetch staff for lane ${laneIdForStaff}:`, e);
            staffDisplayEl.textContent = 'エラー';
        }
    }

    function openModalForCreateLane() {
        if (!laneFormModal || !laneForm || !laneFormTitle) return;
        laneForm.reset();
        if (laneIdInput) laneIdInput.value = '';
        if (laneFormTitle) laneFormTitle.textContent = '新しいレーンを追加';
        if (formErrorMessageEl) {formErrorMessageEl.textContent = ''; formErrorMessageEl.style.display = 'none';}
        laneFormModal.style.display = 'flex';
    }

    async function openModalForEditLane(laneIdVal, currentName, currentStatus) {
        if (!laneFormModal || !laneForm || !laneFormTitle) return;
        if (formErrorMessageEl) {formErrorMessageEl.textContent = ''; formErrorMessageEl.style.display = 'none';}

        laneForm.elements['name'].value = currentName;
        laneForm.elements['status'].value = currentStatus;
        if (laneIdInput) laneIdInput.value = laneIdVal;
        if (laneFormTitle) laneFormTitle.textContent = `レーン編集: ${currentName}`;
        laneFormModal.style.display = 'flex';
    }

    function closeLaneModal() {
        if (laneFormModal) laneFormModal.style.display = 'none';
    }

    if (addLaneButton) addLaneButton.addEventListener('click', openModalForCreateLane);
    if (cancelFormButton) cancelFormButton.addEventListener('click', closeLaneModal);
    if (laneFormModal) {
        laneFormModal.addEventListener('click', (event) => {
            if (event.target === laneFormModal) closeLaneModal();
        });
    }

    if (laneForm) {
        laneForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (formErrorMessageEl) {formErrorMessageEl.textContent = ''; formErrorMessageEl.style.display = 'none';}

            const formData = new FormData(laneForm);
            const laneName = formData.get('name');
            const laneStatus = formData.get('status');
            const currentLaneId = laneIdInput ? laneIdInput.value : null;

            if (!laneName) {
                if (formErrorMessageEl) {formErrorMessageEl.textContent = 'レーン名は必須です。'; formErrorMessageEl.style.display = 'block';}
                return;
            }

            const lanePayload = { name: laneName, status: laneStatus };

            try {
                if (currentLaneId) {
                    await apiRequest(`/lanes/${currentLaneId}`, 'PUT', lanePayload, true);
                } else {
                    await apiRequest('/lanes/', 'POST', lanePayload, true);
                }
                closeLaneModal();
                await fetchAndRenderLanes();
            } catch (error) {
                console.error("Failed to save lane:", error);
                if (formErrorMessageEl) {formErrorMessageEl.textContent = `保存エラー: ${error.message}`; formErrorMessageEl.style.display = 'block';}
            }
        });
    }

    function addLaneActionListeners() {
        document.querySelectorAll('.edit-lane-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                openModalForEditLane(e.target.dataset.id, e.target.dataset.name, e.target.dataset.status);
            });
        });
        document.querySelectorAll('.delete-lane-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                const laneIdVal = e.target.dataset.id;
                const name = e.target.dataset.name || 'このレーン';
                if (confirm(`${name} を削除しますか？この操作は元に戻せません。`)) {
                    try {
                        await apiRequest(`/lanes/${laneIdVal}`, 'DELETE', null, true);
                        await fetchAndRenderLanes();
                    } catch (error) {
                        console.error("Failed to delete lane:", error);
                        alert(`削除エラー: ${error.message}`);
                    }
                }
            });
        });
    }

    await fetchAndRenderLanes();
});

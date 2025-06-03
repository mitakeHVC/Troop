// BOPIS_Lou/frontend/js/pages/admin/staff-admin-page.js
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
    const staffTableBodyEl = document.getElementById('admin-staff-table-body');
    const addStaffButton = document.getElementById('add-staff-button');
    const staffFormModal = document.getElementById('staff-form-modal');
    const staffForm = document.getElementById('staff-form');
    const staffFormTitle = document.getElementById('staff-form-title');
    const cancelFormButton = document.getElementById('cancel-staff-form-button');
    const formErrorMessageEl = document.getElementById('staff-form-error');
    const staffIdInput = document.getElementById('staff-id-input'); // For editing

    // Setup logout button
    const logoutButton = document.getElementById('admin-logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => { e.preventDefault(); logout('login.html'); });
    }

    // Display Tenant Name & Check Tenant Context
    if (adminTenantNameEl) {
        if (tenantId) {
            try {
                const tenantInfo = await apiRequest(`/tenants/${tenantId}`, 'GET', null, true);
                adminTenantNameEl.textContent = tenantInfo.name || `テナントID: ${tenantId}`;
            } catch (e) { adminTenantNameEl.textContent = `テナントID: ${tenantId}`; }
        } else if (userRole === 'super_admin') {
            adminTenantNameEl.textContent = "スーパー管理者 (モード選択)"; // SA needs to pick a tenant
            if(addStaffButton) addStaffButton.disabled = true;
             if(staffTableBodyEl) staffTableBodyEl.innerHTML = '<tr><td colspan="6" class="text-center py-4">スタッフを管理するテナントを選択してください。</td></tr>';
            return; // Stop if SA and no tenant selected
        } else { // tenant_admin must have tenantId
            adminTenantNameEl.textContent = "エラー: テナント情報なし";
            if(addStaffButton) addStaffButton.disabled = true;
            if(staffTableBodyEl) staffTableBodyEl.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-danger">管理者アカウントにテナント情報が関連付けられていません。</td></tr>';
            return;
        }
    }
    if (!tenantId) { // Should be caught above for non-SA roles
         if(staffTableBodyEl) staffTableBodyEl.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-danger">テナントIDが見つかりません。</td></tr>';
         if(addStaffButton) addStaffButton.disabled = true;
        return;
    }


    async function fetchAndRenderStaff() {
        if (!staffTableBodyEl) return;
        try {
            // API: GET /tenants/{tenant_id}/staff
            const staffData = await apiRequest(`/tenants/${tenantId}/staff`, 'GET', null, true);
            staffTableBodyEl.innerHTML = '';
            if (staffData && staffData.items && staffData.items.length > 0) {
                staffData.items.forEach(s => {
                    staffTableBodyEl.innerHTML += `
                        <tr data-staff-id="${s.id}">
                            <td>${s.username}</td>
                            <td>${s.email}</td>
                            <td>${s.role}</td> <!-- API returns full role string e.g. "picker", "counter" -->
                            <td><span class="badge ${s.is_active ? 'badge-success' : 'badge-secondary'}">${s.is_active ? '有効' : '無効'}</span></td>
                            <td class="text-sm">${new Date(s.created_at).toLocaleDateString('ja-JP')}</td>
                            <td>
                                <button class="btn btn-sm btn-outline edit-staff-btn mr-1" data-id="${s.id}">編集</button>
                                <button class="btn btn-sm ${s.is_active ? 'btn-warning' : 'btn-success'} toggle-active-btn" data-id="${s.id}" data-active="${s.is_active}">
                                    ${s.is_active ? '無効化' : '有効化'}
                                </button>
                            </td>
                        </tr>
                    `;
                });
            } else {
                staffTableBodyEl.innerHTML = '<tr><td colspan="6" class="text-center py-4">スタッフが登録されていません。</td></tr>';
            }
            addStaffTableButtonListeners();
        } catch (error) {
            console.error("Failed to fetch staff:", error);
            staffTableBodyEl.innerHTML = '<tr><td colspan="6" class="text-danger text-center py-4">スタッフ一覧の読み込みに失敗。</td></tr>';
        }
    }

    function openModalForCreateStaff() {
        if (!staffFormModal || !staffForm || !staffFormTitle) return;
        staffForm.reset();
        if (staffIdInput) staffIdInput.value = ''; // Clear staff ID for create mode
        if (staffFormTitle) staffFormTitle.textContent = '新しいスタッフを追加';
        // Show password field for create
        const passwordGroup = document.getElementById('staff-password-group');
        if(passwordGroup) passwordGroup.style.display = 'block';
        const passwordInput = staffForm.elements['password'];
        if(passwordInput) passwordInput.required = true;

        if (formErrorMessageEl) formErrorMessageEl.textContent = ''; formErrorMessageEl.style.display = 'none';
        staffFormModal.style.display = 'flex';
    }

    async function openModalForEditStaff(staffUserId) {
        if (!staffFormModal || !staffForm || !staffFormTitle) return;
        if (formErrorMessageEl) formErrorMessageEl.textContent = ''; formErrorMessageEl.style.display = 'none';
        try {
            // API: GET /tenants/{tenant_id}/staff/{user_id}
            const staffUser = await apiRequest(`/tenants/${tenantId}/staff/${staffUserId}`, 'GET', null, true);

            staffForm.elements['username'].value = staffUser.username;
            staffForm.elements['email'].value = staffUser.email;
            staffForm.elements['assigned_role'].value = staffUser.role; // API returns 'role', StaffCreate model uses 'assigned_role'
            staffForm.elements['is_active'].checked = staffUser.is_active;

            if (staffIdInput) staffIdInput.value = staffUser.id;

            // Hide password field for edit, or make it optional for password change
            const passwordGroup = document.getElementById('staff-password-group');
            if(passwordGroup) passwordGroup.style.display = 'none'; // Hide for normal edit
            const passwordInput = staffForm.elements['password'];
            if(passwordInput) passwordInput.required = false;


            if (staffFormTitle) staffFormTitle.textContent = `スタッフ編集: ${staffUser.username}`;
            staffFormModal.style.display = 'flex';
        } catch (error) {
            console.error("Failed to fetch staff for editing:", error);
            alert("スタッフ情報の取得に失敗しました。");
        }
    }

    function closeStaffModal() {
        if (staffFormModal) staffFormModal.style.display = 'none';
    }

    if (addStaffButton) addStaffButton.addEventListener('click', openModalForCreateStaff);
    if (cancelFormButton) cancelFormButton.addEventListener('click', closeStaffModal);
    if (staffFormModal) {
        staffFormModal.addEventListener('click', (event) => {
            if (event.target === staffFormModal) closeStaffModal();
        });
    }

    if (staffForm) {
        staffForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (formErrorMessageEl) {formErrorMessageEl.textContent = ''; formErrorMessageEl.style.display = 'none';}

            const formData = new FormData(staffForm);
            const sId = staffIdInput ? staffIdInput.value : null;

            const staffPayload = {
                username: formData.get('username'),
                email: formData.get('email'),
                // For create, role is 'assigned_role'. For update, it's 'assigned_role'
                // The API doc StaffCreate takes 'username, email, password, role'.
                // The API doc StaffUpdate takes 'is_active, assigned_role'.
                // The GET /staff returns 'role'.
                // Let's align form 'assigned_role' with create/update models.
                assigned_role: formData.get('assigned_role'), // This is from the select
            };

            try {
                if (sId) { // Update existing staff
                    // API: PUT /tenants/{tenant_id}/staff/{user_id}
                    staffPayload.is_active = formData.get('is_active') === 'on'; // Checkbox value
                    // Password change is not handled in this form for PUT.
                    await apiRequest(`/tenants/${tenantId}/staff/${sId}`, 'PUT', staffPayload, true);
                } else { // Create new staff
                    // API: POST /tenants/{tenant_id}/staff
                    // UserCreate model (used by StaffCreate) needs: username, email, password, role, tenant_id
                    // 'role' in UserCreate should be the actual role like 'picker', not 'assigned_role'
                    staffPayload.password = formData.get('password');
                    staffPayload.role = formData.get('assigned_role'); // Map form's assigned_role to UserCreate's role
                    delete staffPayload.assigned_role; // Clean up if not needed directly by UserCreate

                    if (!staffPayload.password) {
                       if (formErrorMessageEl) {formErrorMessageEl.textContent = '新規作成時はパスワードが必須です。'; formErrorMessageEl.style.display = 'block';}
                       return;
                    }
                    await apiRequest(`/tenants/${tenantId}/staff`, 'POST', staffPayload, true);
                }
                closeStaffModal();
                await fetchAndRenderStaff();
            } catch (error) {
                console.error("Failed to save staff:", error);
                 if (formErrorMessageEl) {formErrorMessageEl.textContent = `保存エラー: ${error.message}`; formErrorMessageEl.style.display = 'block';}
            }
        });
    }

    function addStaffTableButtonListeners() {
        document.querySelectorAll('.edit-staff-btn').forEach(button => {
            button.addEventListener('click', (e) => openModalForEditStaff(e.target.dataset.id));
        });
        document.querySelectorAll('.toggle-active-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                const staffUserId = e.target.dataset.id;
                const currentIsActive = e.target.dataset.active === 'true';
                const action = currentIsActive ? 'deactivate' : 'activate';
                const confirmMessage = `${currentIsActive ? '無効化' : '有効化'}しますか？`;

                if (confirm(confirmMessage)) {
                    try {
                        // API: PATCH /tenants/{tenant_id}/staff/{user_id}/activate or /deactivate
                        await apiRequest(`/tenants/${tenantId}/staff/${staffUserId}/${action}`, 'PATCH', null, true);
                        await fetchAndRenderStaff();
                    } catch (error) {
                        console.error(`Failed to ${action} staff:`, error);
                        alert(`スタッフの${action}に失敗しました: ${error.message}`);
                    }
                }
            });
        });
    }

    await fetchAndRenderStaff(); // Initial fetch
});

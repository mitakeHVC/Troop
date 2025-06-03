// BOPIS_Lou/frontend/js/pages/admin/products-admin-page.js
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
    const productsTableBodyEl = document.getElementById('admin-products-table-body');
    const addProductButton = document.getElementById('add-product-button');
    const productFormModal = document.getElementById('product-form-modal');
    const productForm = document.getElementById('product-form');
    const productFormTitle = document.getElementById('product-form-title');
    const cancelFormButton = document.getElementById('cancel-form-button');
    const formErrorMessageEl = document.getElementById('product-form-error');

    // Hidden fields for ID and Version (for editing)
    const productIdInput = document.getElementById('product-id-input');
    const productVersionInput = document.getElementById('product-version-input');


    // Setup logout button
    const logoutButton = document.getElementById('admin-logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => { e.preventDefault(); logout('login.html'); });
    }

    // Display Tenant Name
    if (adminTenantNameEl) {
        if (tenantId) {
            try {
                const tenantInfo = await apiRequest(`/tenants/${tenantId}`, 'GET', null, true);
                adminTenantNameEl.textContent = tenantInfo.name || `テナントID: ${tenantId}`;
            } catch (e) { adminTenantNameEl.textContent = `テナントID: ${tenantId}`; }
        } else if (userRole === 'super_admin') {
            adminTenantNameEl.textContent = "スーパー管理者 (全テナント)";
            // Super Admins might need a tenant selector to manage products.
            // For now, disable product management if no tenantId for super_admin.
            if (addProductButton) addProductButton.disabled = true;
            if (productsTableBodyEl) productsTableBodyEl.innerHTML = '<tr><td colspan="7">スーパー管理者はテナントを選択して商品を管理してください。</td></tr>';
            // return; // Or allow viewing all products if API supports it without tenantId filter for SA
        } else {
            adminTenantNameEl.textContent = "テナント情報なし";
            if (addProductButton) addProductButton.disabled = true;
        }
    }

    // Super admin without tenantId cannot manage specific tenant products here
    if (userRole === 'super_admin' && !tenantId) {
        if (productsTableBodyEl) productsTableBodyEl.innerHTML = '<tr><td colspan="7" class="text-center py-4">スーパー管理者は特定のテナントを選択して商品を管理してください。</td></tr>';
         if (addProductButton) addProductButton.style.display = 'none';
        // return; // Stop further execution if SA and no tenant context
    }


    async function fetchAndRenderProducts() {
        if (!productsTableBodyEl) return;
        if (!tenantId && userRole === 'admin') { // tenant_admin MUST have tenantId - changed from tenant_admin to admin
             productsTableBodyEl.innerHTML = '<tr><td colspan="7" class="text-danger text-center py-4">エラー: 管理者アカウントにテナント情報が紐付いていません。</td></tr>';
             return;
        }

        let apiEndpoint = '/products?size=100'; // Default for super_admin to see all (if API allows)
        if (tenantId) { // If tenantId is present (either admin or SA viewing specific tenant)
            apiEndpoint = `/products?tenantId=${tenantId}&size=100`;
        } else if (userRole !== 'super_admin') { // Non-SA must have tenantId
             productsTableBodyEl.innerHTML = '<tr><td colspan="7" class="text-danger text-center py-4">テナントIDが必要です。</td></tr>';
             return;
        }


        try {
            const productsData = await apiRequest(apiEndpoint, 'GET', null, true);
            productsTableBodyEl.innerHTML = ''; // Clear existing rows
            if (productsData && productsData.items && productsData.items.length > 0) {
                productsData.items.forEach(p => {
                    const lastSync = p.last_synced_at ? new Date(p.last_synced_at).toLocaleString('ja-JP') : 'N/A';
                    productsTableBodyEl.innerHTML += `
                        <tr data-product-id="${p.id}">
                            <td>${p.sku}</td>
                            <td>${p.name}</td>
                            <td>&yen;${Number(p.price).toLocaleString()}</td>
                            <td>${p.stock_quantity}</td>
                            <td class="text-sm">${lastSync}</td>
                            <td>${p.version}</td>
                            <td>
                                <button class="btn btn-sm btn-outline edit-product-btn mr-1" data-id="${p.id}">編集</button>
                                <button class="btn btn-sm btn-danger delete-product-btn" data-id="${p.id}" data-name="${p.name}">削除</button>
                            </td>
                        </tr>
                    `;
                });
            } else {
                productsTableBodyEl.innerHTML = '<tr><td colspan="7" class="text-center py-4">商品が登録されていません。</td></tr>';
            }
            addTableButtonListeners();
        } catch (error) {
            console.error("Failed to fetch products:", error);
            productsTableBodyEl.innerHTML = '<tr><td colspan="7" class="text-danger text-center py-4">商品リストの読み込みに失敗。</td></tr>';
        }
    }

    function openModalForCreate() {
        if (!productFormModal || !productForm || !productFormTitle) return;
        productForm.reset();
        if (productIdInput) productIdInput.value = '';
        if (productVersionInput) productVersionInput.value = '';
        if (productFormTitle) productFormTitle.textContent = '新しい商品を追加';
        if (formErrorMessageEl) formErrorMessageEl.textContent = ''; formErrorMessageEl.style.display = 'none';
        productFormModal.style.display = 'flex';
    }

    async function openModalForEdit(productId) {
        if (!productFormModal || !productForm || !productFormTitle) return;
        if (formErrorMessageEl) formErrorMessageEl.textContent = ''; formErrorMessageEl.style.display = 'none';
        try {
            // Fetch full product details for editing, include tenantId if needed by API for specific product fetch by admin
            const product = await apiRequest(`/products/${productId}${tenantId ? '?tenantId='+tenantId : ''}`, 'GET', null, true);
            productForm.elements['name'].value = product.name;
            productForm.elements['sku'].value = product.sku;
            productForm.elements['price'].value = product.price;
            productForm.elements['stock_quantity'].value = product.stock_quantity;
            productForm.elements['description'].value = product.description || '';
            productForm.elements['image_url'].value = product.image_url || '';
            if (productIdInput) productIdInput.value = product.id;
            if (productVersionInput) productVersionInput.value = product.version; // Important for optimistic locking

            if (productFormTitle) productFormTitle.textContent = `商品編集: ${product.name}`;
            productFormModal.style.display = 'flex';
        } catch (error) {
            console.error("Failed to fetch product for editing:", error);
            alert("商品データの取得に失敗しました。");
        }
    }

    function closeModal() {
        if (productFormModal) productFormModal.style.display = 'none';
    }

    if (addProductButton) {
         addProductButton.addEventListener('click', openModalForCreate);
         // Disable if super_admin and no tenant selected (visual cue)
         if (userRole === 'super_admin' && !tenantId) {
            addProductButton.classList.add('opacity-50', 'cursor-not-allowed');
            addProductButton.disabled = true;
            addProductButton.title = "商品を管理するテナントを選択してください。";
         }
    }
    if (cancelFormButton) cancelFormButton.addEventListener('click', closeModal);
    if (productFormModal) { // Close modal if clicking outside the form content
        productFormModal.addEventListener('click', (event) => {
            if (event.target === productFormModal) closeModal();
        });
    }


    if (productForm) {
        productForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (formErrorMessageEl) {formErrorMessageEl.textContent = ''; formErrorMessageEl.style.display = 'none';}

            const formData = new FormData(productForm);
            const data = Object.fromEntries(formData.entries());
            // Convert to correct types
            data.price = parseFloat(data.price);
            data.stock_quantity = parseInt(data.stock_quantity);
            if (productIdInput && productIdInput.value) data.id = parseInt(productIdInput.value);
            if (productVersionInput && productVersionInput.value) data.version = parseInt(productVersionInput.value);


            // Basic validation
            if (!data.name || !data.sku || isNaN(data.price) || isNaN(data.stock_quantity)) {
                 if (formErrorMessageEl) {
                    formErrorMessageEl.textContent = '必須項目（名前, SKU, 価格, 在庫数）を正しく入力してください。';
                    formErrorMessageEl.style.display = 'block';
                }
                return;
            }


            try {
                if (data.id) { // Update existing product
                    // PUT /products/{product_id}
                    // The API doc says ProductUpdateWithVersion takes version.
                    // Ensure your ProductUpdate schema on backend expects 'id' or it's just in URL.
                    // For now, assuming ID is not in body for PUT, version is.
                    const updatePayload = {
                        name: data.name,
                        description: data.description,
                        price: data.price,
                        stock_quantity: data.stock_quantity,
                        image_url: data.image_url,
                        version: data.version // For optimistic locking
                    };
                    await apiRequest(`/products/${data.id}`, 'PUT', updatePayload, true);
                } else { // Create new product
                    // POST /products
                    // tenant_id is derived by backend from admin's token
                     const createPayload = {
                        name: data.name,
                        description: data.description,
                        price: data.price,
                        sku: data.sku,
                        stock_quantity: data.stock_quantity,
                        image_url: data.image_url
                    };
                    await apiRequest('/products', 'POST', createPayload, true);
                }
                closeModal();
                await fetchAndRenderProducts();
            } catch (error) {
                console.error("Failed to save product:", error);
                if (formErrorMessageEl) {
                    formErrorMessageEl.textContent = `保存エラー: ${error.message}`;
                    formErrorMessageEl.style.display = 'block';
                }
            }
        });
    }

    function addTableButtonListeners() {
        document.querySelectorAll('.edit-product-btn').forEach(button => {
            button.addEventListener('click', (e) => openModalForEdit(e.target.dataset.id));
        });
        document.querySelectorAll('.delete-product-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                const productId = e.target.dataset.id;
                const productName = e.target.dataset.name || 'この商品';
                if (confirm(`${productName} を削除しますか？この操作は元に戻せません。`)) {
                    try {
                        await apiRequest(`/products/${productId}`, 'DELETE', null, true);
                        await fetchAndRenderProducts();
                    } catch (error) {
                        console.error("Failed to delete product:", error);
                        alert(`削除エラー: ${error.message}`);
                    }
                }
            });
        });
    }

    // Initial fetch, but only if tenant context is clear or it's SA (who might see all or need selection)
    if ((tenantId && (userRole === 'admin' || userRole === 'super_admin')) || (userRole === 'super_admin' && !tenantId /* SA might view all products initially */) ) { // Corrected tenant_admin to admin
         await fetchAndRenderProducts();
    } else if (userRole !== 'super_admin' && !tenantId){
        // Handled by specific error messages above
    }
});

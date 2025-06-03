// BOPIS_Lou/frontend/js/pages/counter/login-page.js
'use strict';
import { login, isAuthenticated, getUserRole } from '../../auth.js';
import { redirectTo } from '../../utils.js';

document.addEventListener('DOMContentLoaded', () => {
    if (isAuthenticated()) {
        const role = getUserRole();
        if (role === 'counter') {
            redirectTo('dashboard.html'); // Relative to /mockups/counter/
            return;
        }
        // Optional: Redirect other authenticated roles to a default page or their dashboard
        // redirectTo('../customer/products.html'); // Example fallback
    }

    const loginForm = document.getElementById('counter-login-form');
    const errorMessageElement = document.getElementById('login-error');

    if (loginForm) {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (errorMessageElement) errorMessageElement.textContent = '';

            const staffIdInput = document.getElementById('staff-id');
            const passwordInput = document.getElementById('password');
            // const tenantSelect = document.getElementById('tenant');
            // const laneSelect = document.getElementById('lane');

            if (!staffIdInput || !passwordInput) {
                console.error('Staff ID or password input fields not found.');
                if (errorMessageElement) errorMessageElement.textContent = 'Form fields are misconfigured.';
                return;
            }

            const staffId = staffIdInput.value;
            const password = passwordInput.value;
            // const tenantId = tenantSelect.value;
            // const laneId = laneSelect.value;

            if (!staffId || !password) {
                if (errorMessageElement) errorMessageElement.textContent = 'スタッフIDとパスワードを入力してください。';
                return;
            }
            // Add validation for tenantId and laneId if they become mandatory for login itself.
            // For now, login relies on staffId/password, and tenant/lane might be part of user's profile or set post-login.

            try {
                // The login function in auth.js handles redirection based on role.
                // It will redirect to '../counter/dashboard.html' if role is 'counter'.
                await login(staffId, password);
            } catch (error) {
                console.error('Counter login attempt failed:', error);
                if (errorMessageElement) {
                    errorMessageElement.textContent = error.message.includes('API Error: 401') ? '認証情報が無効です。再試行してください。' : (error.message || 'ログインに失敗しました。認証情報を確認してください。');
                }
            }
        });
    } else {
        console.error('Counter login form not found.');
        if (errorMessageElement) errorMessageElement.textContent = 'ログインフォームが見つかりません。';
    }
});

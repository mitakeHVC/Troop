// BOPIS_Lou/frontend/js/pages/customer/login-page.js
'use strict';
import { login, isAuthenticated, getUserRole } from '../../auth.js';
import { redirectTo } from '../../utils.js';

document.addEventListener('DOMContentLoaded', () => {
    if (isAuthenticated()) {
        const role = getUserRole();
        console.log('User already authenticated with role:', role);
        if (role === 'admin' || role === 'super_admin') {
            redirectTo('../admin/dashboard.html');
        } else if (role === 'picker') {
            redirectTo('../picker/dashboard.html');
        } else if (role === 'counter') {
            redirectTo('../counter/dashboard.html');
        } else {
            redirectTo('products.html');
        }
        return;
    }

    const loginForm = document.getElementById('customer-login-form');
    const errorMessageElement = document.getElementById('login-error');

    if (loginForm) {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (errorMessageElement) errorMessageElement.textContent = '';

            const usernameInput = loginForm.querySelector('input[name="username"]');
            const passwordInput = loginForm.querySelector('input[name="password"]');

            if (!usernameInput || !passwordInput) {
                console.error('Username or password input fields not found or missing name attributes.');
                if (errorMessageElement) errorMessageElement.textContent = 'Form fields are misconfigured.';
                return;
            }

            const username = usernameInput.value;
            const password = passwordInput.value;

            if (!username || !password) {
                if (errorMessageElement) errorMessageElement.textContent = 'Please enter both email and password.';
                return;
            }

            try {
                await login(username, password);
            } catch (error) {
                console.error('Login attempt failed on page:', error);
                if (errorMessageElement) {
                    errorMessageElement.textContent = error.message.includes('API Error: 401') ? 'Invalid credentials. Please try again.' : (error.message || 'Login failed. Please check credentials.');
                }
            }
        });
    }
});

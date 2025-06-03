// BOPIS_Lou/frontend/js/pages/picker/login-page.js
'use strict';
import { login, isAuthenticated, getUserRole } from '../../auth.js';
import { redirectTo } from '../../utils.js';

document.addEventListener('DOMContentLoaded', () => {
    if (isAuthenticated()) {
        const role = getUserRole();
        // If already a picker, go to picker dashboard.
        // Other roles might go to their respective dashboards or a default page.
        if (role === 'picker') {
            redirectTo('dashboard.html'); // Assumes current path is /mockups/picker/
            return;
        }
        // Handle other roles if necessary, or redirect to a generic page or customer products page
        // For simplicity, if authenticated and not a picker, could redirect to customer products or tenant selection
        // This logic might need refinement based on overall app flow for users with multiple roles or unexpected roles.
        // redirectTo('../customer/products.html'); // Example fallback
        // return;
    }

    const loginForm = document.getElementById('picker-login-form');
    const errorMessageElement = document.getElementById('login-error');

    if (loginForm) {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (errorMessageElement) errorMessageElement.textContent = '';

            const staffIdInput = document.getElementById('staff-id');
            const passwordInput = document.getElementById('password');
            // const tenantInput = document.getElementById('tenant'); // Tenant might be needed later

            if (!staffIdInput || !passwordInput) {
                console.error('Staff ID or password input fields not found.');
                if (errorMessageElement) errorMessageElement.textContent = 'Form fields are misconfigured.';
                return;
            }

            const staffId = staffIdInput.value;
            const password = passwordInput.value;
            // const tenantId = tenantInput.value;

            if (!staffId || !password) {
                if (errorMessageElement) errorMessageElement.textContent = 'Please enter Staff ID and Password.';
                return;
            }

            // Optional: check if tenantId is selected if it were to be used for login
            // if (!tenantId) {
            //     if (errorMessageElement) errorMessageElement.textContent = 'Please select a tenant.';
            //     return;
            // }

            try {
                // Using the generic login function. Backend /auth/login must support staffId as username.
                // The login function in auth.js handles redirection.
                await login(staffId, password);
            } catch (error) {
                console.error('Picker login attempt failed:', error);
                if (errorMessageElement) {
                    errorMessageElement.textContent = error.message.includes('API Error: 401') ? 'Invalid credentials. Please try again.' : (error.message || 'Login failed. Please check credentials.');
                }
            }
        });
    } else {
        console.error('Picker login form not found.');
        if (errorMessageElement) errorMessageElement.textContent = 'Login form not found on page.';
    }
});

// BOPIS_Lou/frontend/js/api.js
'use strict';

const API_BASE_URL = ''; // Assuming API is at the same origin, paths like /auth/login

export async function apiRequest(endpoint, method = 'GET', body = null, requiresAuth = true) {
    const headers = new Headers();
    if (requiresAuth) {
        const token = localStorage.getItem('accessToken');
        if (token) {
            headers.append('Authorization', `Bearer ${token}`);
        } else {
            console.warn('Attempting to make authenticated request without token.');
        }
    }

    if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
        headers.append('Content-Type', 'application/json');
    }

    const config = {
        method: method,
        headers: headers,
        body: body ? JSON.stringify(body) : null
    };

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
            } catch (e) {
                errorData = { message: response.statusText };
            }

            if (response.status === 401 && requiresAuth) {
                console.error('API request unauthorized. Token might be expired or invalid.');
                // Caller should handle this, possibly by redirecting to login.
            }
            throw new Error(`API Error: ${response.status} ${errorData.detail || errorData.message || response.statusText}`);
        }
        if (response.status === 204) { // No Content
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('API Request Failed:', endpoint, error);
        throw error;
    }
}

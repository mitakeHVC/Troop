// BOPIS_Lou/frontend/js/auth.js
'use strict';

import { apiRequest } from './api.js';
import { decodeJWT, redirectTo } from './utils.js';

const ACCESS_TOKEN_KEY = 'accessToken';
const REFRESH_TOKEN_KEY = 'refreshToken';

export function saveTokens(accessToken, refreshToken) {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    if (refreshToken) {
        localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    }
}

export function getAccessToken() {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function clearTokens() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export async function login(username, password) {
    try {
        const data = await apiRequest('/auth/login', 'POST', { username, password }, false);
        if (data && data.access_token) {
            saveTokens(data.access_token, data.refresh_token);
            const role = getUserRole();
            if (role === 'admin' || role === 'super_admin') {
                redirectTo('../admin/dashboard.html');
            } else if (role === 'picker') {
                redirectTo('../picker/dashboard.html');
            } else if (role === 'counter') {
                redirectTo('../counter/dashboard.html');
            } else {
                redirectTo('products.html');
            }
            return data;
        } else {
            throw new Error('Login failed: No token received.');
        }
    } catch (error) {
        console.error('Login error:', error);
        clearTokens();
        throw error;
    }
}

export async function refreshToken() {
    const currentRefreshToken = getRefreshToken();
    if (!currentRefreshToken) {
        logout('../customer/login.html');
        throw new Error('No refresh token available for renewal.');
    }
    try {
        const data = await apiRequest('/auth/refresh-token', 'POST', { refresh_token: currentRefreshToken }, false);
        if (data && data.access_token) {
            saveTokens(data.access_token, data.refresh_token);
            return data.access_token;
        } else {
            logout('../customer/login.html');
            throw new Error('Refresh token failed: No new token received.');
        }
    } catch (error) {
        console.error('Token refresh error:', error);
        logout('../customer/login.html');
        throw error;
    }
}

export function logout(redirectToPage = 'login.html') {
    clearTokens();
    redirectTo(redirectToPage);
}

export function isAuthenticated() {
    return !!getAccessToken();
}

export function getUserRole() {
    const token = getAccessToken();
    if (!token) return null;
    const payload = decodeJWT(token);
    return payload ? payload.role : null;
}

export function requireAuth(allowedRoles = [], loginPage = 'login.html') {
    if (!isAuthenticated()) {
        logout(loginPage);
        return false;
    }
    if (allowedRoles && allowedRoles.length > 0) {
        const role = getUserRole();
        if (!allowedRoles.includes(role)) {
            alert('Access Denied: You do not have the required role for this page.');
            redirectTo( loginPage.startsWith('../') ? '../customer/products.html' : 'products.html');
            return false;
        }
    }
    return true;
}

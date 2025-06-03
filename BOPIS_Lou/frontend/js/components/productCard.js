// BOPIS_Lou/frontend/js/components/productCard.js
'use strict';

export function createProductCard(product, tenantId) {
    let placeholderText = 'Product';
    if (typeof product.name === 'string' && product.name) {
        placeholderText = product.name;
    }
    const imageUrl = product.image_url || ('https://via.placeholder.com/300x200.png?text=' + encodeURIComponent(placeholderText));

    const description = product.description ? (product.description.length > 60 ? product.description.substring(0, 57) + '...' : product.description) : 'No description available.';
    const price = typeof product.price === 'number' ? product.price : parseFloat(product.price);

    return `
        <div class="col" style="flex-basis: calc(25% - var(--spacing-lg)); margin-bottom: var(--spacing-lg);">
            <div class="card product-card h-full flex flex-col" data-product-id="${product.id}" style="height: 100%;">
                <img src="${imageUrl}" alt="${placeholderText}" style="width: 100%; height: 200px; object-fit: cover; border-top-left-radius: var(--radius-lg); border-top-right-radius: var(--radius-lg);">
                <div class="card-body flex flex-col flex-grow" style="padding: var(--spacing-md); display: flex; flex-direction: column; flex-grow: 1;">
                    <h3 class="card-title text-lg font-semibold mb-2">${product.name || 'N/A'}</h3>
                    <p class="text-xl font-bold text-primary mb-2">¥${price ? price.toLocaleString() : 'N/A'}</p>
                    <p class="text-sm text-muted flex-grow mb-3" style="flex-grow: 1;">${description}</p>
                    <div class="mt-auto flex justify-between gap-2" style="margin-top: auto;">
                        <a href="product-detail.html?id=${product.id}&tenantId=${tenantId}" class="btn btn-secondary btn-sm" style="width: 48%;">詳細</a>
                        <button class="btn btn-primary btn-sm add-to-cart-btn" style="width: 48%;" data-product-id="${product.id}" data-product-name="${product.name || 'Product'}">カートに追加</button>
                    </div>
                </div>
            </div>
        </div>
    `;
}



const API = "/api";


// --------------------------------------------------
// General helpers
// --------------------------------------------------

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API}${endpoint}`, {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        },
        ...options
    });

    let result;

    try {
        result = await response.json();
    } catch {
        throw new Error("The server returned an invalid response.");
    }

    if (!response.ok || result.success === false) {
        throw new Error(result.error || result.message || "Request failed");
    }

    return result.data;
}


function showMessage(message, type = "success") {
    const box = document.getElementById("alertBox");

    box.className = `alert alert-${type}`;
    box.textContent = message;
    box.classList.remove("d-none");

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

    setTimeout(() => {
        box.classList.add("d-none");
    }, 5000);
}


function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[char]);
}


function displayValue(value) {
    return value === null || value === undefined || value === ""
        ? "-"
        : escapeHTML(value);
}


function formatDate(value) {
    if (!value) return "-";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return escapeHTML(value);
    }

    return date.toLocaleString();
}


function formObject(form) {
    return Object.fromEntries(new FormData(form).entries());
}


function numberValue(value) {
    return value === "" || value === null ? null : Number(value);
}


function setTableMessage(id, message, columns) {
    document.getElementById(id).innerHTML =
        `<tr><td colspan="${columns}" class="text-center">${escapeHTML(message)}</td></tr>`;
}


// --------------------------------------------------
// Dashboard summary
// --------------------------------------------------

async function loadSummary() {
    const data = await apiRequest("/summary");

    document.getElementById("totalProducts").textContent =
        data.products ?? 0;

    document.getElementById("totalSkus").textContent =
        data.skus ?? 0;

    document.getElementById("totalLocations").textContent =
        data.locations ?? 0;

    document.getElementById("totalOrders").textContent =
        data.orders ?? 0;

    document.getElementById("totalOnHand").textContent =
        data.total_on_hand ?? 0;

    document.getElementById("totalReserved").textContent =
        data.total_reserved ?? 0;

    document.getElementById("totalBlocked").textContent =
        data.total_blocked ?? 0;

    document.getElementById("totalInTransit").textContent =
        data.total_in_transit ?? 0;
}


// --------------------------------------------------
// Products
// --------------------------------------------------

async function loadProducts() {
    const products = await apiRequest("/products");

    const tbody = document.getElementById("productsTable");
    const select = document.getElementById("skuProductSelect");

    tbody.innerHTML = "";
    select.innerHTML = '<option value="">Select product</option>';

    products.forEach(product => {
        tbody.innerHTML += `
            <tr>
                <td>${product.id}</td>
                <td>${displayValue(product.product_code)}</td>
                <td>${displayValue(product.name)}</td>
                <td>${displayValue(product.category)}</td>
                <td>${displayValue(product.brand)}</td>
            </tr>
        `;

        select.innerHTML += `
            <option value="${product.id}">
                ${escapeHTML(product.product_code)} - ${escapeHTML(product.name)}
            </option>
        `;
    });

    if (!products.length) {
        setTableMessage("productsTable", "No products found.", 5);
    }
}


async function loadSkus() {
    const skus = await apiRequest("/skus");
    const tbody = document.getElementById("skusTable");

    tbody.innerHTML = "";

    skus.forEach(sku => {
        tbody.innerHTML += `
            <tr>
                <td>${sku.id}</td>
                <td>${displayValue(sku.sku_code)}</td>
                <td>${sku.product_id}</td>
                <td>${displayValue(sku.description)}</td>
                <td>${displayValue(sku.unit_cost)}</td>
            </tr>
        `;
    });

    if (!skus.length) {
        setTableMessage("skusTable", "No SKUs found.", 5);
    }
}


// --------------------------------------------------
// Locations
// --------------------------------------------------

async function loadLocations() {
    const locations = await apiRequest("/locations");
    const tbody = document.getElementById("locationsTable");

    tbody.innerHTML = "";

    locations.forEach(location => {
        tbody.innerHTML += `
            <tr>
                <td>${location.id}</td>
                <td>${displayValue(location.location_code)}</td>
                <td>${displayValue(location.name)}</td>
                <td>${displayValue(location.location_type)}</td>
                <td>${displayValue(location.channel)}</td>
                <td>${displayValue(location.parent_id)}</td>
            </tr>
        `;
    });

    if (!locations.length) {
        setTableMessage("locationsTable", "No locations found.", 6);
    }
}


// --------------------------------------------------
// Inventory
// --------------------------------------------------

async function loadInventory() {
    const inventory = await apiRequest("/inventory");
    const tbody = document.getElementById("inventoryTable");

    tbody.innerHTML = "";

    inventory.forEach(row => {
        tbody.innerHTML += `
            <tr>
                <td>${row.id}</td>
                <td>${row.sku_id}</td>
                <td>${row.location_id}</td>
                <td>${row.on_hand}</td>
                <td>${row.reserved}</td>
                <td>${row.blocked}</td>
                <td>${row.in_transit}</td>
                <td>${row.safety_stock}</td>
                <td><strong>${row.available_to_promise}</strong></td>
            </tr>
        `;
    });

    if (!inventory.length) {
        setTableMessage("inventoryTable", "No inventory balances found.", 9);
    }
}


// --------------------------------------------------
// Stock movements
// --------------------------------------------------

async function loadMovements() {
    const movements = await apiRequest("/movements?limit=100");
    const tbody = document.getElementById("movementsTable");

    tbody.innerHTML = "";

    movements.forEach(movement => {
        tbody.innerHTML += `
            <tr>
                <td>${displayValue(movement.movement_code)}</td>
                <td>${movement.sku_id}</td>
                <td>${displayValue(movement.movement_type)}</td>
                <td>${movement.quantity}</td>
                <td>${displayValue(movement.from_location_id)}</td>
                <td>${displayValue(movement.to_location_id)}</td>
                <td>${formatDate(movement.occurred_at)}</td>
            </tr>
        `;
    });

    if (!movements.length) {
        setTableMessage("movementsTable", "No movements recorded.", 7);
    }
}


// --------------------------------------------------
// Orders
// --------------------------------------------------

async function loadOrders() {
    const orders = await apiRequest("/orders");
    const tbody = document.getElementById("ordersTable");

    tbody.innerHTML = "";

    orders.forEach(order => {
        const terminal = ["completed", "cancelled"].includes(order.status);

        tbody.innerHTML += `
            <tr>
                <td>${displayValue(order.order_code)}</td>
                <td>${displayValue(order.channel)}</td>
                <td><span class="status-pill">${displayValue(order.status)}</span></td>
                <td>${displayValue(order.fulfillment_location_id)}</td>
                <td>${formatDate(order.created_at)}</td>
                <td>
                    ${
                        terminal
                        ? "-"
                        : `
                            <button class="btn btn-sm btn-success action-btn"
                                onclick="fulfillOrder(${order.id})">
                                Fulfill
                            </button>
                            <button class="btn btn-sm btn-outline-danger action-btn"
                                onclick="cancelOrder(${order.id})">
                                Cancel
                            </button>
                        `
                    }
                </td>
            </tr>
        `;
    });

    if (!orders.length) {
        setTableMessage("ordersTable", "No orders found.", 6);
    }
}


async function fulfillOrder(orderId) {
    if (!confirm("Are you sure you want to fulfill this order?")) return;

    try {
        const result = await apiRequest(`/orders/${orderId}/fulfill`, {
            method: "POST"
        });

        showMessage(result?.message || "Order fulfilled successfully.");

        await refreshAll();
    } catch (error) {
        showMessage(error.message, "danger");
    }
}


async function cancelOrder(orderId) {
    if (!confirm("Are you sure you want to cancel this order?")) return;

    try {
        await apiRequest(`/orders/${orderId}/cancel`, {
            method: "POST"
        });

        showMessage("Order cancelled and reservations released.");

        await refreshAll();
    } catch (error) {
        showMessage(error.message, "danger");
    }
}


// --------------------------------------------------
// Transfers
// --------------------------------------------------

async function loadTransfers() {
    const transfers = await apiRequest("/transfers");
    const tbody = document.getElementById("transfersTable");

    tbody.innerHTML = "";

    transfers.forEach(transfer => {
        tbody.innerHTML += `
            <tr>
                <td>${displayValue(transfer.transfer_id)}</td>
                <td>${displayValue(transfer.sku_id)}</td>
                <td>${displayValue(transfer.source_location_id)}</td>
                <td>${displayValue(transfer.destination_location_id)}</td>
                <td>${displayValue(transfer.sent)}</td>
                <td>${displayValue(transfer.received)}</td>
                <td>${displayValue(transfer.remaining)}</td>
                <td><span class="status-pill">${displayValue(transfer.status)}</span></td>
            </tr>
        `;
    });

    if (!transfers.length) {
        setTableMessage("transfersTable", "No transfers found.", 8);
    }
}


// --------------------------------------------------
// Replenishment
// --------------------------------------------------

async function loadReplenishment() {
    const recommendations = await apiRequest("/replenishment");
    const tbody = document.getElementById("replenishmentTable");

    tbody.innerHTML = "";

    recommendations.forEach(item => {
        tbody.innerHTML += `
            <tr>
                <td>${displayValue(item.sku_id)}</td>
                <td>${displayValue(item.location_id)}</td>
                <td>${displayValue(item.atp)}</td>
                <td>${displayValue(item.target_stock)}</td>
                <td><strong>${displayValue(item.recommended_quantity)}</strong></td>
            </tr>
        `;
    });

    if (!recommendations.length) {
        setTableMessage(
            "replenishmentTable",
            "No replenishment recommendations.",
            5
        );
    }
}


// --------------------------------------------------
// Form submissions
// --------------------------------------------------

document.getElementById("productForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        await apiRequest("/products", {
            method: "POST",
            body: JSON.stringify(formObject(event.target))
        });

        event.target.reset();
        showMessage("Product added successfully.");

        await Promise.all([loadProducts(), loadSummary()]);
    } catch (error) {
        showMessage(error.message, "danger");
    }
});


document.getElementById("skuForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        const data = formObject(event.target);

        data.product_id = numberValue(data.product_id);
        data.unit_cost = numberValue(data.unit_cost);

        await apiRequest("/skus", {
            method: "POST",
            body: JSON.stringify(data)
        });

        event.target.reset();
        showMessage("SKU added successfully.");

        await Promise.all([loadSkus(), loadSummary()]);
        await loadProducts();
    } catch (error) {
        showMessage(error.message, "danger");
    }
});


document.getElementById("locationForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        await apiRequest("/locations", {
            method: "POST",
            body: JSON.stringify(formObject(event.target))
        });

        event.target.reset();
        showMessage("Location added successfully.");

        await Promise.all([loadLocations(), loadSummary()]);
    } catch (error) {
        showMessage(error.message, "danger");
    }
});


document.getElementById("movementForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        const data = formObject(event.target);

        data.sku_id = numberValue(data.sku_id);
        data.quantity = numberValue(data.quantity);
        data.from_location_id = numberValue(data.from_location_id);
        data.to_location_id = numberValue(data.to_location_id);

        await apiRequest("/movements", {
            method: "POST",
            body: JSON.stringify(data)
        });

        event.target.reset();
        showMessage("Stock movement recorded.");

        await refreshAll();
    } catch (error) {
        showMessage(error.message, "danger");
    }
});


document.getElementById("orderForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        const data = formObject(event.target);

        const orderData = {
            channel: data.channel,
            fulfillment_location_id: Number(data.fulfillment_location_id),
            reservation_minutes: Number(data.reservation_minutes),
            lines: [
                {
                    sku_id: Number(data.sku_id),
                    quantity: Number(data.quantity),
                    unit_price: Number(data.unit_price)
                }
            ]
        };

        await apiRequest("/orders", {
            method: "POST",
            body: JSON.stringify(orderData)
        });

        event.target.reset();
        showMessage("Order created and stock reserved.");

        await refreshAll();
    } catch (error) {
        showMessage(error.message, "danger");
    }
});


document.getElementById("transferForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        const data = formObject(event.target);

        data.sku_id = Number(data.sku_id);
        data.quantity = Number(data.quantity);
        data.source_location_id = Number(data.source_location_id);
        data.destination_location_id = Number(data.destination_location_id);

        const result = await apiRequest("/transfers", {
            method: "POST",
            body: JSON.stringify(data)
        });

        event.target.reset();

        showMessage(
            `Transfer created. Reference: ${result.transfer_id || result.reference_id || "See transfer records"}`
        );

        await refreshAll();
    } catch (error) {
        showMessage(error.message, "danger");
    }
});


document.getElementById("receiveTransferForm").addEventListener("submit", async event => {
    event.preventDefault();

    try {
        const data = formObject(event.target);

        data.sku_id = Number(data.sku_id);
        data.quantity = Number(data.quantity);
        data.source_location_id = Number(data.source_location_id);
        data.destination_location_id = Number(data.destination_location_id);

        await apiRequest("/transfers/receive", {
            method: "POST",
            body: JSON.stringify(data)
        });

        event.target.reset();
        showMessage("Transfer received successfully.");

        await refreshAll();
    } catch (error) {
        showMessage(error.message, "danger");
    }
});


// --------------------------------------------------
// Load all dashboard data
// --------------------------------------------------

async function refreshAll() {
    const tasks = [
        loadSummary(),
        loadProducts(),
        loadSkus(),
        loadLocations(),
        loadInventory(),
        loadMovements(),
        loadOrders(),
        loadTransfers(),
        loadReplenishment()
    ];

    const results = await Promise.allSettled(tasks);

    const failed = results.filter(result => result.status === "rejected");

    if (failed.length) {
        console.error("Some dashboard sections could not load:", failed);
        showMessage(
            `${failed.length} dashboard section(s) could not load. Check the browser console and Flask terminal.`,
            "warning"
        );
    }
}


document.getElementById("refreshBtn").addEventListener("click", refreshAll);


// --------------------------------------------------
// Sidebar navigation
// --------------------------------------------------

document.querySelectorAll(".sidebar-nav .nav-link").forEach(link => {
    link.addEventListener("click", () => {
        document.querySelectorAll(".sidebar-nav .nav-link")
            .forEach(item => item.classList.remove("active"));

        link.classList.add("active");
    });
});


// Load dashboard when page opens
document.addEventListener("DOMContentLoaded", refreshAll);

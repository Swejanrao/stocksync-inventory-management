"use strict";

/* =========================================
   STOCKSYNC - FRONTEND API INTEGRATION
========================================= */

const API = "/api";

const state = {
    products: [],
    skus: [],
    locations: [],
    inventory: [],
    orders: [],
    movements: [],
    reservations: [],
    shipments: [],
    transfers: [],
    replenishment: []
};

const $ = (id) => document.getElementById(id);

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

function displayValue(value) {
    return value === null || value === undefined || value === ""
        ? "—"
        : escapeHTML(value);
}

function number(value) {
    const result = Number(value ?? 0);
    return Number.isFinite(result) ? result : 0;
}

function formatNumber(value) {
    return number(value).toLocaleString();
}

function formatDate(value) {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return displayValue(value);
    }

    return date.toLocaleString();
}

function getStatus(status) {
    const safeStatus = String(status ?? "unknown");
    return `<span class="status-badge ${escapeHTML(safeStatus.toLowerCase())}">
        ${escapeHTML(safeStatus.replaceAll("_", " "))}
    </span>`;
}

function showAlert(message, type = "success") {
    const area = $("alert-area");

    if (!area) return;

    area.innerHTML = `
        <div class="alert ${type}">
            ${escapeHTML(message)}
        </div>
    `;

    area.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function clearAlert() {
    if ($("alert-area")) {
        $("alert-area").innerHTML = "";
    }
}

function getRows(data) {
    if (Array.isArray(data)) return data;

    if (data && typeof data === "object") {
        for (const key of ["items", "transfers", "recommendations", "records", "results"]) {
            if (Array.isArray(data[key])) return data[key];
        }
    }

    return [];
}

/* =========================================
   API HELPER
========================================= */

async function apiRequest(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    let result;

    try {
        result = await response.json();
    } catch {
        throw new Error(`Server returned an invalid response (${response.status}).`);
    }

    if (!response.ok || result.success === false) {
        throw new Error(
            result.error ||
            result.message ||
            `Request failed with status ${response.status}`
        );
    }

    return result.data !== undefined ? result.data : result;
}

async function getData(path) {
    return apiRequest(path);
}

async function postData(path, body) {
    return apiRequest(path, {
        method: "POST",
        body: JSON.stringify(body)
    });
}

/* =========================================
   PAGE NAVIGATION
========================================= */

function navigateTo(page) {
    document.querySelectorAll(".page-section").forEach(section => {
        section.classList.remove("active");
    });

    document.querySelectorAll(".nav-link").forEach(link => {
        link.classList.toggle("active", link.dataset.page === page);
    });

    const section = $(`page-${page}`);

    if (!section) return;

    section.classList.add("active");

    const activeLink = document.querySelector(
        `.nav-link[data-page="${page}"]`
    );

    $("page-title").textContent = activeLink
        ? activeLink.textContent.trim()
        : page;

    $("sidebar").classList.remove("open");

    loadPageData(page);
}

document.querySelectorAll(".nav-link").forEach(button => {
    button.addEventListener("click", () => {
        navigateTo(button.dataset.page);
    });
});

document.querySelectorAll("[data-go]").forEach(button => {
    button.addEventListener("click", () => {
        navigateTo(button.dataset.go);
    });
});

$("menu-toggle").addEventListener("click", () => {
    $("sidebar").classList.toggle("open");
});

/* =========================================
   DASHBOARD OVERVIEW
========================================= */

async function loadSummary() {
    const data = await getData("/summary");

    const values = {
        "stat-products": data.products,
        "stat-skus": data.skus,
        "stat-locations": data.locations,
        "stat-orders": data.orders,
        "stat-onhand": data.total_on_hand,
        "stat-reserved": data.total_reserved,
        "stat-blocked": data.total_blocked,
        "stat-movements": data.movements,
        "health-onhand": data.total_on_hand,
        "health-reserved": data.total_reserved,
        "health-blocked": data.total_blocked,
        "health-transit": data.total_in_transit
    };

    Object.entries(values).forEach(([id, value]) => {
        if ($(id)) {
            $(id).textContent = formatNumber(value);
        }
    });
}

async function loadRecentMovements() {
    const data = await getData("/movements?limit=8");
    const rows = getRows(data);

    $("recent-movements").innerHTML = rows.length
        ? rows.slice(0, 8).map(item => `
            <tr>
                <td>${displayValue(item.movement_code)}</td>
                <td>${displayValue(item.sku_id)}</td>
                <td>${displayValue(item.movement_type)}</td>
                <td>${formatNumber(item.quantity)}</td>
                <td>${formatDate(item.occurred_at)}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="5" class="empty">No movements found.</td></tr>`;
}

/* =========================================
   PRODUCTS
========================================= */

async function loadProducts() {
    const data = await getData("/products");
    state.products = getRows(data);

    $("products-table").innerHTML = state.products.length
        ? state.products.map(product => `
            <tr>
                <td>${displayValue(product.id)}</td>
                <td>${displayValue(product.product_code)}</td>
                <td>${displayValue(product.name)}</td>
                <td>${displayValue(product.category)}</td>
                <td>${displayValue(product.brand)}</td>
                <td>${getStatus(product.active ? "active" : "inactive")}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="6" class="empty">No products found.</td></tr>`;

    fillSelect(
        "sku-product",
        state.products,
        "id",
        "name",
        "Select product"
    );
}

async function loadSKUs() {
    const data = await getData("/skus");
    state.skus = getRows(data);

    $("skus-table").innerHTML = state.skus.length
        ? state.skus.map(sku => `
            <tr>
                <td>${displayValue(sku.id)}</td>
                <td>${displayValue(sku.sku_code)}</td>
                <td>${displayValue(sku.product_id)}</td>
                <td>${displayValue(sku.description)}</td>
                <td>${displayValue(sku.unit_of_measure)}</td>
                <td>${displayValue(sku.unit_cost)}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="6" class="empty">No SKUs found.</td></tr>`;

    ["order-sku", "transfer-sku", "movement-sku", "reconcile-sku"].forEach(id => {
        fillSelect(id, state.skus, "id", "sku_code", "Select SKU");
    });
}

/* =========================================
   LOCATIONS
========================================= */

async function loadLocations() {
    const data = await getData("/locations");
    state.locations = getRows(data);

    $("locations-table").innerHTML = state.locations.length
        ? state.locations.map(location => `
            <tr>
                <td>${displayValue(location.id)}</td>
                <td>${displayValue(location.location_code)}</td>
                <td>${displayValue(location.name)}</td>
                <td>${displayValue(location.location_type)}</td>
                <td>${displayValue(location.channel)}</td>
                <td>${displayValue(location.parent_id)}</td>
                <td>${getStatus(location.active ? "active" : "inactive")}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="7" class="empty">No locations found.</td></tr>`;

    fillSelect("location-parent", state.locations, "id", "name", "No parent location");

    [
        "order-location",
        "transfer-source",
        "transfer-destination",
        "movement-from",
        "movement-to",
        "reconcile-location"
    ].forEach(id => {
        const placeholder = id === "movement-from" || id === "movement-to"
            ? "No location"
            : "Select location";

        fillSelect(id, state.locations, "id", "name", placeholder);
    });
}

function fillSelect(id, rows, valueKey, labelKey, placeholder) {
    const select = $(id);

    if (!select) return;

    const previousValue = select.value;

    select.innerHTML = `<option value="">${escapeHTML(placeholder)}</option>`;

    rows.forEach(row => {
        const option = document.createElement("option");
        option.value = row[valueKey];
        option.textContent = row[labelKey] ?? row[valueKey];
        select.appendChild(option);
    });

    if (rows.some(row => String(row[valueKey]) === previousValue)) {
        select.value = previousValue;
    }
}

/* =========================================
   INVENTORY
========================================= */

async function loadInventory() {
    const data = await getData("/inventory");
    state.inventory = getRows(data);

    $("inventory-table").innerHTML = state.inventory.length
        ? state.inventory.map(item => `
            <tr>
                <td>${displayValue(item.sku_id)}</td>
                <td>${displayValue(item.location_id)}</td>
                <td>${formatNumber(item.on_hand)}</td>
                <td>${formatNumber(item.reserved)}</td>
                <td>${formatNumber(item.blocked)}</td>
                <td>${formatNumber(item.safety_stock)}</td>
                <td>${formatNumber(item.in_transit)}</td>
                <td><strong>${formatNumber(item.available_to_promise)}</strong></td>
            </tr>
        `).join("")
        : `<tr><td colspan="8" class="empty">No inventory records found.</td></tr>`;
}

/* =========================================
   ORDERS
========================================= */

async function loadOrders() {
    const data = await getData("/orders");
    state.orders = getRows(data);

    $("orders-table").innerHTML = state.orders.length
        ? state.orders.map(order => `
            <tr>
                <td>${displayValue(order.order_code)}</td>
                <td>${displayValue(order.channel)}</td>
                <td>${getStatus(order.status)}</td>
                <td>${displayValue(order.fulfillment_location_id)}</td>
                <td>${formatDate(order.created_at)}</td>
                <td>
                    <button class="action-btn" data-order-action="fulfill"
                        data-id="${escapeHTML(order.id)}">Fulfill</button>
                    <button class="action-btn danger" data-order-action="cancel"
                        data-id="${escapeHTML(order.id)}">Cancel</button>
                </td>
            </tr>
        `).join("")
        : `<tr><td colspan="6" class="empty">No orders found.</td></tr>`;
}

$("orders-table").addEventListener("click", async event => {
    const button = event.target.closest("[data-order-action]");
    if (!button) return;

    const id = button.dataset.id;
    const action = button.dataset.orderAction;

    const message = action === "cancel"
        ? "Are you sure you want to cancel this order?"
        : "Are you sure you want to fulfill this order?";

    if (!confirm(message)) return;

    try {
        await postData(`/orders/${id}/${action}`, {});
        showAlert(`Order ${action} request completed.`);
        await refreshAll();
    } catch (error) {
        showAlert(error.message, "error");
    }
});

/* =========================================
   TRANSFERS
========================================= */

async function loadTransfers() {
    const data = await getData("/transfers");
    state.transfers = getRows(data);

    $("transfers-table").innerHTML = state.transfers.length
        ? state.transfers.map(item => {
            const sku = item.sku_id ?? item.sku;
            const source = item.source_location_id ?? item.from_location_id;
            const destination = item.destination_location_id ?? item.to_location_id;
            const quantity = item.quantity ?? item.transfer_quantity;
            const status = item.status ?? item.movement_type ?? "recorded";

            return `
                <tr>
                    <td>${displayValue(item.transfer_code ?? item.reference_id ?? item.id)}</td>
                    <td>${displayValue(sku)}</td>
                    <td>${displayValue(source)}</td>
                    <td>${displayValue(destination)}</td>
                    <td>${formatNumber(quantity)}</td>
                    <td>${getStatus(status)}</td>
                </tr>
            `;
        }).join("")
        : `<tr><td colspan="6" class="empty">No transfers found.</td></tr>`;
}

/* =========================================
   MOVEMENTS
========================================= */

async function loadMovements() {
    const data = await getData("/movements?limit=100");
    state.movements = getRows(data);

    $("movements-table").innerHTML = state.movements.length
        ? state.movements.map(item => `
            <tr>
                <td>${displayValue(item.movement_code)}</td>
                <td>${displayValue(item.sku_id)}</td>
                <td>${displayValue(item.from_location_id)}</td>
                <td>${displayValue(item.to_location_id)}</td>
                <td>${displayValue(item.movement_type)}</td>
                <td>${formatNumber(item.quantity)}</td>
                <td>${formatDate(item.occurred_at)}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="7" class="empty">No movements found.</td></tr>`;
}

/* =========================================
   RESERVATIONS
========================================= */

async function loadReservations() {
    const data = await getData("/reservations");
    state.reservations = getRows(data);

    $("reservations-table").innerHTML = state.reservations.length
        ? state.reservations.map(item => `
            <tr>
                <td>${displayValue(item.reservation_code)}</td>
                <td>${displayValue(item.order_id)}</td>
                <td>${displayValue(item.sku_id)}</td>
                <td>${displayValue(item.location_id)}</td>
                <td>${formatNumber(item.quantity)}</td>
                <td>${getStatus(item.status)}</td>
                <td>${formatDate(item.expires_at)}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="7" class="empty">No reservations found.</td></tr>`;
}

/* =========================================
   SHIPMENTS
========================================= */

async function loadShipments() {
    const data = await getData("/shipments");
    state.shipments = getRows(data);

    $("shipments-table").innerHTML = state.shipments.length
        ? state.shipments.map(item => `
            <tr>
                <td>${displayValue(item.shipment_code)}</td>
                <td>${displayValue(item.order_id)}</td>
                <td>${displayValue(item.origin_location_id)}</td>
                <td>${displayValue(item.destination_location_id)}</td>
                <td>${getStatus(item.status)}</td>
                <td>${formatDate(item.shipped_at)}</td>
                <td>${formatDate(item.delivered_at)}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="7" class="empty">No shipments found.</td></tr>`;
}

/* =========================================
   REPLENISHMENT
========================================= */

async function loadReplenishment() {
    const data = await getData("/replenishment");
    state.replenishment = getRows(data);

    $("replenishment-table").innerHTML = state.replenishment.length
        ? state.replenishment.map(item => `
            <tr>
                <td>${displayValue(item.sku_code ?? item.sku_id ?? item.sku)}</td>
                <td>${displayValue(item.location_name ?? item.location_id ?? item.location)}</td>
                <td>${displayValue(item.current_stock ?? item.available_stock ?? item.on_hand)}</td>
                <td>${displayValue(item.recommended_quantity ?? item.reorder_quantity ?? item.quantity)}</td>
                <td>${displayValue(item.reason ?? item.recommendation ?? "—")}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="5" class="empty">No replenishment recommendations found.</td></tr>`;
}

/* =========================================
   RECONCILIATION
========================================= */

$("reconciliation-form").addEventListener("submit", async event => {
    event.preventDefault();

    const form = new FormData(event.target);
    const skuId = form.get("sku_id");
    const locationId = form.get("location_id");

    $("reconciliation-result").textContent = "Checking balance...";

    try {
        const data = await getData(
            `/reconciliation/${encodeURIComponent(skuId)}/${encodeURIComponent(locationId)}`
        );

        $("reconciliation-result").textContent =
            JSON.stringify(data, null, 2);

        showAlert("Reconciliation request completed.");
    } catch (error) {
        $("reconciliation-result").textContent = error.message;
        showAlert(error.message, "error");
    }
});

/* =========================================
   FORM HELPER
========================================= */

function formObject(form) {
    const data = Object.fromEntries(new FormData(form).entries());

    Object.keys(data).forEach(key => {
        if (data[key] === "") {
            delete data[key];
        }
    });

    return data;
}

function toNumberFields(data, fields) {
    fields.forEach(field => {
        if (data[field] !== undefined) {
            data[field] = Number(data[field]);
        }
    });

    return data;
}

function bindForm(formId, handler) {
    $(formId).addEventListener("submit", async event => {
        event.preventDefault();

        const form = event.currentTarget;
        const button = form.querySelector('button[type="submit"]');

        if (button) {
            button.disabled = true;
            button.textContent = "Please wait...";
        }

        clearAlert();

        try {
            await handler(form);
            form.reset();
            showAlert("Your request was completed successfully.");
            await refreshAll();
        } catch (error) {
            showAlert(error.message, "error");
        } finally {
            if (button) {
                button.disabled = false;
                button.textContent = button.dataset.originalText || "Submit";
            }
        }
    });

    const button = $(formId).querySelector('button[type="submit"]');

    if (button) {
        button.dataset.originalText = button.textContent;
    }
}

/* =========================================
   CREATE PRODUCT
========================================= */

bindForm("product-form", async form => {
    const data = formObject(form);

    await postData("/products", data);
});

/* =========================================
   CREATE SKU
========================================= */

bindForm("sku-form", async form => {
    const data = toNumberFields(
        formObject(form),
        ["product_id", "unit_cost"]
    );

    await postData("/skus", data);
});

/* =========================================
   CREATE LOCATION
========================================= */

bindForm("location-form", async form => {
    const data = toNumberFields(
        formObject(form),
        ["parent_id"]
    );

    await postData("/locations", data);
});

/* =========================================
   CREATE ORDER
========================================= */

bindForm("order-form", async form => {
    const data = toNumberFields(
        formObject(form),
        [
            "fulfillment_location_id",
            "sku_id",
            "quantity",
            "unit_price",
            "reservation_minutes"
        ]
    );

    const payload = {
        channel: data.channel,
        fulfillment_location_id: data.fulfillment_location_id,
        reservation_minutes: data.reservation_minutes || 20,
        lines: [
            {
                sku_id: data.sku_id,
                quantity: data.quantity,
                unit_price: data.unit_price || 0
            }
        ]
    };

    await postData("/orders", payload);
});

/* =========================================
   CREATE TRANSFER
========================================= */

bindForm("transfer-form", async form => {
    const data = toNumberFields(
        formObject(form),
        [
            "sku_id",
            "source_location_id",
            "destination_location_id",
            "quantity"
        ]
    );

    if (data.source_location_id === data.destination_location_id) {
        throw new Error("Source and destination locations must be different.");
    }

    await postData("/transfers", data);
});

/* =========================================
   CREATE MOVEMENT
========================================= */

bindForm("movement-form", async form => {
    const data = toNumberFields(
        formObject(form),
        [
            "sku_id",
            "from_location_id",
            "to_location_id",
            "quantity"
        ]
    );

    await postData("/movements", data);
});

/* =========================================
   EXPIRE RESERVATIONS
========================================= */

$("expire-reservations").addEventListener("click", async () => {
    if (!confirm("Process reservations that have passed their expiry time?")) {
        return;
    }

    try {
        const result = await postData("/reservations/expire", {});
        showAlert("Expired reservation processing completed.");
        console.log("Reservation expiry result:", result);
        await refreshAll();
    } catch (error) {
        showAlert(error.message, "error");
    }
});

/* =========================================
   SEARCH FILTERS
========================================= */

function addTableSearch(inputId, tableId) {
    const input = $(inputId);

    if (!input) return;

    input.addEventListener("input", () => {
        const query = input.value.toLowerCase();

        document.querySelectorAll(`#${tableId} tr`).forEach(row => {
            row.style.display = row.textContent.toLowerCase().includes(query)
                ? ""
                : "none";
        });
    });
}

addTableSearch("product-search", "products-table");
addTableSearch("inventory-search", "inventory-table");

/* =========================================
   LOAD PAGE DATA
========================================= */

async function loadPageData(page) {
    const loaders = {
        overview: [loadSummary, loadRecentMovements],
        products: [loadProducts, loadSKUs],
        locations: [loadLocations],
        inventory: [loadInventory],
        orders: [loadOrders],
        transfers: [loadTransfers],
        movements: [loadMovements],
        reservations: [loadReservations],
        shipments: [loadShipments],
        replenishment: [loadReplenishment],
        reconciliation: [loadSKUs, loadLocations]
    };

    const tasks = loaders[page] || [];

    const results = await Promise.allSettled(
        tasks.map(loader => loader())
    );

    const failures = results.filter(result => result.status === "rejected");

    if (failures.length) {
        showAlert(
            `Some ${page} data could not be loaded: ` +
            failures.map(item => item.reason.message).join("; "),
            "error"
        );
    }
}

/* =========================================
   REFRESH ALL DASHBOARD DATA
========================================= */

async function refreshAll() {
    clearAlert();

    const tasks = [
        loadSummary(),
        loadRecentMovements(),
        loadProducts(),
        loadSKUs(),
        loadLocations(),
        loadInventory(),
        loadOrders(),
        loadTransfers(),
        loadMovements(),
        loadReservations(),
        loadShipments(),
        loadReplenishment()
    ];

    const results = await Promise.allSettled(tasks);

    const failures = results.filter(result => result.status === "rejected");

    $("connection-status").textContent = failures.length
        ? "Some API requests failed"
        : "Connected";

    const dot = document.querySelector(".status-dot");

    if (dot) {
        dot.style.background = failures.length ? "#e7b84e" : "#38c987";
    }

    if (failures.length) {
        console.error("Dashboard loading errors:", failures);
        showAlert(
            `${failures.length} dashboard data request(s) failed. Check the browser console and Flask terminal.`,
            "error"
        );
    }
}
// Add Inventory button
document.addEventListener("DOMContentLoaded", () => {
    const addInventoryButton = document.getElementById("add-inventory-btn");

    if (addInventoryButton) {
        addInventoryButton.addEventListener("click", () => {
            // Open the Movements page
            const movementPageButton = document.querySelector(
                '[data-page="movements"]'
            );

            if (movementPageButton) {
                movementPageButton.click();
            }

            // Automatically select Receipt
            const movementType = document.querySelector(
                '#movement-form [name="movement_type"]'
            );

            if (movementType) {
                movementType.value = "receipt";
            }

            // Scroll to the movement form
            document.getElementById("movement-form")?.scrollIntoView({
                behavior: "smooth",
                block: "center"
            });
        });
    }
});

$("refresh-btn").addEventListener("click", refreshAll);

/* =========================================
   START APPLICATION
========================================= */

document.addEventListener("DOMContentLoaded", () => {
    refreshAll();
});

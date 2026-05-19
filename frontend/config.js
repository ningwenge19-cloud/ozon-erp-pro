// Keep empty for local/Railway single-service mode.
// For Vercel static frontend, replace this with your Railway backend URL.
// Example: window.OZON_ERP_API_BASE_URL = "https://ozon-erp-pro.up.railway.app";
const apiParam = new URLSearchParams(window.location.search).get("api");
if (apiParam) localStorage.setItem("apiBaseUrl", apiParam.replace(/\/+$/, ""));
window.OZON_ERP_API_BASE_URL = window.OZON_ERP_API_BASE_URL || localStorage.getItem("apiBaseUrl") || "";

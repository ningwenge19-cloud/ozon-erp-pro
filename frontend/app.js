const $ = id => document.getElementById(id);

let token = localStorage.getItem("token") || "";
let me = JSON.parse(localStorage.getItem("me") || "null");
let cachedOrders = [];
let cachedSourcingProducts = [];
let profitTimer = null;
let appConfig = {
  app_name: "Ozon SaaS ERP",
  tagline: "面向跨境卖家的订单、库存、利润和 AI 运营工作台",
  exchange_rate: 0.078,
  support_email: "support@example.com"
};
const API_BASE_URL = String(window.OZON_ERP_API_BASE_URL || localStorage.getItem("apiBaseUrl") || "").replace(/\/+$/, "");

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[ch]));
}

function money(value, digits = 2) {
  return Number(value || 0).toLocaleString("zh-CN", {
    maximumFractionDigits: digits
  });
}

async function api(path, options = {}) {
  const timeoutMs = options.timeoutMs;
  delete options.timeoutMs;
  let timer = null;
  if (timeoutMs) {
    const controller = new AbortController();
    options.signal = controller.signal;
    timer = setTimeout(() => controller.abort(), timeoutMs);
  }
  options.headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };
  if (token) options.headers.Authorization = "Bearer " + token;
  try {
    const url = /^https?:\/\//i.test(path) ? path : API_BASE_URL + path;
    return await fetch(url, options);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

async function responseData(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { detail: text || "服务器返回了无法解析的响应" };
  }
}

function toast(message) {
  $("toast").innerText = message;
  $("toast").classList.remove("hidden");
  setTimeout(() => $("toast").classList.add("hidden"), 2600);
}

function showAuth() {
  $("authPage").classList.remove("hidden");
  $("app").classList.add("hidden");
}

function showApp() {
  $("authPage").classList.add("hidden");
  $("app").classList.remove("hidden");
}

function switchAuth(tab, event) {
  document.querySelectorAll(".auth-tabs button").forEach(button => button.classList.remove("active"));
  if (event?.target) event.target.classList.add("active");
  $("loginBox").classList.toggle("hidden", tab !== "login");
  $("registerBox").classList.toggle("hidden", tab !== "register");
}

async function login() {
  const account = $("loginAccount").value.trim();
  const password = $("loginPassword").value;
  if (!account || !password) return toast("请输入账号和密码");

  const response = await api("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ account, password })
  });
  const data = await response.json();
  if (!response.ok) return toast(data.detail || "登录失败");

  token = data.token;
  me = data.user;
  localStorage.setItem("token", token);
  localStorage.setItem("me", JSON.stringify(me));
  init();
}

async function register() {
  const username = $("regUsername").value.trim();
  const email = $("regEmail").value.trim();
  const password = $("regPassword").value;
  const code = $("regCode").value.trim();
  if (!username || !email || !password || !code) return toast("请完整填写注册信息和邮箱验证码");

  const response = await api("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, email, password, code })
  });
  const data = await responseData(response);
  if (!response.ok) return toast(data.detail || "注册失败");

  token = data.token;
  me = data.user;
  localStorage.setItem("token", token);
  localStorage.setItem("me", JSON.stringify(me));
  init();
}

async function sendRegisterCode() {
  const email = $("regEmail").value.trim();
  if (!email) return toast("请先填写邮箱");
  const response = await api("/api/auth/register/code", {
    method: "POST",
    body: JSON.stringify({ email })
  });
  const data = await responseData(response);
  if (!response.ok) return toast(data.detail || "验证码发送失败");
  toast(data.dev_code ? `开发模式验证码：${data.dev_code}` : "验证码已发送到邮箱");
}

function logout() {
  localStorage.clear();
  token = "";
  me = null;
  showAuth();
}

function applyAppSettings() {
  document.title = appConfig.app_name || "Ozon SaaS ERP";
  document.querySelectorAll("[data-brand-name]").forEach(item => item.innerText = appConfig.app_name || "Ozon SaaS ERP");
  document.querySelectorAll("[data-brand-tagline]").forEach(item => item.innerText = appConfig.tagline || "面向跨境卖家的订单、库存、利润和 AI 运营工作台");
  if ($("pfRateHint")) $("pfRateHint").innerText = `当前汇率：1 ₽ ≈ ¥${Number(appConfig.exchange_rate || 0.078).toFixed(3)}`;
}

async function loadAppSettings() {
  const response = await api("/api/app/settings");
  if (!response.ok) {
    applyAppSettings();
    return;
  }
  appConfig = await response.json();
  applyAppSettings();
  if (isAdmin() && $("setAppName")) fillSettingsForm();
}

function fillSettingsForm() {
  $("setAppName").value = appConfig.app_name || "";
  $("setTagline").value = appConfig.tagline || "";
  $("setRate").value = appConfig.exchange_rate || 0.078;
  $("setEmail").value = appConfig.support_email || "";
}

document.querySelectorAll(".nav[data-tab]").forEach(button => {
  button.onclick = () => {
    document.querySelectorAll(".nav").forEach(item => item.classList.remove("active"));
    button.classList.add("active");
    document.querySelectorAll(".page").forEach(page => page.classList.remove("active"));
    $(button.dataset.tab).classList.add("active");
    $("pageTitle").innerText = button.innerText;
    loadAll();
  };
});

["pfProduct", "pfSku", "pfCategory", "pfPrice", "pfCost", "pfWeight", "pfShip", "pfComm", "pfScheme"].forEach(id => {
  const element = $(id);
  if (element) element.addEventListener(id === "pfScheme" ? "change" : "input", scheduleProfitPreview);
});

function isAdmin() {
  return me && me.role === "admin";
}

function applyRoleUI() {
  $("userInfo").innerText = `${me.username} · ${isAdmin() ? "管理员" : "普通用户"}`;
  document.querySelectorAll(".admin-only").forEach(item => item.classList.toggle("hidden", !isAdmin()));
}

async function init() {
  await loadAppSettings();
  if (!token) return showAuth();
  const response = await api("/api/me");
  if (!response.ok) return logout();

  me = await response.json();
  localStorage.setItem("me", JSON.stringify(me));
  showApp();
  applyRoleUI();
  await loadAll();
}

async function loadAll() {
  if (!token) return;
  loadAppSettings();
  loadDashboard();
  loadOrders();
  loadRefunds();
  loadOzonSettings();
  loadOzonShops();
  loadFeeRules();
  loadProducts();
  loadSourcing();
  loadTickets();
  loadAISettings();
  if (isAdmin()) {
    loadAdmin();
    if ($("setAppName")) fillSettingsForm();
  }
}

function table(element, headers, rows) {
  element.innerHTML = `
    <thead><tr>${headers.map(header => `<th>${esc(header)}</th>`).join("")}</tr></thead>
    <tbody>${rows.length ? rows.join("") : `<tr><td colspan="${headers.length}" class="empty">暂无数据</td></tr>`}</tbody>
  `;
}

async function loadDashboard() {
  const response = await api("/api/dashboard");
  if (!response.ok) return;
  const data = await response.json();

  $("stOrders").innerText = money(data.orders, 0);
  $("stSales").innerText = money(data.sales_rub);
  $("stProfit").innerText = money(data.profit_cny);
  $("stProducts").innerText = money(data.products, 0);
  $("stTickets").innerText = money(data.open_tickets, 0);

  table($("recentOrders"), ["订单号", "状态", "商品", "数量", "售价 ₽", "利润 ¥"], data.recent_orders.map(order => `
    <tr>
      <td>${esc(order.order_no)}</td>
      <td><span class="badge">${esc(order.status)}</span></td>
      <td>${esc(order.product)}</td>
      <td>${esc(order.quantity)}</td>
      <td>${money(order.price_rub)}</td>
      <td>${money(order.profit_cny)}</td>
    </tr>
  `));
}

async function calcProfit(silent = false) {
  if (!$("pfProduct").value.trim() && !$("pfPrice").value && !silent) return toast("请输入商品或售价");
  const commissionValue = $("pfComm").value.trim();
  const response = await api("/api/profit/preview", {
    method: "POST",
    body: JSON.stringify({
      product: $("pfProduct").value.trim(),
      sku: $("pfSku").value.trim(),
      category: $("pfCategory").value.trim(),
      scheme: $("pfScheme").value,
      price_rub: Number($("pfPrice").value || 0),
      cost_cny: Number($("pfCost").value || 0),
      weight_kg: Number($("pfWeight").value || 0),
      shipping_cny: Number($("pfShip").value || 0),
      commission_rate: commissionValue ? Number(commissionValue) : null
    })
  });
  const data = await responseData(response);
  if (!response.ok) {
    if (!silent) toast(data.detail || "计算失败");
    return;
  }
  const finance = data.finance || {};
  if (data.category) $("pfCategory").value = data.category;
  const fee = data.category_fee || {};
  const categoryLine = data.category ? `匹配类目：${data.category}` : "匹配类目：未匹配，可手动填写";
  const feeLine = fee.percent !== undefined ? `平台费率：${Number(fee.percent).toFixed(2)}%（${fee.scheme === "fbp" ? "FBP" : "rFBS"}，${fee.column}）` : `平台费率：${(Number(finance.commission_rate || 0) * 100).toFixed(2)}%`;
  const profitRate = finance.revenue_cny ? Number(finance.profit_cny || 0) / Number(finance.revenue_cny) * 100 : 0;
  $("profitResult").innerText =
    `${categoryLine}\n` +
    `${feeLine}\n` +
    `收入约：¥${money(finance.revenue_cny)}\n` +
    `采购成本：¥${money($("pfCost").value)}\n` +
    `物流成本：¥${money(finance.logistics_fee_cny)}\n` +
    `平台费用：¥${money(finance.platform_fee_cny)}\n` +
    `额外税费：¥${money(finance.tax_cny)}\n` +
    `预计利润：¥${money(finance.profit_cny)}\n` +
    `利润率：${profitRate.toFixed(1)}%`;
}

function scheduleProfitPreview() {
  clearTimeout(profitTimer);
  profitTimer = setTimeout(() => {
    if ($("pfProduct") && ($("pfProduct").value.trim() || $("pfPrice").value)) calcProfit(true);
  }, 450);
}

async function saveOzon() {
  const body = {
    client_id: $("ozonClient").value.trim(),
    api_key: $("ozonKey").value,
    sync_type: $("ozonType").value
  };
  const response = await api("/api/ozon/settings", {
    method: "POST",
    body: JSON.stringify(body)
  });
  toast(response.ok ? "Ozon 配置已保存" : "保存失败");
  if (response.ok) loadOzonSettings();
}

async function loadOzonSettings() {
  const response = await api("/api/ozon/settings");
  if (!response.ok) return;
  const data = await response.json();
  $("ozonClient").value = data.client_id || "";
  $("ozonType").value = data.sync_type || $("ozonType").value;
  $("ozonKey").placeholder = data.api_key_set ? "API-Key 已保存，留空可保持不变" : "API-Key";
}

async function syncDemoOrders() {
  const response = await api("/api/ozon/sync-demo", { method: "POST" });
  const data = await response.json();
  toast(response.ok ? `已导入 ${data.imported} 条演示订单` : data.detail || "导入失败");
  loadOrders();
  loadDashboard();
}

async function bindOzonShop() {
  if (!$("shopClient").value.trim() || !$("shopKey").value.trim()) return toast("请填写 Ozon Client-Id 和 API-Key");
  const body = {
    shop_name: $("shopName").value.trim() || "Ozon Store",
    client_id: $("shopClient").value.trim(),
    api_key: $("shopKey").value.trim(),
    sync_type: $("shopType").value,
    auto_sync: $("shopAuto").checked
  };
  const response = await api("/api/ozon/shops", {
    method: "POST",
    body: JSON.stringify(body)
  });
  const data = await responseData(response);
  toast(response.ok ? "店铺已绑定" : data.detail || "绑定失败");
  if (response.ok) {
    $("shopKey").value = "";
    loadOzonShops();
  }
}

async function loadOzonShops() {
  if (!$("shopsTable")) return;
  const response = await api("/api/ozon/shops");
  if (!response.ok) return;
  const rows = await response.json();
  if ($("jobShop")) {
    const current = $("jobShop").value;
    $("jobShop").innerHTML = `<option value="">选择 Ozon 店铺</option>` + rows.map(shop => `<option value="${shop.id}">${esc(shop.shop_name)}</option>`).join("");
    $("jobShop").value = current;
  }
  table($("shopsTable"), ["店铺", "Client-Id", "类型", "订单", "销售 ₽", "退款 ¥", "利润 ¥", "自动同步", "上次同步", "操作"], rows.map(shop => `
    <tr>
      <td>${esc(shop.shop_name)}</td>
      <td>${esc(shop.client_id)}</td>
      <td>${esc(shop.sync_type)}</td>
      <td>${money(shop.order_count, 0)}</td>
      <td>${money(shop.sales_rub)}</td>
      <td>${money(shop.refund_cny)}</td>
      <td>${money(shop.profit_cny)}</td>
      <td>${shop.auto_sync ? "开启" : "关闭"}</td>
      <td>${esc(shop.last_sync_at || "-")}</td>
      <td>
        <button onclick="syncOzonShop(${shop.id})">立即同步</button>
        <button onclick="deleteOzonShop(${shop.id})">删除</button>
      </td>
    </tr>
  `));
}

async function syncOzonShop(id) {
  toast("正在同步 Ozon 订单...");
  const response = await api(`/api/ozon/shops/${id}/sync`, { method: "POST", timeoutMs: 70000 });
  const data = await responseData(response);
  toast(response.ok ? `同步完成，订单 ${data.imported || 0} 条，退款 ${data.refunds || 0} 条` : data.detail || "同步失败");
  loadOzonShops();
  loadOrders();
  loadRefunds();
  loadDashboard();
}

async function deleteOzonShop(id) {
  await api(`/api/ozon/shops/${id}`, { method: "DELETE" });
  loadOzonShops();
}

async function loadFeeRules() {
  if (!$("platformFeesTable")) return;
  const platform = await api("/api/fees/platform");
  if (platform.ok) {
    const rows = await platform.json();
    table($("platformFeesTable"), ["名称", "类目", "SKU 包含", "佣金率", "额外税率", "状态", "操作"], rows.map(rule => `
      <tr>
        <td>${esc(rule.name)}</td>
        <td>${esc(rule.category || "默认")}</td>
        <td>${esc(rule.sku_pattern || "默认")}</td>
        <td>${(Number(rule.commission_rate) * 100).toFixed(2)}%</td>
        <td>${(Number(rule.tax_rate) * 100).toFixed(2)}%</td>
        <td>${rule.active ? "启用" : "停用"}</td>
        <td><button onclick="deletePlatformFeeRule(${rule.id})">删除</button></td>
      </tr>
    `));
  }
  const logistics = await api("/api/fees/logistics");
  if (logistics.ok) {
    const rows = await logistics.json();
    table($("logisticsTable"), ["名称", "来源", "类目", "SKU 包含", "重量 kg", "计费公式", "状态", "操作"], rows.map(rule => `
      <tr>
        <td>${esc(rule.name)}</td>
        <td>${esc(rule.source_sheet || "手动")}</td>
        <td>${esc(rule.category || "默认")}</td>
        <td>${esc(rule.sku_pattern || "默认")}</td>
        <td>${money(rule.min_weight_kg)} - ${money(rule.max_weight_kg)}</td>
        <td>${rule.formula_text ? esc(rule.formula_text) : `¥${money(rule.base_fee_cny)} + ¥${money(rule.fee_per_kg_cny)}/kg`}</td>
        <td>${rule.active ? "启用" : "停用"}</td>
        <td><button onclick="deleteLogisticsRule(${rule.id})">删除</button></td>
      </tr>
    `));
  }
}

async function addPlatformFeeRule() {
  const body = {
    name: $("feeName").value.trim() || "平台税规则",
    category: $("feeCategory").value.trim(),
    sku_pattern: $("feeSku").value.trim(),
    commission_rate: Number($("feeCommission").value || 0.15),
    tax_rate: Number($("feeTax").value || 0),
    active: true
  };
  const response = await api("/api/fees/platform", { method: "POST", body: JSON.stringify(body) });
  const data = await responseData(response);
  toast(response.ok ? "平台税规则已保存" : data.detail || "保存失败");
  if (response.ok) {
    ["feeName", "feeCategory", "feeSku", "feeCommission", "feeTax"].forEach(id => $(id).value = "");
    loadFeeRules();
  }
}

async function addLogisticsRule() {
  const body = {
    name: $("lgName").value.trim() || "物流规则",
    category: $("lgCategory").value.trim(),
    sku_pattern: $("lgSku").value.trim(),
    min_weight_kg: Number($("lgMin").value || 0),
    max_weight_kg: Number($("lgMax").value || 999999),
    base_fee_cny: Number($("lgBase").value || 0),
    fee_per_kg_cny: Number($("lgPerKg").value || 0),
    fee_cny: Number($("lgFee").value || 0),
    active: true
  };
  const response = await api("/api/fees/logistics", { method: "POST", body: JSON.stringify(body) });
  const data = await responseData(response);
  toast(response.ok ? "物流规则已保存" : data.detail || "保存失败");
  if (response.ok) {
    ["lgName", "lgCategory", "lgSku", "lgMin", "lgMax", "lgBase", "lgPerKg", "lgFee"].forEach(id => $(id).value = "");
    loadFeeRules();
  }
}

async function deletePlatformFeeRule(id) {
  await api(`/api/fees/platform/${id}`, { method: "DELETE" });
  loadFeeRules();
}

async function deleteLogisticsRule(id) {
  await api(`/api/fees/logistics/${id}`, { method: "DELETE" });
  loadFeeRules();
}

async function addOrder() {
  if (!$("odNo").value.trim()) return toast("请输入订单号");

  const body = {
    month: $("odMonth").value,
    order_no: $("odNo").value.trim(),
    status: $("odStatus").value,
    product: $("odProduct").value.trim(),
    sku: $("odSku").value.trim(),
    category: $("odCategory").value.trim(),
    quantity: +$("odQty").value || 1,
    price_rub: +$("odPrice").value || 0,
    cost_cny: +$("odCost").value || 0,
    weight_kg: +$("odWeight").value || 0,
    shipping_cny: +$("odShip").value || 0,
    commission_rate: $("odComm").value.trim() ? Number($("odComm").value) : null
  };
  const response = await api("/api/orders", {
    method: "POST",
    body: JSON.stringify(body)
  });
  const data = await response.json();
  toast(response.ok ? `订单已保存，预计利润 ¥${money(data.profit_cny)}` : data.detail || "保存失败");
  if (response.ok) {
    ["odNo", "odProduct", "odSku", "odCategory", "odPrice", "odCost", "odWeight", "odShip"].forEach(id => $(id).value = "");
    loadOrders();
    loadDashboard();
  }
}

async function loadOrders() {
  const response = await api("/api/orders");
  if (!response.ok) return;
  const rows = await response.json();
  cachedOrders = rows;
  table($("ordersTable"), ["月份", "订单号", "状态", "商品", "类目", "SKU", "数量", "售价 ₽", "平台税 ¥", "物流 ¥", "退款 ¥", "利润 ¥", "详情"], rows.map(order => `
    <tr>
      <td>${esc(order.month)}</td>
      <td>${esc(order.order_no)}</td>
      <td><span class="badge">${esc(order.status)}</span></td>
      <td>${esc(order.product)}</td>
      <td>${esc(order.category || "-")}</td>
      <td>${esc(order.sku)}</td>
      <td>${esc(order.quantity)}</td>
      <td>${money(order.price_rub)}</td>
      <td>${money(order.platform_fee_cny)}</td>
      <td>${money(order.logistics_fee_cny || order.shipping_cny)}</td>
      <td>${money(order.refund_cny)}</td>
      <td>${money(order.profit_cny)}</td>
      <td><button onclick="showOrderDetail(${order.id})">查看</button></td>
    </tr>
  `));
}

async function showOrderDetail(id) {
  let order = cachedOrders.find(item => Number(item.id) === Number(id));
  const response = await api(`/api/orders/${id}`);
  if (response.ok) order = await response.json();
  if (!order) return;
  const rawSource = order.raw_data !== undefined ? order.raw_data : order.raw_json;
  const raw = rawSource ? (() => {
    try { return typeof rawSource === "string" ? JSON.stringify(JSON.parse(rawSource), null, 2) : JSON.stringify(rawSource, null, 2); } catch { return String(rawSource); }
  })() : "无";
  const categoryFee = order.category_fee ? `${money(order.category_fee.percent)}% (${order.category_fee.scheme || "rFBS"})` : "-";
  const logisticsRule = order.logistics_rule ? `${order.logistics_rule.name || ""} ${order.logistics_rule.formula_text || ""}`.trim() : "-";
  $("orderDetailBody").innerHTML = `
    <div class="detail-grid">
      <div><span>订单号</span><b>${esc(order.order_no)}</b></div>
      <div><span>店铺ID</span><b>${esc(order.shop_id || "-")}</b></div>
      <div><span>状态</span><b>${esc(order.status)}</b></div>
      <div><span>同步时间</span><b>${esc(order.synced_at || order.created_at || "-")}</b></div>
      <div><span>商品</span><b>${esc(order.product)}</b></div>
      <div><span>SKU</span><b>${esc(order.sku)}</b></div>
      <div><span>类目</span><b>${esc(order.category || "-")}</b></div>
      <div><span>重量</span><b>${money(order.weight_kg, 3)} kg</b></div>
      <div><span>收入</span><b>¥${money(order.revenue_cny)}</b></div>
      <div><span>平台费</span><b>¥${money(order.platform_fee_cny)}</b></div>
      <div><span>平台税</span><b>¥${money(order.tax_cny)}</b></div>
      <div><span>物流费</span><b>¥${money(order.logistics_fee_cny || order.shipping_cny)}</b></div>
      <div><span>退款扣减</span><b>¥${money(order.refund_cny)}</b></div>
      <div><span>采购成本</span><b>¥${money(order.cost_cny)}</b></div>
      <div><span>利润</span><b>¥${money(order.profit_cny)}</b></div>
      <div><span>匹配平台费率</span><b>${esc(categoryFee)}</b></div>
      <div><span>匹配物流规则</span><b>${esc(logisticsRule)}</b></div>
    </div>
    ${(order.refunds || []).length ? `<h4>退款记录</h4><pre class="ai-box">${esc(JSON.stringify(order.refunds, null, 2))}</pre>` : ""}
    <pre class="ai-box">${esc(raw)}</pre>
  `;
  $("orderDrawer").classList.remove("hidden");
}

function closeOrderDetail() {
  $("orderDrawer").classList.add("hidden");
}

async function loadRefunds() {
  if (!$("refundsTable")) return;
  const response = await api("/api/refunds/alerts");
  if (!response.ok) return;
  const data = await response.json();
  $("refundAlert").innerText = data.count
    ? `已识别 ${data.count} 笔退款/退货，累计扣减 ¥${money(data.amount_cny)}。`
    : "暂无退款提醒";
  table($("refundsTable"), ["订单", "商品", "退款号", "状态", "金额 ₽", "扣减 ¥", "原因", "时间"], (data.items || []).map(item => `
    <tr>
      <td>${esc(item.order_no || item.posting_number || "-")}</td>
      <td>${esc(item.product || "-")}</td>
      <td>${esc(item.refund_no)}</td>
      <td><span class="badge danger">${esc(item.status)}</span></td>
      <td>${money(item.amount_rub)}</td>
      <td>${money(item.amount_cny)}</td>
      <td>${esc(item.reason || "-")}</td>
      <td>${esc(item.synced_at || item.created_at || "-")}</td>
    </tr>
  `));
}

async function loadSourcing() {
  if (!$("listingJobsTable")) return;
  loadMarketplaceAccounts();
  loadSourcingProducts();
  loadListingJobs();
  loadCatalogFees();
}

async function matchSourcingKeyword() {
  const keyword = $("scKeyword").value.trim();
  if (!keyword) return toast("请输入商品关键词");
  const response = await api("/api/catalog/match", {
    method: "POST",
    body: JSON.stringify({ keyword })
  });
  const data = await responseData(response);
  if (!response.ok) return toast(data.detail || "匹配失败");
  if (!data.matches.length) {
    $("categoryMatchBox").innerText = "没有匹配到类目，可以在关键词库继续补充。";
    return;
  }
  const first = data.matches[0];
  $("jobName").value = keyword;
  $("jobCategory").value = first.category || "";
  $("jobKeywords").value = data.matches.map(item => item.keyword).join("、");
  $("jobCost").value = $("scCost").value;
  $("jobWeight").value = $("scWeight").value;
  $("jobPrice").value = $("scPrice").value;
  $("categoryMatchBox").innerHTML = data.matches.map(item => {
    const fee = item.fee || {};
    const rate = fee.category ? `≤1500: rFBS ${money(fee.r_fbs_1500)}% / FBP ${money(fee.fbp_1500)}%，≤5000: rFBS ${money(fee.r_fbs_5000)}% / FBP ${money(fee.fbp_5000)}%，>5000: rFBS ${money(fee.r_fbs_above)}% / FBP ${money(fee.fbp_above)}%` : "暂无费率";
    return `<div class="match-item"><b>${esc(item.keyword)}</b><span>${esc(item.category)}</span><small>${esc(item.note || "")}</small><p>${rate}</p></div>`;
  }).join("");
}

function open1688Search() {
  const keyword = $("scKeyword").value.trim() || $("jobName").value.trim();
  if (!keyword) return toast("请输入选品关键词");
  window.open(`https://s.1688.com/selloffer/offer_search.htm?keywords=${encodeURIComponent(keyword)}`, "_blank");
}

function openTaobaoLogin() {
  window.open("https://login.taobao.com/member/login.jhtml", "_blank");
}

async function loadMarketplaceAccounts() {
  const response = await api("/api/marketplace/accounts");
  if (!response.ok) return;
  const rows = await response.json();
  table($("marketplaceTable"), ["平台", "账号", "状态", "备注", "更新时间"], rows.map(item => `
    <tr>
      <td>${esc(item.platform)}</td>
      <td>${esc(item.account_name || "-")}</td>
      <td><span class="badge">${esc(item.status)}</span></td>
      <td>${esc(item.note || "-")}</td>
      <td>${esc(item.updated_at)}</td>
    </tr>
  `));
}

async function saveMarketplaceAccount() {
  const response = await api("/api/marketplace/accounts", {
    method: "POST",
    body: JSON.stringify({
      platform: $("mpPlatform").value,
      account_name: $("mpAccount").value.trim(),
      status: $("mpStatus").value,
      note: $("mpNote").value.trim()
    })
  });
  const data = await responseData(response);
  toast(response.ok ? "平台账号状态已保存" : data.detail || "保存失败");
  if (response.ok) loadMarketplaceAccounts();
}

async function loadCatalogFees() {
  if (!$("catalogFeesTable")) return;
  const q = $("feeSearch")?.value.trim() || "";
  const response = await api(`/api/catalog/fees${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  if (!response.ok) return;
  const rows = await response.json();
  table($("catalogFeesTable"), ["模块", "类目", "≤1500 rFBS", "≤1500 FBP", "≤5000 rFBS", "≤5000 FBP", ">5000 rFBS", ">5000 FBP"], rows.map(item => `
    <tr>
      <td>${esc(item.module)}</td>
      <td>${esc(item.category)}</td>
      <td>${money(item.r_fbs_1500)}%</td>
      <td>${money(item.fbp_1500)}%</td>
      <td>${money(item.r_fbs_5000)}%</td>
      <td>${money(item.fbp_5000)}%</td>
      <td>${money(item.r_fbs_above)}%</td>
      <td>${money(item.fbp_above)}%</td>
    </tr>
  `));
}

async function generateProductImage() {
  if (!$("jobName").value.trim() && !$("imagePrompt").value.trim()) return toast("请输入商品名或图片提示词");
  $("imagePreview").innerHTML = `<div class="panel-empty">AI 正在生成图片...</div>`;
  const response = await api("/api/ai/image", {
    method: "POST",
    body: JSON.stringify({
      product_name: $("jobName").value.trim(),
      prompt: $("imagePrompt").value.trim() || $("jobKeywords").value.trim()
    }),
    timeoutMs: 100000
  });
  const data = await responseData(response);
  if (!response.ok) {
    $("imagePreview").innerHTML = `<div class="panel-empty">${esc(data.detail || "生成失败")}</div>`;
    return;
  }
  if (data.image_url) {
    $("jobImageUrl").value = data.image_url;
    $("imagePreview").innerHTML = `<img src="${esc(data.image_url)}" alt="AI生成图片"/>`;
  } else if (data.b64_json) {
    const src = `data:image/png;base64,${data.b64_json}`;
    $("jobImageUrl").value = src;
    $("imagePreview").innerHTML = `<img src="${src}" alt="AI生成图片"/>`;
  } else {
    $("imagePreview").innerHTML = `<pre class="ai-box">${esc(JSON.stringify(data.raw || data, null, 2))}</pre>`;
  }
}

async function generateSourcingListing() {
  if (!$("jobName").value.trim()) return toast("请输入商品名称");
  $("jobListing").innerText = "正在生成 Listing...";
  const response = await api("/api/ai/listing", {
    method: "POST",
    body: JSON.stringify({
      product_name: $("jobName").value.trim(),
      category: $("jobCategory").value.trim(),
      keywords: $("jobKeywords").value.trim(),
      price_rub: $("jobPrice").value
    }),
    timeoutMs: 60000
  });
  const data = await responseData(response);
  $("jobListing").innerText = response.ok ? data.listing : data.detail || JSON.stringify(data, null, 2);
}

async function saveListingJob() {
  if (!$("jobName").value.trim()) return toast("请输入商品名称");
  const response = await api("/api/listing/jobs", {
    method: "POST",
    body: JSON.stringify({
      product_name: $("jobName").value.trim(),
      source: $("jobSourceUrl").value.includes("taobao") ? "taobao" : "1688",
      source_url: $("jobSourceUrl").value.trim(),
      category: $("jobCategory").value.trim(),
      keywords: $("jobKeywords").value.trim(),
      cost_cny: Number($("jobCost").value || 0),
      weight_kg: Number($("jobWeight").value || 0),
      price_rub: Number($("jobPrice").value || 0),
      image_url: $("jobImageUrl").value.trim(),
      generated_listing: $("jobListing").innerText,
      ozon_shop_id: $("jobShop").value ? Number($("jobShop").value) : null
    })
  });
  const data = await responseData(response);
  toast(response.ok ? "上品任务已保存" : data.detail || "保存失败");
  if (response.ok) loadListingJobs();
}

async function loadListingJobs() {
  const response = await api("/api/listing/jobs");
  if (!response.ok) return;
  const rows = await response.json();
  table($("listingJobsTable"), ["商品", "来源", "类目", "成本 ¥", "重量 kg", "售价 ₽", "状态", "操作"], rows.map(job => `
    <tr>
      <td>${esc(job.product_name)}</td>
      <td>${job.source_url ? `<a href="${esc(job.source_url)}" target="_blank">${esc(job.source || "来源")}</a>` : esc(job.source || "-")}</td>
      <td>${esc(job.category || "-")}</td>
      <td>${money(job.cost_cny)}</td>
      <td>${money(job.weight_kg, 3)}</td>
      <td>${money(job.price_rub)}</td>
      <td><span class="badge">${esc(job.ozon_status)}</span></td>
      <td><button onclick="publishListingJob(${job.id})">一键上架 Ozon</button></td>
    </tr>
  `));
}

async function publishListingJob(id) {
  const shopId = $("jobShop").value ? Number($("jobShop").value) : null;
  const response = await api(`/api/listing/jobs/${id}/publish`, {
    method: "POST",
    body: JSON.stringify({ shop_id: shopId })
  });
  const data = await responseData(response);
  toast(response.ok ? "已提交 Ozon 上品接口" : data.detail || "提交失败");
  loadListingJobs();
}

async function addProduct() {
  if (!$("pdTitle").value.trim()) return toast("请输入商品名称");

  const body = {
    title: $("pdTitle").value.trim(),
    category: $("pdCategory").value.trim(),
    cost_cny: +$("pdCost").value || 0,
    weight_kg: +$("pdWeight").value || 0,
    price_rub: +$("pdPrice").value || 0,
    stock: +$("pdStock").value || 0
  };
  const response = await api("/api/products", {
    method: "POST",
    body: JSON.stringify(body)
  });
  toast(response.ok ? "商品已保存" : "保存失败");
  if (response.ok) {
    ["pdTitle", "pdCategory", "pdCost", "pdWeight", "pdPrice", "pdStock"].forEach(id => $(id).value = "");
    loadProducts();
    loadDashboard();
  }
}

async function loadProducts() {
  const response = await api("/api/products");
  if (!response.ok) return;
  const rows = await response.json();
  table($("productsTable"), ["商品", "类目", "成本 ¥", "重量 kg", "售价 ₽", "库存", "状态", "操作"], rows.map(product => `
    <tr>
      <td>${esc(product.title)}</td>
      <td>${esc(product.category)}</td>
      <td>${money(product.cost_cny)}</td>
      <td>${money(product.weight_kg, 3)}</td>
      <td>${money(product.price_rub)}</td>
      <td>${esc(product.stock)}</td>
      <td>${esc(product.status)}</td>
      <td><button onclick="delProduct(${product.id})">删除</button></td>
    </tr>
  `));
}

async function delProduct(id) {
  await api("/api/products/" + id, { method: "DELETE" });
  loadProducts();
  loadDashboard();
}

async function loadAISettings() {
  const response = await api("/api/ai/settings");
  if (!response.ok) return;
  const data = await response.json();
  $("aiBase").value = data.base_url || "";
  $("aiModel").value = data.model || "";
  $("aiImage").value = data.image_model || "";
  $("aiKey").placeholder = data.api_key_set ? "API Key 已保存，留空可保持不变" : "豆包 API Key，ark-...";
  $("aiStatus").innerText = data.api_key_set ? "API Key 已保存，请确认文字模型 Endpoint 已填写" : "尚未保存 API Key";
}

async function saveAISettings(silent = false) {
  if (!$("aiBase").value.trim()) {
    if (!silent) toast("请填写 Base URL");
    return false;
  }
  if (!$("aiModel").value.trim()) {
    const message = "请填写文字模型 Endpoint，例如 ep-xxxxxxxx。图片模型不能用于聊天。";
    $("aiAnswer").innerText = message;
    if (!silent) toast(message);
    return false;
  }
  const body = {
    api_key: $("aiKey").value.trim(),
    base_url: $("aiBase").value.trim(),
    model: $("aiModel").value.trim(),
    image_model: $("aiImage").value.trim()
  };
  const response = await api("/api/ai/settings", {
    method: "POST",
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) {
    if (!silent) toast(data.detail || "保存失败");
    return false;
  }
  $("aiKey").value = "";
  $("aiStatus").innerText = "AI 配置已保存";
  if (!silent) toast("AI 配置已保存");
  loadAISettings();
  return true;
}

async function testAISettings() {
  const saved = await saveAISettings(true);
  if (!saved) return;
  $("aiStatus").innerText = "正在测试连接...";
  try {
    const response = await api("/api/ai/test", { method: "POST", timeoutMs: 45000 });
    const data = await responseData(response);
    $("aiStatus").innerText = response.ok ? "连接成功" : "连接失败";
    $("aiAnswer").innerText = response.ok ? (data.answer || "连接成功") : data.detail || JSON.stringify(data, null, 2);
  } catch (error) {
    $("aiStatus").innerText = "连接超时";
    $("aiAnswer").innerText = "连接豆包超时或被浏览器中断，请检查网络、防火墙、代理和 Base URL。";
  }
}

async function askAI() {
  if (!$("aiMsg").value.trim()) return toast("请输入要咨询的问题");
  const saved = await saveAISettings(true);
  if (!saved) return;
  $("aiAnswer").innerText = "豆包正在思考中...";
  try {
    const response = await api("/api/doubao/chat", {
      method: "POST",
      body: JSON.stringify({ message: $("aiMsg").value }),
      timeoutMs: 45000
    });
    const data = await responseData(response);
    $("aiAnswer").innerText = response.ok ? data.answer : data.detail || JSON.stringify(data, null, 2);
  } catch (error) {
    $("aiAnswer").innerText = "连接豆包超时或被浏览器中断，请检查网络、防火墙、代理和 Base URL。";
  }
}

async function generateListing() {
  if (!$("lsName").value.trim()) return toast("请输入商品名称");
  $("listingResult").innerText = "正在生成...";
  const body = {
    product_name: $("lsName").value,
    category: $("lsCat").value,
    keywords: $("lsKeywords").value,
    price_rub: $("lsPrice").value
  };
  const response = await api("/api/ai/listing", {
    method: "POST",
    body: JSON.stringify(body)
  });
  const data = await response.json();
  $("listingResult").innerText = response.ok ? data.listing : data.detail || JSON.stringify(data, null, 2);
}

async function addTicket() {
  if (!$("tkMessage").value.trim()) return toast("请输入客户消息");
  const response = await api("/api/tickets", {
    method: "POST",
    body: JSON.stringify({ customer: $("tkCustomer").value, message: $("tkMessage").value })
  });
  toast(response.ok ? "消息已新增" : "新增失败");
  if (response.ok) {
    $("tkMessage").value = "";
    loadTickets();
    loadDashboard();
  }
}

async function loadTickets() {
  const response = await api("/api/tickets");
  if (!response.ok) return;
  const rows = await response.json();
  $("ticketsList").innerHTML = rows.length ? rows.map(ticket => `
    <div class="ticket">
      <b>${esc(ticket.customer)}</b>
      <small>${esc(ticket.created_at)}</small>
      <p>${esc(ticket.message)}</p>
      <button onclick="aiReply(${ticket.id})">豆包生成回复</button>
      ${ticket.ai_reply ? `<pre class="ai-box">${esc(ticket.ai_reply)}</pre>` : ""}
    </div>
  `).join("") : `<div class="empty panel-empty">暂无消息</div>`;
}

async function aiReply(id) {
  const response = await api(`/api/tickets/${id}/ai-reply`, { method: "POST" });
  const data = await response.json();
  toast(response.ok ? "已生成回复" : data.detail || "生成失败");
  loadTickets();
}

async function loadAdmin() {
  const overview = await api("/api/admin/overview");
  if (overview.ok) {
    const data = await overview.json();
    $("adUsers").innerText = money(data.users, 0);
    $("adOrders").innerText = money(data.orders, 0);
    $("adProducts").innerText = money(data.products, 0);
    $("auditLogs").innerHTML = data.logs.length ? data.logs.map(log => `
      <p><b>${esc(log.action)}</b> · ${esc(log.username || "-")} · ${esc(log.detail || "")} <small>${esc(log.created_at)}</small></p>
    `).join("") : `<div class="empty panel-empty">暂无日志</div>`;
  }

  const users = await api("/api/admin/users");
  if (users.ok) {
    const rows = await users.json();
    table($("adminUsers"), ["ID", "用户名", "邮箱", "角色", "状态", "操作"], rows.map(user => `
      <tr>
        <td>${user.id}</td>
        <td>${esc(user.username)}</td>
        <td>${esc(user.email)}</td>
        <td>${esc(user.role)}</td>
        <td>${esc(user.status)}</td>
        <td>
          <button onclick="setRole(${user.id}, '${user.role === "admin" ? "user" : "admin"}')">切换角色</button>
          <button onclick="setStatus(${user.id}, '${user.status === "active" ? "disabled" : "active"}')">启停</button>
        </td>
      </tr>
    `));
  }
}

async function adminCreateUser() {
  const username = $("newUsername").value.trim();
  const email = $("newEmail").value.trim();
  const password = $("newPassword").value;
  if (!username || !email || !password) return toast("请填写用户名、邮箱和初始密码");
  const response = await api("/api/admin/users", {
    method: "POST",
    body: JSON.stringify({
      username,
      email,
      password,
      role: $("newRole").value
    })
  });
  const data = await responseData(response);
  toast(response.ok ? "账户已开通" : data.detail || "开通失败");
  if (response.ok) {
    ["newUsername", "newEmail", "newPassword"].forEach(id => $(id).value = "");
    loadAdmin();
  }
}

async function saveAppSettings() {
  const body = {
    app_name: $("setAppName").value.trim(),
    tagline: $("setTagline").value.trim(),
    exchange_rate: Number($("setRate").value || 0.078),
    support_email: $("setEmail").value.trim()
  };
  if (!body.app_name) return toast("请输入系统名称");
  if (!body.exchange_rate || body.exchange_rate <= 0) return toast("请输入正确汇率");

  const response = await api("/api/admin/app/settings", {
    method: "POST",
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) return toast(data.detail || "保存失败");

  appConfig = data.settings;
  applyAppSettings();
  fillSettingsForm();
  toast("系统设置已保存");
}

async function setRole(id, role) {
  await api(`/api/admin/users/${id}/role`, {
    method: "POST",
    body: JSON.stringify({ role })
  });
  loadAdmin();
}

async function setStatus(id, status) {
  await api(`/api/admin/users/${id}/status`, {
    method: "POST",
    body: JSON.stringify({ status })
  });
  loadAdmin();
}

init();

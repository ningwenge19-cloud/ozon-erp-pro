CREATE TABLE IF NOT EXISTS users(
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_settings(
  id INTEGER PRIMARY KEY CHECK(id=1),
  api_key TEXT,
  base_url TEXT,
  model TEXT,
  image_model TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS app_settings(
  id INTEGER PRIMARY KEY CHECK(id=1),
  app_name TEXT NOT NULL,
  tagline TEXT NOT NULL,
  exchange_rate DOUBLE PRECISION NOT NULL,
  support_email TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS ozon_settings(
  user_id INTEGER PRIMARY KEY,
  client_id TEXT,
  api_key TEXT,
  sync_type TEXT DEFAULT 'FBS / rFBS',
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS ozon_shops(
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  shop_name TEXT NOT NULL,
  client_id TEXT NOT NULL,
  api_key TEXT NOT NULL,
  sync_type TEXT DEFAULT 'FBS',
  auto_sync INTEGER DEFAULT 1,
  last_sync_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS platform_fee_rules(
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  category TEXT DEFAULT '',
  sku_pattern TEXT DEFAULT '',
  commission_rate DOUBLE PRECISION DEFAULT 0.15,
  tax_rate DOUBLE PRECISION DEFAULT 0,
  active INTEGER DEFAULT 1,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS logistics_rules(
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  category TEXT DEFAULT '',
  sku_pattern TEXT DEFAULT '',
  channel_name TEXT DEFAULT '',
  source_sheet TEXT DEFAULT '',
  formula_text TEXT DEFAULT '',
  delivery_days TEXT DEFAULT '',
  base_fee_cny DOUBLE PRECISION DEFAULT 0,
  fee_per_kg_cny DOUBLE PRECISION DEFAULT 0,
  min_weight_kg DOUBLE PRECISION DEFAULT 0,
  max_weight_kg DOUBLE PRECISION DEFAULT 999999,
  fee_cny DOUBLE PRECISION DEFAULT 0,
  active INTEGER DEFAULT 1,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_logs(
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  shop_id INTEGER,
  status TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders(
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  shop_id INTEGER,
  posting_number TEXT,
  month TEXT,
  order_no TEXT,
  status TEXT,
  product TEXT,
  sku TEXT,
  category TEXT DEFAULT '',
  quantity INTEGER DEFAULT 1,
  price_rub DOUBLE PRECISION DEFAULT 0,
  cost_cny DOUBLE PRECISION DEFAULT 0,
  weight_kg DOUBLE PRECISION DEFAULT 0,
  shipping_cny DOUBLE PRECISION DEFAULT 0,
  commission_rate DOUBLE PRECISION DEFAULT 0.15,
  revenue_cny DOUBLE PRECISION DEFAULT 0,
  platform_fee_cny DOUBLE PRECISION DEFAULT 0,
  tax_cny DOUBLE PRECISION DEFAULT 0,
  logistics_fee_cny DOUBLE PRECISION DEFAULT 0,
  profit_cny DOUBLE PRECISION DEFAULT 0,
  fee_rule_id INTEGER,
  logistics_rule_id INTEGER,
  raw_json TEXT,
  created_at TEXT NOT NULL,
  synced_at TEXT
);

CREATE TABLE IF NOT EXISTS products(
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  category TEXT,
  cost_cny DOUBLE PRECISION DEFAULT 0,
  weight_kg DOUBLE PRECISION DEFAULT 0,
  price_rub DOUBLE PRECISION DEFAULT 0,
  stock INTEGER DEFAULT 0,
  status TEXT DEFAULT 'draft',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets(
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  customer TEXT,
  message TEXT,
  status TEXT DEFAULT 'open',
  ai_reply TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs(
  id SERIAL PRIMARY KEY,
  user_id INTEGER,
  action TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS category_keyword_rules(
  id SERIAL PRIMARY KEY,
  keyword TEXT UNIQUE NOT NULL,
  category TEXT NOT NULL,
  note TEXT DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS category_fee_matrix(
  id SERIAL PRIMARY KEY,
  module TEXT NOT NULL,
  category TEXT UNIQUE NOT NULL,
  r_fbs_1500 DOUBLE PRECISION DEFAULT 0,
  fbp_1500 DOUBLE PRECISION DEFAULT 0,
  r_fbs_5000 DOUBLE PRECISION DEFAULT 0,
  fbp_5000 DOUBLE PRECISION DEFAULT 0,
  r_fbs_above DOUBLE PRECISION DEFAULT 0,
  fbp_above DOUBLE PRECISION DEFAULT 0,
  match_method TEXT DEFAULT 'category+price+scheme',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listing_jobs(
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  product_name TEXT NOT NULL,
  source TEXT DEFAULT '',
  source_url TEXT DEFAULT '',
  category TEXT DEFAULT '',
  keywords TEXT DEFAULT '',
  cost_cny DOUBLE PRECISION DEFAULT 0,
  weight_kg DOUBLE PRECISION DEFAULT 0,
  price_rub DOUBLE PRECISION DEFAULT 0,
  image_url TEXT DEFAULT '',
  generated_listing TEXT DEFAULT '',
  ozon_shop_id INTEGER,
  ozon_status TEXT DEFAULT 'draft',
  raw_json TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS marketplace_accounts(
  user_id INTEGER NOT NULL,
  platform TEXT NOT NULL,
  account_name TEXT DEFAULT '',
  status TEXT DEFAULT 'not_logged_in',
  note TEXT DEFAULT '',
  updated_at TEXT NOT NULL,
  PRIMARY KEY(user_id, platform)
);

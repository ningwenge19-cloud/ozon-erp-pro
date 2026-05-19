import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import smtplib
import ssl
import threading
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ozon_erp.db"
FRONTEND_DIR = ROOT.parent / "frontend"
APP_NAME = "Ozon SaaS ERP"
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL", "")
USE_POSTGRES = DATABASE_URL.lower().startswith(("postgres://", "postgresql://"))
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-in-railway")
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_BASE_URL = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "")
DOUBAO_IMAGE_MODEL = os.getenv("DOUBAO_IMAGE_MODEL", "doubao-seedream-3-0-t2i-250415")
OZON_API_BASE_URL = os.getenv("OZON_API_BASE_URL", "https://api-seller.ozon.ru")
DEFAULT_EXCHANGE_RATE = float(os.getenv("EXCHANGE_RATE_RUB_CNY", "0.078"))
AUTO_SYNC_SECONDS = int(os.getenv("AUTO_SYNC_SECONDS", "900"))
CORS_ORIGINS = [item.strip() for item in os.getenv("CORS_ORIGINS", "*").split(",") if item.strip()]
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "")
APP_ENV = os.getenv("APP_ENV", "local").lower()
REQUIRE_EMAIL_VERIFICATION = os.getenv("REQUIRE_EMAIL_VERIFICATION", "1") == "1"
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "noreply@ozon-erp.local")
SMTP_TLS = os.getenv("SMTP_TLS", "1") == "1"

if USE_POSTGRES:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:
        raise RuntimeError("DATABASE_URL is set, but psycopg2-binary is not installed.") from exc

CATEGORY_KEYWORDS = [
    ("帐篷", "运动和休闲用品", "露营/户外"), ("天幕", "运动和休闲用品", "露营/户外"), ("睡袋", "运动和休闲用品", "露营/户外"),
    ("登山杖", "运动和休闲用品", "运动户外"), ("瑜伽", "运动和休闲用品", "运动用品"), ("健身", "运动和休闲用品", "运动用品"),
    ("泳池", "蹦床、游泳池和立式桨板", "水上用品"), ("蹦床", "蹦床、游泳池和立式桨板", "户外玩具"), ("桨板", "蹦床、游泳池和立式桨板", "水上运动"),
    ("运动营养", "运动营养", "营养食品"), ("蛋白粉", "运动营养", "运动营养"), ("文具", "兴趣、创意与文具", "办公/文具"), ("画笔", "兴趣、创意与文具", "兴趣创意"), ("手工", "兴趣、创意与文具", "兴趣创意"), ("书", "书籍", "书籍"),
    ("耳机", "音频和视频设备配件", "音频配件"), ("音箱", "音频和视频设备配件", "音频设备"), ("麦克风", "音频和视频设备配件", "音频配件"),
    ("手机壳", "电子产品配饰", "手机配件"), ("手机膜", "电子产品配饰", "手机配件"), ("充电器", "电子产品配饰", "电子配件"), ("数据线", "电子产品配饰", "电子配件"), ("支架", "电子产品配饰", "电子配件"),
    ("苹果", "苹果设备", "Apple设备"), ("iphone", "苹果设备", "Apple设备"), ("ipad", "苹果设备", "Apple设备"), ("三星", "三星智能手机和平板电脑", "三星设备"),
    ("平板", "智能手机和平板电脑", "数码"), ("手机", "智能手机和平板电脑", "数码"), ("智能手表", "智能手表与健身手环", "穿戴设备"), ("手环", "智能手表与健身手环", "穿戴设备"),
    ("显示器", "显示器", "显示器"), ("电脑", "电脑设备配件", "电脑/配件"), ("笔记本", "笔记本电脑", "电脑"), ("键盘", "电脑外设设备及耗材", "外设"), ("鼠标", "电脑外设设备及耗材", "外设"),
    ("打印机", "办公电脑设备、收银及仓储设备", "办公设备"), ("摄像机", "游戏主机及配件、摄影器材", "摄影器材"), ("相机", "游戏主机及配件、摄影器材", "摄影器材"), ("游戏机", "游戏主机及配件、摄影器材", "游戏主机"),
    ("家电", "家用电器", "家电"), ("电视", "电视机", "电视"), ("冰箱", "非内置式大型家用电器", "大家电"), ("洗衣机", "非内置式大型家用电器", "大家电"), ("吸尘器", "戴森设备", "清洁电器"), ("戴森", "戴森设备", "品牌设备"),
    ("美容仪", "美容设备", "美容电器"), ("剃须刀", "美容设备", "美容设备"), ("化妆", "美容与健康", "美容"), ("护肤", "美容与健康", "美容"), ("口红", "美容与健康", "美容"),
    ("牙刷", "专业口腔护理", "口腔护理"), ("冲牙器", "专业口腔护理", "口腔护理"), ("衣服", "服装和配饰", "服饰"), ("连衣裙", "服装和配饰", "服饰"), ("T恤", "服装和配饰", "服饰"), ("外套", "外衣", "外衣"), ("羽绒服", "外衣", "外衣"), ("鞋", "鞋类", "鞋类"),
    ("包", "包装袋", "包袋/包装"), ("收纳", "装饰、清洁与储物", "家居收纳"), ("清洁", "装饰、清洁与储物", "家居清洁"), ("装饰", "装饰、清洁与储物", "家居装饰"),
    ("床品", "住宅和花园", "家居"), ("家具", "家具", "家具"), ("花园", "住宅和花园", "住宅和花园"), ("园艺", "建筑、装修和园艺设备", "园艺设备"),
    ("工具", "手动工具和测量仪器", "工具"), ("卷尺", "手动工具和测量仪器", "测量工具"), ("汽车", "汽车用品", "汽车用品"), ("车载", "汽车用品", "汽车用品"), ("轮胎", "轮胎", "轮胎"),
    ("建材", "建筑和装修", "建筑装修"), ("瓷砖", "装饰材料", "装饰材料"), ("卫浴", "卫浴设备", "卫浴"), ("水龙头", "卫浴设备", "卫浴"), ("滤水", "水过滤器", "水过滤器"), ("净水", "水过滤器", "水过滤器"),
    ("圣诞", "新年装饰用品", "节日装饰"), ("新年", "新年装饰用品", "节日装饰"), ("儿童", "玩具", "儿童用品默认"), ("玩具", "玩具", "玩具"), ("婴儿车", "婴儿推车和汽车安全座椅", "婴儿出行"), ("安全座椅", "婴儿推车和汽车安全座椅", "儿童出行"),
    ("尿布", "儿童卫生用品", "儿童卫生"), ("奶瓶", "儿童餐具", "儿童餐具"), ("儿童餐具", "儿童餐具", "儿童餐具"), ("儿童纺织", "儿童纺织品", "儿童纺织"),
    ("宠物粮", "宠物饲料与农场用品", "宠物食品"), ("猫粮", "宠物饲料与农场用品", "宠物食品"), ("狗粮", "宠物饲料与农场用品", "宠物食品"), ("宠物", "宠物用品", "宠物用品"), ("猫砂", "宠物卫生与护理", "宠物卫生"),
    ("食品", "食品", "食品"), ("零食", "食品", "食品"), ("新鲜", "新鲜食品", "新鲜食品"), ("卫生巾", "个人卫生用品", "个人卫生"), ("纸巾", "个人卫生用品", "个人卫生"), ("隐形眼镜", "隐形眼镜", "隐形眼镜"),
    ("药", "药店", "药品"), ("维生素", "维生素和膳食补充剂", "补充剂"), ("补充剂", "维生素和膳食补充剂", "补充剂"), ("电子烟", "电子烟及加热系统配件", "电子烟配件"), ("矫形", "矫形用品", "矫形"),
]

CATEGORY_FEES = [
    ("药房商品", "药店", 12, 11, 14, 13, 18, 17), ("药房商品", "矫形用品", 12, 11, 17, 16, 17, 16), ("药房商品", "成人用品", 12, 11, 14, 13, 21, 20), ("药房商品", "电子烟及加热系统配件", 12, 11, 24, 23, 24, 23), ("药房商品", "维生素和膳食补充剂", 12, 11, 18, 17, 18, 17),
    ("家居与汽车用品", "装饰、清洁与储物", 12, 11, 14, 13, 18, 17), ("家居与汽车用品", "住宅和花园", 12, 11, 14, 13, 20, 19), ("家居与汽车用品", "汽车用品", 12, 11, 17, 16, 17, 16), ("家居与汽车用品", "手动工具和测量仪器", 12, 11, 17, 16, 17, 16), ("家居与汽车用品", "建筑和装修", 12, 11, 18, 17, 18, 17), ("家居与汽车用品", "家具", 10, 9, 10, 9, 10, 9), ("家居与汽车用品", "轮胎", 10, 9, 10, 9, 10, 9), ("家居与汽车用品", "水过滤器", 12, 11, 17, 16, 17, 16), ("家居与汽车用品", "运动手表", 12, 11, 12, 11, 12, 11),
    ("美容", "服装和配饰", 12, 11, 14, 13, 20.5, 19.5), ("美容", "鞋类", 12, 11, 12, 11, 12, 11), ("美容", "美容与健康", 12, 11, 14, 13, 18, 17), ("美容", "专业口腔护理", 12, 11, 17, 16, 17, 16), ("美容", "外衣", 10, 9, 10, 9, 10, 9),
    ("其它", "包装袋", 10, 9, 10, 9, 10, 9), ("儿童用品", "儿童纺织品", 12, 11, 19, 18, 19, 18), ("儿童用品", "玩具", 12, 11, 14, 13, 17.5, 16.5), ("儿童用品", "婴儿推车和汽车安全座椅", 12, 11, 14, 13, 20, 19), ("儿童用品", "儿童卫生用品", 12, 11, 18, 17, 18, 17),
    ("宠物用品", "宠物饲料与农场用品", 12, 11, 13, 12, 13, 12), ("宠物用品", "宠物用品", 12, 11, 14, 13, 15, 14), ("宠物用品", "宠物卫生与护理", 12, 11, 14, 13, 13, 12),
    ("快速消费品（FMCG）", "食品", 11, 10, 11, 10, 11, 10), ("快速消费品（FMCG）", "新鲜食品", 11, 10, 11, 10, 11, 10), ("快速消费品（FMCG）", "个人卫生用品", 12, 11, 18, 17, 18, 17), ("快速消费品（FMCG）", "隐形眼镜", 12, 11, 18, 17, 18, 17),
    ("爱好与运动", "运动和休闲用品", 12, 11, 19, 18, 19, 18), ("爱好与运动", "兴趣、创意与文具", 12, 11, 14, 13, 16, 15), ("爱好与运动", "书籍", 12, 11, 22, 21, 22, 21), ("爱好与运动", "蹦床、游泳池和立式桨板", 12, 11, 16, 15, 16, 15), ("爱好与运动", "运动营养", 12, 11, 15, 14, 15, 14),
    ("电子产品", "电子产品配饰", 12, 11, 20, 19, 20, 19), ("电子产品", "音频和视频设备配件", 12, 11, 14.5, 13.5, 14.5, 13.5), ("电子产品", "家用电器", 10, 9, 10, 9, 10, 9), ("电子产品", "电视机", 9, 8, 9, 8, 9, 8), ("电子产品", "美容设备", 12, 11, 14, 13, 16, 15), ("电子产品", "智能手机和平板电脑", 11.5, 10.5, 11.5, 10.5, 11.5, 10.5), ("电子产品", "笔记本电脑", 8, 7, 8, 7, 8, 7), ("电子产品", "苹果设备", 7, 6, 7, 6, 7, 6), ("电子产品", "戴森设备", 8, 7, 8, 7, 8, 7),
]

app = FastAPI(title=APP_NAME, version="2.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=False if CORS_ORIGINS == ["*"] else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def conn():
    if USE_POSTGRES:
        kwargs = {}
        if "sslmode=" not in DATABASE_URL.lower():
            kwargs["sslmode"] = os.getenv("PGSSLMODE", "require")
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, **kwargs)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


INSERT_ID_TABLES = {
    "users", "ai_settings", "app_settings", "ozon_shops", "platform_fee_rules",
    "logistics_rules", "sync_logs", "orders", "products", "tickets", "audit_logs",
    "category_keyword_rules", "category_fee_matrix", "listing_jobs",
    "email_verification_codes", "refunds", "sourcing_products",
}


def db_sql(sql: str):
    return sql.replace("?", "%s") if USE_POSTGRES else sql


def insert_table_name(sql: str):
    match = re.match(r"\s*INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.I)
    return match.group(1).lower() if match else ""


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def hash_password(password: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return salt, digest


def verify_password(password: str, salt: str, digest: str):
    return hmac.compare_digest(hash_password(password, salt)[1], digest)


def b64url(data: bytes):
    import base64
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def sign_token(payload: dict):
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {**payload, "exp": int((datetime.utcnow() + timedelta(days=7)).timestamp())}
    body = b64url(json.dumps(header, separators=(",", ":")).encode()) + "." + b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return body + "." + b64url(sig)


def decode_token(token: str):
    import base64
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        body = header_b64 + "." + payload_b64
        expected = b64url(hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, sig_b64):
            raise ValueError("bad signature")
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if payload.get("exp", 0) < int(datetime.utcnow().timestamp()):
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")


def init_postgres_db():
    c = conn()
    cur = c.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password_salt TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS ai_settings(id INTEGER PRIMARY KEY CHECK(id=1), api_key TEXT, base_url TEXT, model TEXT, image_model TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS app_settings(id INTEGER PRIMARY KEY CHECK(id=1), app_name TEXT NOT NULL, tagline TEXT NOT NULL, exchange_rate DOUBLE PRECISION NOT NULL, support_email TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS ozon_settings(user_id INTEGER PRIMARY KEY, client_id TEXT, api_key TEXT, sync_type TEXT DEFAULT 'FBS / rFBS', updated_at TEXT);
    CREATE TABLE IF NOT EXISTS ozon_shops(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, shop_name TEXT NOT NULL, client_id TEXT NOT NULL, api_key TEXT NOT NULL, sync_type TEXT DEFAULT 'FBS', auto_sync INTEGER DEFAULT 1, last_sync_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS platform_fee_rules(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL, category TEXT DEFAULT '', sku_pattern TEXT DEFAULT '', commission_rate DOUBLE PRECISION DEFAULT 0.15, tax_rate DOUBLE PRECISION DEFAULT 0, active INTEGER DEFAULT 1, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS logistics_rules(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL, category TEXT DEFAULT '', sku_pattern TEXT DEFAULT '', channel_name TEXT DEFAULT '', source_sheet TEXT DEFAULT '', formula_text TEXT DEFAULT '', delivery_days TEXT DEFAULT '', base_fee_cny DOUBLE PRECISION DEFAULT 0, fee_per_kg_cny DOUBLE PRECISION DEFAULT 0, min_weight_kg DOUBLE PRECISION DEFAULT 0, max_weight_kg DOUBLE PRECISION DEFAULT 999999, fee_cny DOUBLE PRECISION DEFAULT 0, active INTEGER DEFAULT 1, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sync_logs(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, shop_id INTEGER, status TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orders(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, shop_id INTEGER, posting_number TEXT, month TEXT, order_no TEXT, status TEXT, product TEXT, sku TEXT, category TEXT DEFAULT '', quantity INTEGER DEFAULT 1, price_rub DOUBLE PRECISION DEFAULT 0, cost_cny DOUBLE PRECISION DEFAULT 0, weight_kg DOUBLE PRECISION DEFAULT 0, shipping_cny DOUBLE PRECISION DEFAULT 0, commission_rate DOUBLE PRECISION DEFAULT 0.15, revenue_cny DOUBLE PRECISION DEFAULT 0, platform_fee_cny DOUBLE PRECISION DEFAULT 0, tax_cny DOUBLE PRECISION DEFAULT 0, logistics_fee_cny DOUBLE PRECISION DEFAULT 0, refund_cny DOUBLE PRECISION DEFAULT 0, profit_cny DOUBLE PRECISION DEFAULT 0, fee_rule_id INTEGER, logistics_rule_id INTEGER, raw_json TEXT, created_at TEXT NOT NULL, synced_at TEXT);
    CREATE TABLE IF NOT EXISTS products(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, title TEXT NOT NULL, category TEXT, cost_cny DOUBLE PRECISION DEFAULT 0, weight_kg DOUBLE PRECISION DEFAULT 0, price_rub DOUBLE PRECISION DEFAULT 0, stock INTEGER DEFAULT 0, status TEXT DEFAULT 'draft', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tickets(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, customer TEXT, message TEXT, status TEXT DEFAULT 'open', ai_reply TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit_logs(id SERIAL PRIMARY KEY, user_id INTEGER, action TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS category_keyword_rules(id SERIAL PRIMARY KEY, keyword TEXT UNIQUE NOT NULL, category TEXT NOT NULL, note TEXT DEFAULT '', updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS category_fee_matrix(id SERIAL PRIMARY KEY, module TEXT NOT NULL, category TEXT UNIQUE NOT NULL, r_fbs_1500 DOUBLE PRECISION DEFAULT 0, fbp_1500 DOUBLE PRECISION DEFAULT 0, r_fbs_5000 DOUBLE PRECISION DEFAULT 0, fbp_5000 DOUBLE PRECISION DEFAULT 0, r_fbs_above DOUBLE PRECISION DEFAULT 0, fbp_above DOUBLE PRECISION DEFAULT 0, match_method TEXT DEFAULT 'category+price+scheme', updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS listing_jobs(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, product_name TEXT NOT NULL, source TEXT DEFAULT '', source_url TEXT DEFAULT '', category TEXT DEFAULT '', keywords TEXT DEFAULT '', cost_cny DOUBLE PRECISION DEFAULT 0, weight_kg DOUBLE PRECISION DEFAULT 0, price_rub DOUBLE PRECISION DEFAULT 0, image_url TEXT DEFAULT '', generated_listing TEXT DEFAULT '', ozon_shop_id INTEGER, ozon_status TEXT DEFAULT 'draft', raw_json TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS marketplace_accounts(user_id INTEGER NOT NULL, platform TEXT NOT NULL, account_name TEXT DEFAULT '', status TEXT DEFAULT 'not_logged_in', note TEXT DEFAULT '', updated_at TEXT NOT NULL, PRIMARY KEY(user_id, platform));
    CREATE TABLE IF NOT EXISTS email_verification_codes(id SERIAL PRIMARY KEY, email TEXT NOT NULL, purpose TEXT NOT NULL, code_hash TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT, attempts INTEGER DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS refunds(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, shop_id INTEGER, order_id INTEGER, posting_number TEXT DEFAULT '', refund_no TEXT NOT NULL, status TEXT DEFAULT 'new', amount_rub DOUBLE PRECISION DEFAULT 0, amount_cny DOUBLE PRECISION DEFAULT 0, reason TEXT DEFAULT '', raw_json TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, synced_at TEXT);
    CREATE TABLE IF NOT EXISTS sourcing_products(id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, platform TEXT NOT NULL, title TEXT NOT NULL, source_url TEXT DEFAULT '', supplier_name TEXT DEFAULT '', price_cny DOUBLE PRECISION DEFAULT 0, domestic_shipping_cny DOUBLE PRECISION DEFAULT 0, min_order_qty INTEGER DEFAULT 1, stock INTEGER DEFAULT 0, image_url TEXT DEFAULT '', category TEXT DEFAULT '', note TEXT DEFAULT '', status TEXT DEFAULT 'candidate', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    """)
    for table, fields in {
        "orders": {"shop_id": "INTEGER", "posting_number": "TEXT", "category": "TEXT DEFAULT ''", "weight_kg": "DOUBLE PRECISION DEFAULT 0", "revenue_cny": "DOUBLE PRECISION DEFAULT 0", "platform_fee_cny": "DOUBLE PRECISION DEFAULT 0", "tax_cny": "DOUBLE PRECISION DEFAULT 0", "logistics_fee_cny": "DOUBLE PRECISION DEFAULT 0", "refund_cny": "DOUBLE PRECISION DEFAULT 0", "fee_rule_id": "INTEGER", "logistics_rule_id": "INTEGER", "raw_json": "TEXT", "synced_at": "TEXT"},
        "logistics_rules": {"channel_name": "TEXT DEFAULT ''", "source_sheet": "TEXT DEFAULT ''", "formula_text": "TEXT DEFAULT ''", "delivery_days": "TEXT DEFAULT ''", "base_fee_cny": "DOUBLE PRECISION DEFAULT 0", "fee_per_kg_cny": "DOUBLE PRECISION DEFAULT 0"},
    }.items():
        for name, ddl in fields.items():
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {ddl}")
    cur.execute("SELECT id FROM users LIMIT 1")
    if not cur.fetchone():
        salt, digest = hash_password(os.getenv("ADMIN_PASSWORD", "admin123456"))
        cur.execute("INSERT INTO users(username,email,password_salt,password_hash,role,status,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)", ("admin", "admin@example.com", salt, digest, "admin", "active", now_iso()))
    cur.execute("SELECT id FROM ai_settings WHERE id=1")
    if not cur.fetchone():
        cur.execute("INSERT INTO ai_settings(id,api_key,base_url,model,image_model,updated_at) VALUES(1,%s,%s,%s,%s,%s)", (DOUBAO_API_KEY, DOUBAO_BASE_URL, DOUBAO_MODEL, DOUBAO_IMAGE_MODEL, now_iso()))
    cur.execute("SELECT id FROM app_settings WHERE id=1")
    if not cur.fetchone():
        cur.execute("INSERT INTO app_settings(id,app_name,tagline,exchange_rate,support_email,updated_at) VALUES(1,%s,%s,%s,%s,%s)", (APP_NAME, "Ozon seller ERP workspace", DEFAULT_EXCHANGE_RATE, "support@example.com", now_iso()))
    cur.execute("SELECT id FROM platform_fee_rules LIMIT 1")
    if not cur.fetchone():
        cur.execute("INSERT INTO platform_fee_rules(user_id,name,commission_rate,tax_rate,active,updated_at) VALUES(%s,%s,%s,%s,%s,%s)", (1, "Default Ozon fee", 0.15, 0, 1, now_iso()))
    bad_text = "%\ufffd%"
    cur.execute("DELETE FROM category_keyword_rules WHERE keyword LIKE %s OR category LIKE %s OR note LIKE %s", (bad_text, bad_text, bad_text))
    cur.execute("DELETE FROM category_fee_matrix WHERE module LIKE %s OR category LIKE %s OR match_method LIKE %s", (bad_text, bad_text, bad_text))
    cur.executemany("""
        INSERT INTO category_keyword_rules(keyword,category,note,updated_at)
        VALUES(%s,%s,%s,%s)
        ON CONFLICT(keyword) DO UPDATE SET category=EXCLUDED.category,note=EXCLUDED.note,updated_at=EXCLUDED.updated_at
    """, [(k, cat, note, now_iso()) for k, cat, note in CATEGORY_KEYWORDS])
    cur.executemany("""
        INSERT INTO category_fee_matrix(module,category,r_fbs_1500,fbp_1500,r_fbs_5000,fbp_5000,r_fbs_above,fbp_above,updated_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(category) DO UPDATE SET module=EXCLUDED.module,r_fbs_1500=EXCLUDED.r_fbs_1500,fbp_1500=EXCLUDED.fbp_1500,r_fbs_5000=EXCLUDED.r_fbs_5000,fbp_5000=EXCLUDED.fbp_5000,r_fbs_above=EXCLUDED.r_fbs_above,fbp_above=EXCLUDED.fbp_above,updated_at=EXCLUDED.updated_at
    """, [(*row, now_iso()) for row in CATEGORY_FEES])
    c.commit()
    c.close()


def init_db():
    if USE_POSTGRES:
        init_postgres_db()
        return
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password_salt TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS ai_settings(id INTEGER PRIMARY KEY CHECK(id=1), api_key TEXT, base_url TEXT, model TEXT, image_model TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS app_settings(id INTEGER PRIMARY KEY CHECK(id=1), app_name TEXT NOT NULL, tagline TEXT NOT NULL, exchange_rate REAL NOT NULL, support_email TEXT, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS ozon_settings(user_id INTEGER PRIMARY KEY, client_id TEXT, api_key TEXT, sync_type TEXT DEFAULT 'FBS / rFBS订单', updated_at TEXT);
    CREATE TABLE IF NOT EXISTS ozon_shops(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, shop_name TEXT NOT NULL, client_id TEXT NOT NULL, api_key TEXT NOT NULL, sync_type TEXT DEFAULT 'FBS', auto_sync INTEGER DEFAULT 1, last_sync_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS platform_fee_rules(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL, category TEXT DEFAULT '', sku_pattern TEXT DEFAULT '', commission_rate REAL DEFAULT 0.15, tax_rate REAL DEFAULT 0, active INTEGER DEFAULT 1, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS logistics_rules(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL, category TEXT DEFAULT '', sku_pattern TEXT DEFAULT '', channel_name TEXT DEFAULT '', source_sheet TEXT DEFAULT '', formula_text TEXT DEFAULT '', delivery_days TEXT DEFAULT '', base_fee_cny REAL DEFAULT 0, fee_per_kg_cny REAL DEFAULT 0, min_weight_kg REAL DEFAULT 0, max_weight_kg REAL DEFAULT 999999, fee_cny REAL DEFAULT 0, active INTEGER DEFAULT 1, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sync_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, shop_id INTEGER, status TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, shop_id INTEGER, posting_number TEXT, month TEXT, order_no TEXT, status TEXT, product TEXT, sku TEXT, category TEXT DEFAULT '', quantity INTEGER DEFAULT 1, price_rub REAL DEFAULT 0, cost_cny REAL DEFAULT 0, weight_kg REAL DEFAULT 0, shipping_cny REAL DEFAULT 0, commission_rate REAL DEFAULT 0.15, revenue_cny REAL DEFAULT 0, platform_fee_cny REAL DEFAULT 0, tax_cny REAL DEFAULT 0, logistics_fee_cny REAL DEFAULT 0, refund_cny REAL DEFAULT 0, profit_cny REAL DEFAULT 0, fee_rule_id INTEGER, logistics_rule_id INTEGER, raw_json TEXT, created_at TEXT NOT NULL, synced_at TEXT);
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL, category TEXT, cost_cny REAL DEFAULT 0, weight_kg REAL DEFAULT 0, price_rub REAL DEFAULT 0, stock INTEGER DEFAULT 0, status TEXT DEFAULT 'draft', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, customer TEXT, message TEXT, status TEXT DEFAULT 'open', ai_reply TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS category_keyword_rules(id INTEGER PRIMARY KEY AUTOINCREMENT, keyword TEXT UNIQUE NOT NULL, category TEXT NOT NULL, note TEXT DEFAULT '', updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS category_fee_matrix(id INTEGER PRIMARY KEY AUTOINCREMENT, module TEXT NOT NULL, category TEXT UNIQUE NOT NULL, r_fbs_1500 REAL DEFAULT 0, fbp_1500 REAL DEFAULT 0, r_fbs_5000 REAL DEFAULT 0, fbp_5000 REAL DEFAULT 0, r_fbs_above REAL DEFAULT 0, fbp_above REAL DEFAULT 0, match_method TEXT DEFAULT '按商品类目+售价区间+方案', updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS listing_jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_name TEXT NOT NULL, source TEXT DEFAULT '', source_url TEXT DEFAULT '', category TEXT DEFAULT '', keywords TEXT DEFAULT '', cost_cny REAL DEFAULT 0, weight_kg REAL DEFAULT 0, price_rub REAL DEFAULT 0, image_url TEXT DEFAULT '', generated_listing TEXT DEFAULT '', ozon_shop_id INTEGER, ozon_status TEXT DEFAULT 'draft', raw_json TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS marketplace_accounts(user_id INTEGER NOT NULL, platform TEXT NOT NULL, account_name TEXT DEFAULT '', status TEXT DEFAULT '未登录', note TEXT DEFAULT '', updated_at TEXT NOT NULL, PRIMARY KEY(user_id, platform));
    CREATE TABLE IF NOT EXISTS email_verification_codes(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, purpose TEXT NOT NULL, code_hash TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT, attempts INTEGER DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS refunds(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, shop_id INTEGER, order_id INTEGER, posting_number TEXT DEFAULT '', refund_no TEXT NOT NULL, status TEXT DEFAULT 'new', amount_rub REAL DEFAULT 0, amount_cny REAL DEFAULT 0, reason TEXT DEFAULT '', raw_json TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, synced_at TEXT);
    CREATE TABLE IF NOT EXISTS sourcing_products(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, platform TEXT NOT NULL, title TEXT NOT NULL, source_url TEXT DEFAULT '', supplier_name TEXT DEFAULT '', price_cny REAL DEFAULT 0, domestic_shipping_cny REAL DEFAULT 0, min_order_qty INTEGER DEFAULT 1, stock INTEGER DEFAULT 0, image_url TEXT DEFAULT '', category TEXT DEFAULT '', note TEXT DEFAULT '', status TEXT DEFAULT 'candidate', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    """)
    migrations = {
        "orders": {"shop_id": "INTEGER", "posting_number": "TEXT", "category": "TEXT DEFAULT ''", "weight_kg": "REAL DEFAULT 0", "revenue_cny": "REAL DEFAULT 0", "platform_fee_cny": "REAL DEFAULT 0", "tax_cny": "REAL DEFAULT 0", "logistics_fee_cny": "REAL DEFAULT 0", "refund_cny": "REAL DEFAULT 0", "fee_rule_id": "INTEGER", "logistics_rule_id": "INTEGER", "raw_json": "TEXT", "synced_at": "TEXT"},
        "logistics_rules": {"channel_name": "TEXT DEFAULT ''", "source_sheet": "TEXT DEFAULT ''", "formula_text": "TEXT DEFAULT ''", "delivery_days": "TEXT DEFAULT ''", "base_fee_cny": "REAL DEFAULT 0", "fee_per_kg_cny": "REAL DEFAULT 0"},
    }
    for table, fields in migrations.items():
        existing = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
        for name, ddl in fields.items():
            if name not in existing:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    if not c.execute("SELECT id FROM users LIMIT 1").fetchone():
        salt, digest = hash_password(os.getenv("ADMIN_PASSWORD", "admin123456"))
        c.execute("INSERT INTO users(username,email,password_salt,password_hash,role,status,created_at) VALUES(?,?,?,?,?,?,?)", ("admin", "admin@example.com", salt, digest, "admin", "active", now_iso()))
    if not c.execute("SELECT id FROM ai_settings WHERE id=1").fetchone():
        c.execute("INSERT INTO ai_settings(id,api_key,base_url,model,image_model,updated_at) VALUES(1,?,?,?,?,?)", (DOUBAO_API_KEY, DOUBAO_BASE_URL, DOUBAO_MODEL, DOUBAO_IMAGE_MODEL, now_iso()))
    if not c.execute("SELECT id FROM app_settings WHERE id=1").fetchone():
        c.execute("INSERT INTO app_settings(id,app_name,tagline,exchange_rate,support_email,updated_at) VALUES(1,?,?,?,?,?)", (APP_NAME, "面向跨境卖家的订单、库存、利润和 AI 运营工作台", DEFAULT_EXCHANGE_RATE, "support@example.com", now_iso()))
    if not c.execute("SELECT id FROM platform_fee_rules LIMIT 1").fetchone():
        c.execute("INSERT INTO platform_fee_rules(user_id,name,commission_rate,tax_rate,active,updated_at) VALUES(?,?,?,?,?,?)", (1, "Default Ozon fee", 0.15, 0, 1, now_iso()))
    bad_text = "%\ufffd%"
    c.execute("DELETE FROM category_keyword_rules WHERE keyword LIKE ? OR category LIKE ? OR note LIKE ?", (bad_text, bad_text, bad_text))
    c.execute("DELETE FROM category_fee_matrix WHERE module LIKE ? OR category LIKE ? OR match_method LIKE ?", (bad_text, bad_text, bad_text))
    c.executemany("""
        INSERT INTO category_keyword_rules(keyword,category,note,updated_at)
        VALUES(?,?,?,?)
        ON CONFLICT(keyword) DO UPDATE SET category=excluded.category,note=excluded.note,updated_at=excluded.updated_at
    """, [(k, cat, note, now_iso()) for k, cat, note in CATEGORY_KEYWORDS])
    c.executemany("""
        INSERT INTO category_fee_matrix(module,category,r_fbs_1500,fbp_1500,r_fbs_5000,fbp_5000,r_fbs_above,fbp_above,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(category) DO UPDATE SET module=excluded.module,r_fbs_1500=excluded.r_fbs_1500,fbp_1500=excluded.fbp_1500,r_fbs_5000=excluded.r_fbs_5000,fbp_5000=excluded.fbp_5000,r_fbs_above=excluded.r_fbs_above,fbp_above=excluded.fbp_above,updated_at=excluded.updated_at
    """, [(*row, now_iso()) for row in CATEGORY_FEES])
    c.commit()
    c.close()


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: str
    password: str = Field(min_length=6)
    code: str = ""


class RegisterCodeIn(BaseModel):
    email: str


class LoginIn(BaseModel):
    account: str
    password: str


class AISettingsIn(BaseModel):
    api_key: str = ""
    base_url: str = DOUBAO_BASE_URL
    model: str = ""
    image_model: str = DOUBAO_IMAGE_MODEL


class AppSettingsIn(BaseModel):
    app_name: str = Field(default=APP_NAME, min_length=2, max_length=60)
    tagline: str = Field(default="面向跨境卖家的订单、库存、利润和 AI 运营工作台", max_length=180)
    exchange_rate: float = Field(default=DEFAULT_EXCHANGE_RATE, gt=0)
    support_email: str = ""


class ProductIn(BaseModel):
    title: str
    category: str = ""
    cost_cny: float = 0
    weight_kg: float = 0
    price_rub: float = 0
    stock: int = 0
    status: str = "draft"


class OrderIn(BaseModel):
    month: str = ""
    order_no: str
    status: str = ""
    product: str = ""
    sku: str = ""
    category: str = ""
    quantity: int = 1
    price_rub: float = 0
    cost_cny: float = 0
    shipping_cny: float = 0
    commission_rate: Optional[float] = None
    weight_kg: float = 0


class OzonSettingsIn(BaseModel):
    client_id: str = ""
    api_key: str = ""
    sync_type: str = "FBS / rFBS订单"


class OzonShopIn(BaseModel):
    shop_name: str = Field(default="Ozon Store", min_length=1, max_length=80)
    client_id: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    sync_type: str = "FBS"
    auto_sync: bool = True


class PlatformFeeRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: str = ""
    sku_pattern: str = ""
    commission_rate: float = Field(default=0.15, ge=0, le=1)
    tax_rate: float = Field(default=0, ge=0, le=1)
    active: bool = True


class LogisticsRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: str = ""
    sku_pattern: str = ""
    channel_name: str = ""
    source_sheet: str = ""
    formula_text: str = ""
    delivery_days: str = ""
    base_fee_cny: float = Field(default=0, ge=0)
    fee_per_kg_cny: float = Field(default=0, ge=0)
    min_weight_kg: float = Field(default=0, ge=0)
    max_weight_kg: float = Field(default=999999, ge=0)
    fee_cny: float = Field(default=0, ge=0)
    active: bool = True


class ChatIn(BaseModel):
    message: str
    system: str = "你是Ozon跨境电商ERP助手，请用中文回答，给出可执行步骤。"


class AdminCreateUserIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: str
    password: str = Field(min_length=6)
    role: str = "user"


class MarketplaceAccountIn(BaseModel):
    platform: str
    account_name: str = ""
    status: str = "未登录"
    note: str = ""


class ListingJobIn(BaseModel):
    product_name: str = Field(min_length=1)
    source: str = ""
    source_url: str = ""
    category: str = ""
    keywords: str = ""
    cost_cny: float = 0
    weight_kg: float = 0
    price_rub: float = 0
    image_url: str = ""
    generated_listing: str = ""
    ozon_shop_id: Optional[int] = None


class SourcingProductIn(BaseModel):
    platform: str = "1688"
    title: str = Field(min_length=1)
    source_url: str = ""
    supplier_name: str = ""
    price_cny: float = 0
    domestic_shipping_cny: float = 0
    min_order_qty: int = 1
    stock: int = 0
    image_url: str = ""
    category: str = ""
    note: str = ""
    status: str = "candidate"


class RefundIn(BaseModel):
    order_id: Optional[int] = None
    posting_number: str = ""
    refund_no: str = ""
    status: str = "new"
    amount_rub: float = 0
    amount_cny: float = 0
    reason: str = ""


class ImageGenerateIn(BaseModel):
    product_name: str = ""
    prompt: str
    style: str = "白底电商主图，真实产品摄影，高级质感，适合 Ozon 商品展示"


class ProfitPreviewIn(BaseModel):
    product: str = ""
    sku: str = ""
    category: str = ""
    price_rub: float = 0
    cost_cny: float = 0
    shipping_cny: float = 0
    weight_kg: float = 0
    commission_rate: Optional[float] = None
    scheme: str = "r_fbs"


def rows(sql: str, *args):
    c = conn()
    try:
        if USE_POSTGRES:
            cur = c.cursor()
            cur.execute(db_sql(sql), args)
            return [dict(x) for x in cur.fetchall()]
        return [dict(x) for x in c.execute(sql, args).fetchall()]
    finally:
        c.close()


def one(sql: str, *args):
    c = conn()
    try:
        if USE_POSTGRES:
            cur = c.cursor()
            cur.execute(db_sql(sql), args)
            row = cur.fetchone()
        else:
            row = c.execute(sql, args).fetchone()
        return dict(row) if row else None
    finally:
        c.close()


def write(sql: str, *args):
    c = conn()
    try:
        final_sql = db_sql(sql)
        table_name = insert_table_name(sql)
        should_return_id = USE_POSTGRES and table_name in INSERT_ID_TABLES and " returning " not in final_sql.lower()
        if should_return_id:
            final_sql = final_sql.rstrip().rstrip(";") + " RETURNING id"
        if USE_POSTGRES:
            cur = c.cursor()
            cur.execute(final_sql, args)
            last_id = None
            if should_return_id:
                row = cur.fetchone()
                last_id = row["id"] if row else None
        else:
            cur = c.execute(final_sql, args)
            last_id = cur.lastrowid
        c.commit()
        return last_id
    except Exception as exc:
        c.rollback()
        if USE_POSTGRES and exc.__class__.__name__ in {"UniqueViolation", "IntegrityError"}:
            raise sqlite3.IntegrityError(str(exc)) from exc
        raise
    finally:
        c.close()


init_db()


def code_hash(email: str, code: str, purpose: str = "register"):
    raw = f"{email.strip().lower()}:{purpose}:{code}:{JWT_SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()


def smtp_ready():
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM)


def send_email(to_email: str, subject: str, body: str):
    if not smtp_ready():
        if APP_ENV == "production":
            raise HTTPException(status_code=500, detail="邮件服务未配置，请在服务器环境变量中配置 SMTP。")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body)
    if SMTP_TLS:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=20) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    return True


def issue_email_code(email: str, purpose: str = "register"):
    email = email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="请输入有效邮箱。")
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat(timespec="seconds") + "Z"
    write(
        "INSERT INTO email_verification_codes(email,purpose,code_hash,expires_at,created_at) VALUES(?,?,?,?,?)",
        email, purpose, code_hash(email, code, purpose), expires_at, now_iso()
    )
    sent = send_email(
        email,
        "Ozon ERP Pro 注册验证码",
        f"你的注册验证码是：{code}\n\n验证码 10 分钟内有效。若不是你本人操作，请忽略本邮件。\n{PUBLIC_APP_URL}".strip()
    )
    return {"ok": True, "email_sent": sent, "dev_code": code if not sent and APP_ENV != "production" else None}


def verify_email_code(email: str, code: str, purpose: str = "register"):
    email = email.strip().lower()
    code = (code or "").strip()
    row = one(
        "SELECT * FROM email_verification_codes WHERE email=? AND purpose=? AND used_at IS NULL ORDER BY id DESC LIMIT 1",
        email, purpose
    )
    if not row:
        raise HTTPException(status_code=400, detail="请先发送邮箱验证码。")
    if row.get("attempts", 0) >= 5:
        raise HTTPException(status_code=400, detail="验证码错误次数过多，请重新发送。")
    if row["expires_at"] < now_iso():
        raise HTTPException(status_code=400, detail="验证码已过期，请重新发送。")
    if not hmac.compare_digest(row["code_hash"], code_hash(email, code, purpose)):
        write("UPDATE email_verification_codes SET attempts=attempts+1 WHERE id=?", row["id"])
        raise HTTPException(status_code=400, detail="验证码不正确。")
    write("UPDATE email_verification_codes SET used_at=? WHERE id=?", now_iso(), row["id"])
    return True


def current_user(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    payload = decode_token(authorization.split(" ", 1)[1])
    user = one("SELECT id,username,email,role,status,created_at FROM users WHERE id=?", payload["uid"])
    if not user or user["status"] != "active":
        raise HTTPException(status_code=403, detail="账号不可用")
    return user


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def log_action(user_id: Optional[int], action: str, detail: str = ""):
    write("INSERT INTO audit_logs(user_id,action,detail,created_at) VALUES(?,?,?,?)", user_id, action, detail[:500], now_iso())


def app_settings():
    return one("SELECT app_name,tagline,exchange_rate,support_email FROM app_settings WHERE id=1") or {"app_name": APP_NAME, "tagline": "面向跨境卖家的订单、库存、利润和 AI 运营工作台", "exchange_rate": DEFAULT_EXCHANGE_RATE, "support_email": "support@example.com"}


def match_rule(rule: Dict[str, Any], sku: str, category: str, weight_kg: float):
    sku_pattern = (rule.get("sku_pattern") or "").strip().lower()
    rule_category = (rule.get("category") or "").strip().lower()
    if sku_pattern and sku_pattern not in (sku or "").lower():
        return False
    if rule_category and category and rule_category != category.strip().lower():
        return False
    return float(rule.get("min_weight_kg") or 0) <= weight_kg <= float(rule.get("max_weight_kg") or 999999)


def category_fee_for(category: str, price_rub: float, scheme: str = "r_fbs"):
    if not category:
        return None
    row = one("SELECT * FROM category_fee_matrix WHERE category=?", category)
    if not row:
        return None
    prefix = "fbp" if (scheme or "").lower() == "fbp" else "r_fbs"
    if price_rub <= 1500:
        column = f"{prefix}_1500"
    elif price_rub <= 5000:
        column = f"{prefix}_5000"
    else:
        column = f"{prefix}_above"
    percent = float(row.get(column) or 0)
    return {"category": category, "scheme": prefix, "column": column, "percent": percent, "rate": percent / 100, "matrix": row}


def calculate_order(user_id: int, payload: Dict[str, Any]):
    sku, category = payload.get("sku", ""), payload.get("category", "")
    weight = float(payload.get("weight_kg") or 0)
    price_rub = float(payload.get("price_rub") or 0)
    if not category:
        matches = match_category_text(" ".join([payload.get("product", ""), sku]))
        category = matches[0]["category"] if matches else ""
    revenue = price_rub * float(app_settings()["exchange_rate"])
    fee_rule = next((r for r in rows("SELECT * FROM platform_fee_rules WHERE user_id=? AND active=1 ORDER BY sku_pattern DESC, category DESC, id DESC", user_id) if match_rule(r, sku, category, weight)), None)
    logistics_rule = next((r for r in rows("SELECT * FROM logistics_rules WHERE user_id=? AND active=1 ORDER BY min_weight_kg DESC,id DESC", user_id) if match_rule(r, sku, category, weight)), None)
    category_fee = category_fee_for(category, price_rub, payload.get("scheme") or "r_fbs")
    manual_rate = payload.get("commission_rate")
    specific_fee_rule = fee_rule if fee_rule and ((fee_rule.get("sku_pattern") or "").strip() or (fee_rule.get("category") or "").strip()) else None
    if manual_rate in ("", None):
        if specific_fee_rule:
            commission_rate = float(specific_fee_rule["commission_rate"])
        elif category_fee:
            commission_rate = float(category_fee["rate"])
        elif fee_rule:
            commission_rate = float(fee_rule["commission_rate"])
        else:
            commission_rate = 0.15
    else:
        commission_rate = float(manual_rate)
    platform_fee = revenue * commission_rate
    tax = revenue * float(fee_rule["tax_rate"] if fee_rule else 0)
    if logistics_rule:
        billable_weight = max(weight, float(logistics_rule.get("min_weight_kg") or 0))
        formula_fee = float(logistics_rule.get("base_fee_cny") or 0) + billable_weight * float(logistics_rule.get("fee_per_kg_cny") or 0)
        logistics_fee = formula_fee if formula_fee > 0 else float(logistics_rule.get("fee_cny") or 0)
    else:
        logistics_fee = float(payload.get("shipping_cny") or 0)
    refund_cny = float(payload.get("refund_cny") or 0)
    profit = revenue - float(payload.get("cost_cny") or 0) - platform_fee - tax - logistics_fee - refund_cny
    return {"matched_category": category, "category_fee": category_fee, "revenue_cny": round(revenue, 2), "commission_rate": commission_rate, "platform_fee_cny": round(platform_fee, 2), "tax_cny": round(tax, 2), "logistics_fee_cny": round(logistics_fee, 2), "shipping_cny": round(logistics_fee, 2), "refund_cny": round(refund_cny, 2), "profit_cny": round(profit, 2), "fee_rule_id": (specific_fee_rule or fee_rule)["id"] if (specific_fee_rule or fee_rule) else None, "logistics_rule_id": logistics_rule["id"] if logistics_rule else None}


def upsert_order(user_id: int, payload: Dict[str, Any]):
    finance = calculate_order(user_id, payload)
    order_no = payload.get("order_no") or payload.get("posting_number") or ""
    month = payload.get("month") or datetime.utcnow().strftime("%Y-%m")
    existing = one("SELECT id FROM orders WHERE user_id=? AND order_no=?", user_id, order_no)
    values = (payload.get("shop_id"), payload.get("posting_number") or order_no, month, order_no, payload.get("status", ""), payload.get("product", ""), payload.get("sku", ""), finance.get("matched_category") or payload.get("category", ""), int(payload.get("quantity") or 1), float(payload.get("price_rub") or 0), float(payload.get("cost_cny") or 0), float(payload.get("weight_kg") or 0), finance["shipping_cny"], finance["commission_rate"], finance["revenue_cny"], finance["platform_fee_cny"], finance["tax_cny"], finance["logistics_fee_cny"], finance["refund_cny"], finance["profit_cny"], finance["fee_rule_id"], finance["logistics_rule_id"], payload.get("raw_json", ""), now_iso())
    if existing:
        write("UPDATE orders SET shop_id=?,posting_number=?,month=?,order_no=?,status=?,product=?,sku=?,category=?,quantity=?,price_rub=?,cost_cny=?,weight_kg=?,shipping_cny=?,commission_rate=?,revenue_cny=?,platform_fee_cny=?,tax_cny=?,logistics_fee_cny=?,refund_cny=?,profit_cny=?,fee_rule_id=?,logistics_rule_id=?,raw_json=?,synced_at=? WHERE id=?", *values, existing["id"])
        order_id = existing["id"]
    else:
        order_id = write("INSERT INTO orders(user_id,shop_id,posting_number,month,order_no,status,product,sku,category,quantity,price_rub,cost_cny,weight_kg,shipping_cny,commission_rate,revenue_cny,platform_fee_cny,tax_cny,logistics_fee_cny,refund_cny,profit_cny,fee_rule_id,logistics_rule_id,raw_json,created_at,synced_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", user_id, *values[:-1], now_iso(), values[-1])
    return {"id": order_id, **finance}


def parse_float(value: Any):
    try:
        return float(str(value or "0").replace(",", "."))
    except Exception:
        return 0.0


def ozon_order(shop: Dict[str, Any], posting: Dict[str, Any]):
    products = posting.get("products") or [{}]
    first = products[0] if products else {}
    quantity = sum(int(p.get("quantity") or 1) for p in products) or 1
    price = sum(parse_float(p.get("price")) * int(p.get("quantity") or 1) for p in products)
    return {"shop_id": shop["id"], "posting_number": posting.get("posting_number"), "order_no": posting.get("posting_number"), "month": (posting.get("in_process_at") or now_iso())[:7], "status": posting.get("status", ""), "product": first.get("name") or first.get("offer_id") or "", "sku": first.get("offer_id") or str(first.get("sku") or ""), "quantity": quantity, "price_rub": price, "raw_json": json.dumps(posting, ensure_ascii=False)}


REFUND_WORDS = ("refund", "return", "cancel", "canceled", "cancelled", "возврат", "отмена", "returned", "refunded")


def is_refund_like(value: Any):
    text = json.dumps(value, ensure_ascii=False).lower() if not isinstance(value, str) else value.lower()
    return any(word in text for word in REFUND_WORDS)


def order_base_profit(order: Dict[str, Any], refund_cny: float):
    return round(
        float(order.get("revenue_cny") or 0)
        - float(order.get("cost_cny") or 0)
        - float(order.get("platform_fee_cny") or 0)
        - float(order.get("tax_cny") or 0)
        - float(order.get("logistics_fee_cny") or order.get("shipping_cny") or 0)
        - refund_cny,
        2,
    )


def recalc_order_refunds(user_id: int, order_id: Optional[int] = None, posting_number: str = ""):
    order = None
    if order_id:
        order = one("SELECT * FROM orders WHERE id=? AND user_id=?", order_id, user_id)
    if not order and posting_number:
        order = one("SELECT * FROM orders WHERE posting_number=? AND user_id=?", posting_number, user_id)
    if not order:
        return
    refund = one("SELECT COALESCE(SUM(amount_cny),0) n FROM refunds WHERE user_id=? AND (order_id=? OR posting_number=?)", user_id, order["id"], order.get("posting_number") or order.get("order_no") or "")
    refund_cny = round(float(refund["n"] or 0), 2)
    write("UPDATE orders SET refund_cny=?, profit_cny=? WHERE id=? AND user_id=?", refund_cny, order_base_profit(order, refund_cny), order["id"], user_id)


def save_refund(user_id: int, shop_id: Optional[int], order_id: Optional[int], posting_number: str, refund_no: str, status: str, amount_rub: float, reason: str, raw: Any):
    rate = float(app_settings()["exchange_rate"])
    amount_cny = round(abs(float(amount_rub or 0)) * rate, 2)
    refund_no = refund_no or f"{posting_number or order_id}-{status}"
    existing = one("SELECT id FROM refunds WHERE user_id=? AND refund_no=?", user_id, refund_no)
    raw_json = json.dumps(raw or {}, ensure_ascii=False)[:4000]
    if existing:
        write("UPDATE refunds SET shop_id=?,order_id=?,posting_number=?,status=?,amount_rub=?,amount_cny=?,reason=?,raw_json=?,updated_at=?,synced_at=? WHERE id=? AND user_id=?", shop_id, order_id, posting_number, status, amount_rub, amount_cny, reason, raw_json, now_iso(), now_iso(), existing["id"], user_id)
        refund_id = existing["id"]
    else:
        refund_id = write("INSERT INTO refunds(user_id,shop_id,order_id,posting_number,refund_no,status,amount_rub,amount_cny,reason,raw_json,created_at,updated_at,synced_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", user_id, shop_id, order_id, posting_number, refund_no, status, amount_rub, amount_cny, reason, raw_json, now_iso(), now_iso(), now_iso())
    recalc_order_refunds(user_id, order_id, posting_number)
    return refund_id


def detect_refund_from_posting(shop: Dict[str, Any], posting: Dict[str, Any], order_id: int):
    status = posting.get("status", "")
    if not is_refund_like(status):
        return 0
    order_amount = ozon_order(shop, posting)["price_rub"]
    posting_number = posting.get("posting_number") or ""
    save_refund(
        shop["user_id"],
        shop["id"],
        order_id,
        posting_number,
        f"{posting_number}-{status}",
        status,
        order_amount,
        posting.get("cancellation", {}).get("cancel_reason") or posting.get("substatus") or "Ozon order status indicates refund/return/cancellation",
        posting,
    )
    return 1


def sync_ozon_finance_refunds(shop: Dict[str, Any], days: int = 14):
    payload = {
        "filter": {
            "date": {"from": (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z", "to": now_iso()},
            "transaction_type": "all",
        },
        "page": 1,
        "page_size": 1000,
    }
    try:
        resp = requests.post(OZON_API_BASE_URL.rstrip("/") + "/v3/finance/transaction/list", headers={"Client-Id": shop["client_id"], "Api-Key": shop["api_key"], "Content-Type": "application/json"}, json=payload, timeout=(15, 60))
    except requests.exceptions.RequestException as exc:
        write("INSERT INTO sync_logs(user_id,shop_id,status,detail,created_at) VALUES(?,?,?,?,?)", shop["user_id"], shop["id"], "warn", f"refund finance sync failed: {exc}"[:500], now_iso())
        return 0
    if resp.status_code >= 400:
        write("INSERT INTO sync_logs(user_id,shop_id,status,detail,created_at) VALUES(?,?,?,?,?)", shop["user_id"], shop["id"], "warn", f"refund finance sync failed: {resp.text[:400]}", now_iso())
        return 0
    data = resp.json().get("result", {})
    operations = data.get("operations") or data.get("items") or []
    imported = 0
    for op in operations:
        if not is_refund_like(op):
            continue
        posting = op.get("posting") or {}
        posting_number = posting.get("posting_number") or op.get("posting_number") or ""
        order = one("SELECT id FROM orders WHERE user_id=? AND (posting_number=? OR order_no=?)", shop["user_id"], posting_number, posting_number)
        amount_rub = abs(parse_float(op.get("amount") or op.get("operation_amount") or op.get("price") or 0))
        if not amount_rub and order:
            order_row = one("SELECT price_rub FROM orders WHERE id=?", order["id"])
            amount_rub = float(order_row.get("price_rub") or 0) if order_row else 0
        refund_no = str(op.get("operation_id") or op.get("transaction_id") or f"{posting_number}-{op.get('operation_type','refund')}")
        save_refund(shop["user_id"], shop["id"], order["id"] if order else None, posting_number, refund_no, op.get("operation_type") or op.get("type") or "refund", amount_rub, op.get("operation_type_name") or op.get("name") or "Ozon finance refund/return operation", op)
        imported += 1
    return imported


def sync_ozon_shop(shop: Dict[str, Any], days: int = 14):
    payload = {"dir": "DESC", "filter": {"since": (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z", "to": now_iso()}, "limit": 100, "offset": 0, "with": {"analytics_data": True, "financial_data": True}}
    resp = requests.post(OZON_API_BASE_URL.rstrip("/") + "/v3/posting/fbs/list", headers={"Client-Id": shop["client_id"], "Api-Key": shop["api_key"], "Content-Type": "application/json"}, json=payload, timeout=(15, 60))
    if resp.status_code >= 400:
        write("INSERT INTO sync_logs(user_id,shop_id,status,detail,created_at) VALUES(?,?,?,?,?)", shop["user_id"], shop["id"], "error", resp.text[:500], now_iso())
        raise HTTPException(status_code=resp.status_code, detail=f"Ozon 同步失败：{resp.text}")
    imported = 0
    refunds = 0
    for posting in resp.json().get("result", {}).get("postings", []):
        saved = upsert_order(shop["user_id"], ozon_order(shop, posting))
        refunds += detect_refund_from_posting(shop, posting, saved["id"])
        imported += 1
    refunds += sync_ozon_finance_refunds(shop, days=days)
    write("UPDATE ozon_shops SET last_sync_at=?, updated_at=? WHERE id=?", now_iso(), now_iso(), shop["id"])
    write("INSERT INTO sync_logs(user_id,shop_id,status,detail,created_at) VALUES(?,?,?,?,?)", shop["user_id"], shop["id"], "ok", f"imported={imported}, refunds={refunds}", now_iso())
    return {"imported": imported, "refunds": refunds}


def ai_config():
    row = one("SELECT api_key,base_url,model,image_model FROM ai_settings WHERE id=1") or {}
    return {"api_key": row.get("api_key") or DOUBAO_API_KEY, "base_url": row.get("base_url") or DOUBAO_BASE_URL, "model": row.get("model") or DOUBAO_MODEL, "image_model": row.get("image_model") or DOUBAO_IMAGE_MODEL}


def call_doubao(prompt: str, system: str = ""):
    cfg = ai_config()
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="未配置豆包 API Key。请先在 AI 设置里填写 API Key 并保存。")
    if not cfg["model"]:
        raise HTTPException(status_code=400, detail="未配置豆包文字模型 Endpoint。请填写火山方舟控制台里的 ep-... Endpoint。")
    try:
        r = requests.post(cfg["base_url"].rstrip("/") + "/chat/completions", headers={"Authorization": "Bearer " + cfg["api_key"], "Content-Type": "application/json"}, json={"model": cfg["model"], "messages": [{"role": "system", "content": system or "你是一个中文 ERP 助手。"}, {"role": "user", "content": prompt}], "temperature": 0.4}, timeout=(10, 30))
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="豆包接口请求超时，请检查网络、Base URL 和文字模型 Endpoint。")
    except requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"豆包接口请求失败：{exc}")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=f"豆包接口调用失败：{r.text}")
    data = r.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content") or json.dumps(data, ensure_ascii=False, indent=2)


def call_doubao_image(prompt: str):
    cfg = ai_config()
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="未配置豆包 API Key。请先在 AI 设置里填写 API Key 并保存。")
    if not cfg["image_model"]:
        raise HTTPException(status_code=400, detail="未配置图片模型。")
    try:
        r = requests.post(
            cfg["base_url"].rstrip("/") + "/images/generations",
            headers={"Authorization": "Bearer " + cfg["api_key"], "Content-Type": "application/json"},
            json={"model": cfg["image_model"], "prompt": prompt, "size": "1024x1024", "response_format": "url"},
            timeout=(10, 90),
        )
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="豆包图片生成超时，请稍后重试。")
    except requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"豆包图片接口请求失败：{exc}")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=f"豆包图片接口调用失败：{r.text}")
    data = r.json()
    item = (data.get("data") or [{}])[0]
    return {"image_url": item.get("url", ""), "b64_json": item.get("b64_json", ""), "raw": data}


def match_category_text(text: str):
    query = (text or "").strip().lower()
    if not query:
        return []
    result = []
    for rule in rows("SELECT * FROM category_keyword_rules ORDER BY length(keyword) DESC, id ASC"):
        if rule["keyword"].lower() in query:
            fee = one("SELECT * FROM category_fee_matrix WHERE category=?", rule["category"]) or {}
            result.append({**rule, "fee": fee})
    return result


@app.get("/api/health")
def health():
    return {"ok": True, "app": APP_NAME, "time": now_iso(), "public_url": PUBLIC_APP_URL, "database": "postgres" if USE_POSTGRES else "sqlite"}


@app.post("/api/auth/register/code")
def send_register_code(data: RegisterCodeIn):
    existing = one("SELECT id FROM users WHERE email=?", data.email.strip().lower())
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已注册。")
    return issue_email_code(data.email, "register")


@app.post("/api/auth/register")
def register(data: RegisterIn):
    if REQUIRE_EMAIL_VERIFICATION:
        verify_email_code(data.email, data.code, "register")
    salt, digest = hash_password(data.password)
    try:
        uid = write("INSERT INTO users(username,email,password_salt,password_hash,role,status,created_at) VALUES(?,?,?,?,?,?,?)", data.username, data.email.strip().lower(), salt, digest, "user", "active", now_iso())
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")
    return {"token": sign_token({"uid": uid, "role": "user"}), "user": one("SELECT id,username,email,role,status,created_at FROM users WHERE id=?", uid)}


@app.post("/api/auth/login")
def login(data: LoginIn):
    user = one("SELECT * FROM users WHERE username=? OR email=?", data.account, data.account)
    if not user or not verify_password(data.password, user["password_salt"], user["password_hash"]):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if user["status"] != "active":
        raise HTTPException(status_code=403, detail="账号已停用")
    return {"token": sign_token({"uid": user["id"], "role": user["role"]}), "user": {k: user[k] for k in ("id", "username", "email", "role", "status", "created_at")}}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return user


@app.get("/api/app/settings")
def public_settings():
    return app_settings()


@app.post("/api/admin/app/settings")
def save_app_settings(data: AppSettingsIn, admin=Depends(require_admin)):
    write("INSERT INTO app_settings(id,app_name,tagline,exchange_rate,support_email,updated_at) VALUES(1,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET app_name=excluded.app_name,tagline=excluded.tagline,exchange_rate=excluded.exchange_rate,support_email=excluded.support_email,updated_at=excluded.updated_at", data.app_name, data.tagline, data.exchange_rate, data.support_email, now_iso())
    log_action(admin["id"], "save_app_settings", data.app_name)
    return {"ok": True, "settings": app_settings()}


@app.get("/api/dashboard")
def dashboard(user=Depends(current_user)):
    stats = one("SELECT COUNT(*) orders, COALESCE(SUM(price_rub),0) sales_rub, COALESCE(SUM(profit_cny),0) profit_cny FROM orders WHERE user_id=?", user["id"])
    return {**stats, "products": one("SELECT COUNT(*) n FROM products WHERE user_id=?", user["id"])["n"], "open_tickets": one("SELECT COUNT(*) n FROM tickets WHERE user_id=? AND status='open'", user["id"])["n"], "recent_orders": rows("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 8", user["id"])}


@app.get("/api/orders")
def list_orders(user=Depends(current_user)):
    return rows("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 300", user["id"])


@app.get("/api/orders/{order_id}")
def order_detail(order_id: int, user=Depends(current_user)):
    order = one("SELECT * FROM orders WHERE id=? AND user_id=?", order_id, user["id"])
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    try:
        order["raw_data"] = json.loads(order.get("raw_json") or "{}")
    except Exception:
        order["raw_data"] = order.get("raw_json") or ""
    order["refunds"] = rows("SELECT * FROM refunds WHERE user_id=? AND (order_id=? OR posting_number=?) ORDER BY id DESC", user["id"], order["id"], order.get("posting_number") or order.get("order_no") or "")
    if order.get("fee_rule_id"):
        order["platform_rule"] = one("SELECT * FROM platform_fee_rules WHERE id=?", order["fee_rule_id"])
    if order.get("logistics_rule_id"):
        order["logistics_rule"] = one("SELECT * FROM logistics_rules WHERE id=?", order["logistics_rule_id"])
    if order.get("category"):
        order["category_fee"] = category_fee_for(order["category"], float(order.get("price_rub") or 0))
    return order


@app.post("/api/profit/preview")
def profit_preview(data: ProfitPreviewIn, user=Depends(current_user)):
    payload = data.model_dump()
    matches = match_category_text(" ".join([payload.get("product", ""), payload.get("sku", ""), payload.get("category", "")]))
    if not payload.get("category") and matches:
        payload["category"] = matches[0]["category"]
    finance = calculate_order(user["id"], payload)
    return {
        "ok": True,
        "matches": matches,
        "category": finance.get("matched_category") or payload.get("category", ""),
        "category_fee": finance.get("category_fee"),
        "finance": finance,
    }


@app.post("/api/orders")
def create_order(data: OrderIn, user=Depends(current_user)):
    return {"ok": True, **upsert_order(user["id"], data.model_dump())}


@app.get("/api/refunds")
def list_refunds(user=Depends(current_user)):
    return rows("SELECT refunds.*,orders.order_no,orders.product FROM refunds LEFT JOIN orders ON orders.id=refunds.order_id WHERE refunds.user_id=? ORDER BY refunds.id DESC LIMIT 200", user["id"])


@app.get("/api/refunds/alerts")
def refund_alerts(user=Depends(current_user)):
    items = rows("SELECT refunds.*,orders.order_no,orders.product FROM refunds LEFT JOIN orders ON orders.id=refunds.order_id WHERE refunds.user_id=? ORDER BY refunds.id DESC LIMIT 20", user["id"])
    total = one("SELECT COALESCE(SUM(amount_cny),0) amount, COUNT(*) count FROM refunds WHERE user_id=?", user["id"])
    return {"items": items, "count": total["count"], "amount_cny": round(float(total["amount"] or 0), 2)}


@app.post("/api/refunds")
def create_refund(data: RefundIn, user=Depends(current_user)):
    order = one("SELECT * FROM orders WHERE id=? AND user_id=?", data.order_id, user["id"]) if data.order_id else None
    if not order and data.posting_number:
        order = one("SELECT * FROM orders WHERE user_id=? AND (posting_number=? OR order_no=?)", user["id"], data.posting_number, data.posting_number)
    amount_rub = data.amount_rub or (float(data.amount_cny or 0) / float(app_settings()["exchange_rate"]))
    refund_id = save_refund(user["id"], order.get("shop_id") if order else None, order.get("id") if order else None, data.posting_number or (order.get("posting_number") if order else ""), data.refund_no or f"MANUAL-{int(time.time())}", data.status, amount_rub, data.reason or "Manual refund", data.model_dump())
    return {"ok": True, "id": refund_id}


@app.get("/api/products")
def list_products(user=Depends(current_user)):
    return rows("SELECT * FROM products WHERE user_id=? ORDER BY id DESC", user["id"])


@app.post("/api/products")
def create_product(data: ProductIn, user=Depends(current_user)):
    write("INSERT INTO products(user_id,title,category,cost_cny,weight_kg,price_rub,stock,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)", user["id"], data.title, data.category, data.cost_cny, data.weight_kg, data.price_rub, data.stock, data.status, now_iso())
    return {"ok": True}


@app.delete("/api/products/{pid}")
def delete_product(pid: int, user=Depends(current_user)):
    write("DELETE FROM products WHERE id=? AND user_id=?", pid, user["id"])
    return {"ok": True}


@app.post("/api/ozon/settings")
def save_ozon_settings(data: OzonSettingsIn, user=Depends(current_user)):
    current = one("SELECT api_key FROM ozon_settings WHERE user_id=?", user["id"])
    write("INSERT INTO ozon_settings(user_id,client_id,api_key,sync_type,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET client_id=excluded.client_id,api_key=excluded.api_key,sync_type=excluded.sync_type,updated_at=excluded.updated_at", user["id"], data.client_id, data.api_key or (current["api_key"] if current else ""), data.sync_type, now_iso())
    return {"ok": True}


@app.get("/api/ozon/settings")
def get_ozon_settings(user=Depends(current_user)):
    row = one("SELECT client_id,api_key,sync_type FROM ozon_settings WHERE user_id=?", user["id"])
    return {"client_id": row["client_id"] if row else "", "api_key_set": bool(row and row["api_key"]), "sync_type": row["sync_type"] if row else "FBS / rFBS订单"}


@app.get("/api/ozon/shops")
def list_shops(user=Depends(current_user)):
    return rows("""
        SELECT id,shop_name,client_id,sync_type,auto_sync,last_sync_at,created_at,updated_at,
        (SELECT COUNT(*) FROM orders o WHERE o.user_id=ozon_shops.user_id AND o.shop_id=ozon_shops.id) order_count,
        (SELECT COALESCE(SUM(price_rub),0) FROM orders o WHERE o.user_id=ozon_shops.user_id AND o.shop_id=ozon_shops.id) sales_rub,
        (SELECT COALESCE(SUM(profit_cny),0) FROM orders o WHERE o.user_id=ozon_shops.user_id AND o.shop_id=ozon_shops.id) profit_cny,
        (SELECT COALESCE(SUM(refund_cny),0) FROM orders o WHERE o.user_id=ozon_shops.user_id AND o.shop_id=ozon_shops.id) refund_cny,
        (SELECT COUNT(*) FROM refunds r WHERE r.user_id=ozon_shops.user_id AND r.shop_id=ozon_shops.id) refund_count
        FROM ozon_shops WHERE user_id=? ORDER BY id DESC
    """, user["id"])


@app.post("/api/ozon/shops")
def bind_shop(data: OzonShopIn, user=Depends(current_user)):
    existing = one("SELECT id FROM ozon_shops WHERE user_id=? AND client_id=?", user["id"], data.client_id)
    if existing:
        write("UPDATE ozon_shops SET shop_name=?,api_key=?,sync_type=?,auto_sync=?,updated_at=? WHERE id=? AND user_id=?", data.shop_name, data.api_key, data.sync_type, int(data.auto_sync), now_iso(), existing["id"], user["id"])
        shop_id = existing["id"]
    else:
        shop_id = write("INSERT INTO ozon_shops(user_id,shop_name,client_id,api_key,sync_type,auto_sync,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", user["id"], data.shop_name, data.client_id, data.api_key, data.sync_type, int(data.auto_sync), now_iso(), now_iso())
    log_action(user["id"], "bind_ozon_shop", data.shop_name)
    return {"ok": True, "id": shop_id}


@app.delete("/api/ozon/shops/{shop_id}")
def delete_shop(shop_id: int, user=Depends(current_user)):
    write("DELETE FROM ozon_shops WHERE id=? AND user_id=?", shop_id, user["id"])
    return {"ok": True}


@app.post("/api/ozon/shops/{shop_id}/sync")
def sync_shop_now(shop_id: int, user=Depends(current_user)):
    shop = one("SELECT * FROM ozon_shops WHERE id=? AND user_id=?", shop_id, user["id"])
    if not shop:
        raise HTTPException(status_code=404, detail="店铺不存在")
    return {"ok": True, **sync_ozon_shop(shop)}


@app.post("/api/ozon/sync-demo")
def sync_demo(user=Depends(current_user)):
    if os.getenv("ENABLE_DEMO_ORDERS", "0") != "1":
        raise HTTPException(status_code=404, detail="Demo order import is disabled in production.")
    samples = [{"order_no": "DEMO-1001", "status": "delivering", "product": "Палатка туристическая 4 места", "sku": "TENT-4P", "quantity": 1, "price_rub": 1542, "cost_cny": 58, "weight_kg": 0.7}, {"order_no": "DEMO-1002", "status": "awaiting_deliver", "product": "Багажный бокс 600 л", "sku": "BOX-600", "quantity": 1, "price_rub": 1677, "cost_cny": 72, "weight_kg": 1.2}, {"order_no": "DEMO-1003", "status": "cancelled", "product": "Плащ дождевик туристический", "sku": "RAIN-01", "quantity": 2, "price_rub": 498, "cost_cny": 18, "weight_kg": 0.4}]
    for item in samples:
        upsert_order(user["id"], item)
    return {"ok": True, "imported": len(samples)}


@app.get("/api/fees/platform")
def platform_fees(user=Depends(current_user)):
    return rows("SELECT * FROM platform_fee_rules WHERE user_id=? ORDER BY active DESC,id DESC", user["id"])


@app.post("/api/fees/platform")
def create_platform_fee(data: PlatformFeeRuleIn, user=Depends(current_user)):
    write("INSERT INTO platform_fee_rules(user_id,name,category,sku_pattern,commission_rate,tax_rate,active,updated_at) VALUES(?,?,?,?,?,?,?,?)", user["id"], data.name, data.category, data.sku_pattern, data.commission_rate, data.tax_rate, int(data.active), now_iso())
    return {"ok": True}


@app.delete("/api/fees/platform/{rule_id}")
def delete_platform_fee(rule_id: int, user=Depends(current_user)):
    write("DELETE FROM platform_fee_rules WHERE id=? AND user_id=?", rule_id, user["id"])
    return {"ok": True}


@app.get("/api/fees/logistics")
def logistics_fees(user=Depends(current_user)):
    return rows("SELECT * FROM logistics_rules WHERE user_id=? ORDER BY active DESC,min_weight_kg,id DESC", user["id"])


@app.post("/api/fees/logistics")
def create_logistics_fee(data: LogisticsRuleIn, user=Depends(current_user)):
    if data.max_weight_kg < data.min_weight_kg:
        raise HTTPException(status_code=400, detail="最大重量不能小于最小重量")
    write("INSERT INTO logistics_rules(user_id,name,category,sku_pattern,channel_name,source_sheet,formula_text,delivery_days,base_fee_cny,fee_per_kg_cny,min_weight_kg,max_weight_kg,fee_cny,active,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", user["id"], data.name, data.category, data.sku_pattern, data.channel_name, data.source_sheet, data.formula_text, data.delivery_days, data.base_fee_cny, data.fee_per_kg_cny, data.min_weight_kg, data.max_weight_kg, data.fee_cny, int(data.active), now_iso())
    return {"ok": True}


@app.delete("/api/fees/logistics/{rule_id}")
def delete_logistics_fee(rule_id: int, user=Depends(current_user)):
    write("DELETE FROM logistics_rules WHERE id=? AND user_id=?", rule_id, user["id"])
    return {"ok": True}


@app.get("/api/ai/settings")
def get_ai_settings(user=Depends(current_user)):
    cfg = ai_config()
    return {"api_key_set": bool(cfg["api_key"]), "base_url": cfg["base_url"], "model": cfg["model"], "image_model": cfg["image_model"]}


@app.post("/api/ai/settings")
def save_ai_settings(data: AISettingsIn, user=Depends(current_user)):
    current = ai_config()
    write("INSERT INTO ai_settings(id,api_key,base_url,model,image_model,updated_at) VALUES(1,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET api_key=excluded.api_key,base_url=excluded.base_url,model=excluded.model,image_model=excluded.image_model,updated_at=excluded.updated_at", data.api_key.strip() or current["api_key"], data.base_url.strip(), data.model.strip(), data.image_model.strip(), now_iso())
    return {"ok": True}


@app.get("/api/doubao/settings")
def public_ai_settings():
    cfg = ai_config()
    return {"api_key_set": bool(cfg["api_key"]), "base_url": cfg["base_url"], "model": cfg["model"], "image_model": cfg["image_model"]}


@app.post("/api/ai/test")
def test_ai(user=Depends(current_user)):
    return {"ok": True, "answer": call_doubao("请只回复：连接成功", "你是接口连通性测试助手。")}


@app.post("/api/doubao/chat")
def doubao_chat(data: ChatIn, user=Depends(current_user)):
    return {"answer": call_doubao(data.message, data.system)}


@app.post("/api/ai/listing")
def ai_listing(payload: Dict[str, Any], user=Depends(current_user)):
    prompt = f"请为 Ozon 平台生成商品 Listing：商品名：{payload.get('product_name','')}，类目：{payload.get('category','')}，关键词/卖点：{payload.get('keywords') or payload.get('selling_points','')}，价格：{payload.get('price_rub','')} 卢布。输出俄语标题、俄语五点卖点和中文运营建议。"
    return {"listing": call_doubao(prompt, "你是Ozon商品运营专家。")}


@app.post("/api/ai/image")
def ai_image(data: ImageGenerateIn, user=Depends(current_user)):
    prompt = f"{data.product_name}，{data.prompt}，{data.style}".strip("，")
    return call_doubao_image(prompt)


@app.get("/api/catalog/keywords")
def catalog_keywords(q: str = "", user=Depends(current_user)):
    if q:
        like = f"%{q}%"
        return rows("SELECT * FROM category_keyword_rules WHERE keyword LIKE ? OR category LIKE ? OR note LIKE ? ORDER BY id ASC", like, like, like)
    return rows("SELECT * FROM category_keyword_rules ORDER BY id ASC")


@app.get("/api/catalog/fees")
def catalog_fees(q: str = "", user=Depends(current_user)):
    if q:
        like = f"%{q}%"
        return rows("SELECT * FROM category_fee_matrix WHERE module LIKE ? OR category LIKE ? ORDER BY module,category", like, like)
    return rows("SELECT * FROM category_fee_matrix ORDER BY module,category")


@app.post("/api/catalog/match")
def catalog_match(payload: Dict[str, str], user=Depends(current_user)):
    text = payload.get("keyword") or payload.get("text") or ""
    return {"matches": match_category_text(text)}


@app.get("/api/marketplace/accounts")
def marketplace_accounts(user=Depends(current_user)):
    return rows("SELECT * FROM marketplace_accounts WHERE user_id=? ORDER BY platform", user["id"])


@app.post("/api/marketplace/accounts")
def save_marketplace_account(data: MarketplaceAccountIn, user=Depends(current_user)):
    if data.platform not in ("1688", "taobao", "ozon"):
        raise HTTPException(status_code=400, detail="platform 只能是 1688、taobao 或 ozon")
    write(
        "INSERT INTO marketplace_accounts(user_id,platform,account_name,status,note,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,platform) DO UPDATE SET account_name=excluded.account_name,status=excluded.status,note=excluded.note,updated_at=excluded.updated_at",
        user["id"], data.platform, data.account_name, data.status, data.note, now_iso()
    )
    return {"ok": True}


@app.get("/api/sourcing/products")
def sourcing_products(user=Depends(current_user)):
    return rows("SELECT * FROM sourcing_products WHERE user_id=? ORDER BY id DESC LIMIT 300", user["id"])


@app.post("/api/sourcing/products")
def create_sourcing_product(data: SourcingProductIn, user=Depends(current_user)):
    if data.platform not in ("1688", "taobao", "manual"):
        raise HTTPException(status_code=400, detail="platform 只能是 1688、taobao 或 manual")
    item_id = write(
        "INSERT INTO sourcing_products(user_id,platform,title,source_url,supplier_name,price_cny,domestic_shipping_cny,min_order_qty,stock,image_url,category,note,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        user["id"], data.platform, data.title, data.source_url, data.supplier_name, data.price_cny, data.domestic_shipping_cny, data.min_order_qty, data.stock, data.image_url, data.category, data.note, data.status, now_iso(), now_iso()
    )
    return {"ok": True, "id": item_id}


@app.delete("/api/sourcing/products/{item_id}")
def delete_sourcing_product(item_id: int, user=Depends(current_user)):
    write("DELETE FROM sourcing_products WHERE id=? AND user_id=?", item_id, user["id"])
    return {"ok": True}


@app.get("/api/listing/jobs")
def listing_jobs(user=Depends(current_user)):
    return rows("SELECT * FROM listing_jobs WHERE user_id=? ORDER BY id DESC", user["id"])


@app.post("/api/listing/jobs")
def create_listing_job(data: ListingJobIn, user=Depends(current_user)):
    job_id = write(
        "INSERT INTO listing_jobs(user_id,product_name,source,source_url,category,keywords,cost_cny,weight_kg,price_rub,image_url,generated_listing,ozon_shop_id,ozon_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        user["id"], data.product_name, data.source, data.source_url, data.category, data.keywords, data.cost_cny, data.weight_kg, data.price_rub, data.image_url, data.generated_listing, data.ozon_shop_id, "draft", now_iso(), now_iso()
    )
    return {"ok": True, "id": job_id}


@app.post("/api/listing/jobs/{job_id}/publish")
def publish_listing_job(job_id: int, payload: Dict[str, Any], user=Depends(current_user)):
    job = one("SELECT * FROM listing_jobs WHERE id=? AND user_id=?", job_id, user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="上品任务不存在")
    shop_id = payload.get("shop_id") or job.get("ozon_shop_id")
    shop = one("SELECT * FROM ozon_shops WHERE id=? AND user_id=?", shop_id, user["id"]) if shop_id else None
    if not shop:
        raise HTTPException(status_code=400, detail="请先绑定 Ozon 店铺，并在上品任务里选择店铺。")
    request_body = payload.get("ozon_payload") or {
        "items": [{
            "offer_id": payload.get("offer_id") or f"SKU-{job_id}",
            "name": job["product_name"],
            "price": str(job["price_rub"] or 0),
            "currency_code": "RUB",
            "vat": "0",
            "images": [job["image_url"]] if job["image_url"] else [],
            "weight": int(float(job["weight_kg"] or 0) * 1000) or 100,
            "weight_unit": "g",
        }]
    }
    resp = requests.post(OZON_API_BASE_URL.rstrip("/") + "/v3/product/import", headers={"Client-Id": shop["client_id"], "Api-Key": shop["api_key"], "Content-Type": "application/json"}, json=request_body, timeout=(15, 60))
    status = "published" if resp.ok else "failed"
    write("UPDATE listing_jobs SET ozon_shop_id=?,ozon_status=?,raw_json=?,updated_at=? WHERE id=?", shop["id"], status, resp.text[:4000], now_iso(), job_id)
    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail=f"Ozon 上品接口返回失败：{resp.text}")
    return {"ok": True, "ozon_response": resp.json()}


@app.post("/api/tickets")
def create_ticket(payload: Dict[str, str], user=Depends(current_user)):
    write("INSERT INTO tickets(user_id,customer,message,status,created_at) VALUES(?,?,?,?,?)", user["id"], payload.get("customer", "客户"), payload.get("message", ""), "open", now_iso())
    return {"ok": True}


@app.get("/api/tickets")
def tickets(user=Depends(current_user)):
    return rows("SELECT * FROM tickets WHERE user_id=? ORDER BY id DESC", user["id"])


@app.post("/api/tickets/{tid}/ai-reply")
def ticket_reply(tid: int, user=Depends(current_user)):
    ticket = one("SELECT * FROM tickets WHERE id=? AND user_id=?", tid, user["id"])
    if not ticket:
        raise HTTPException(status_code=404, detail="消息不存在")
    reply = call_doubao(f"请帮我用中文生成一段适合跨境电商客服的回复，客户消息：{ticket['message']}", "你是跨境电商客服专家，回复要礼貌、简洁、可执行。")
    write("UPDATE tickets SET ai_reply=? WHERE id=?", reply, tid)
    return {"reply": reply}


@app.get("/api/admin/overview")
def admin_overview(admin=Depends(require_admin)):
    return {"users": one("SELECT COUNT(*) n FROM users")["n"], "orders": one("SELECT COUNT(*) n FROM orders")["n"], "products": one("SELECT COUNT(*) n FROM products")["n"], "logs": rows("SELECT audit_logs.*,users.username FROM audit_logs LEFT JOIN users ON users.id=audit_logs.user_id ORDER BY audit_logs.id DESC LIMIT 20")}


@app.get("/api/admin/users")
def admin_users(admin=Depends(require_admin)):
    return rows("SELECT id,username,email,role,status,created_at FROM users ORDER BY id DESC")


@app.post("/api/admin/users")
def admin_create_user(data: AdminCreateUserIn, admin=Depends(require_admin)):
    if data.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="role 只能是 admin 或 user")
    salt, digest = hash_password(data.password)
    try:
        uid = write("INSERT INTO users(username,email,password_salt,password_hash,role,status,created_at) VALUES(?,?,?,?,?,?,?)", data.username, data.email, salt, digest, data.role, "active", now_iso())
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")
    log_action(admin["id"], "create_user", f"user={data.username}, role={data.role}")
    return {"ok": True, "id": uid}


@app.post("/api/admin/users/{uid}/role")
def set_role(uid: int, payload: Dict[str, str], admin=Depends(require_admin)):
    if payload.get("role") not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="role 只能是 admin 或 user")
    write("UPDATE users SET role=? WHERE id=?", payload["role"], uid)
    return {"ok": True}


@app.post("/api/admin/users/{uid}/status")
def set_status(uid: int, payload: Dict[str, str], admin=Depends(require_admin)):
    if payload.get("status") not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="status 只能是 active 或 disabled")
    if uid == admin["id"] and payload["status"] == "disabled":
        raise HTTPException(status_code=400, detail="不能停用当前登录的管理员账号")
    write("UPDATE users SET status=? WHERE id=?", payload["status"], uid)
    return {"ok": True}


def auto_sync_loop():
    while True:
        time.sleep(AUTO_SYNC_SECONDS)
        for shop in rows("SELECT * FROM ozon_shops WHERE auto_sync=1"):
            try:
                sync_ozon_shop(shop, days=2)
            except Exception as exc:
                write("INSERT INTO sync_logs(user_id,shop_id,status,detail,created_at) VALUES(?,?,?,?,?)", shop["user_id"], shop["id"], "error", str(exc)[:500], now_iso())


@app.on_event("startup")
def start_auto_sync_worker():
    if os.getenv("DISABLE_AUTO_SYNC", "0") != "1":
        threading.Thread(target=auto_sync_loop, daemon=True).start()


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

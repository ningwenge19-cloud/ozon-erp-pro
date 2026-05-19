# Ozon ERP Pro

面向 Ozon 跨境卖家的商业版 ERP：账号权限、Ozon 店铺绑定、订单同步、利润计算、平台费率、CEL 物流费用、选品上架、AI Listing 和 AI 图片生成。

## 本地运行

Windows 可直接双击 `start.bat`，或手动运行：

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8899
```

电脑访问：

```text
http://127.0.0.1:8899
```

手机访问同一 Wi-Fi 下的电脑局域网 IP：

```text
http://电脑IP:8899
```

如果手机打不开，通常是 Windows 防火墙没有放行 Python/8899 端口。

## Supabase

项目已支持 Supabase Postgres。线上只要配置：

```env
DATABASE_URL=postgresql://...
PGSSLMODE=require
JWT_SECRET=change-this-to-a-long-random-string
```

后端启动时会自动建表并初始化管理员、默认配置、关键词类目和平台费率。手动建表脚本在：

```text
supabase/schema.sql
```

当前已在 Supabase 项目 `ozon-erp-pro` 中创建核心表结构。

## Railway 后端

Railway 服务建议直接连接 GitHub 仓库，并设置：

```text
Root Directory: backend
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

环境变量至少配置：

```env
DATABASE_URL=Supabase pooled/session connection string
PGSSLMODE=require
JWT_SECRET=一串足够长的随机密钥
CORS_ORIGINS=https://你的前端.vercel.app
OZON_API_BASE_URL=https://api-seller.ozon.ru
AUTO_SYNC_SECONDS=900
DOUBAO_API_KEY=ark-...
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=ep-...
DOUBAO_IMAGE_MODEL=doubao-seedream-3-0-t2i-250415
```

如果前后端都放 Railway，前端会由 FastAPI 自动挂载，不需要 Vercel。

## Vercel 前端

仓库根目录已添加 `vercel.json`，Vercel 会把 `frontend` 当静态站点发布。

前端连接 Railway 后端有两种方式：

1. 修改 `frontend/config.js`：

```js
window.OZON_ERP_API_BASE_URL = "https://你的-railway-后端域名";
```

2. 临时测试时在 Vercel 地址后加参数：

```text
https://你的前端.vercel.app?api=https://你的-railway-后端域名
```

## 商业化注意

- 不要把 Ozon API Key、豆包 Key、Supabase 密码写进前端代码。
- 上线后第一时间修改默认管理员密码，或用管理员后台创建新管理员后停用旧账号。
- `ENABLE_DEMO_ORDERS` 默认关闭，生产环境不会导入演示订单。
- 平台费率和物流规则都写入数据库，订单同步后会按数据库规则计算利润。

# Ozon ERP Pro

Ozon SaaS ERP for Ozon cross-border sellers. The local project is ready at `C:\Users\35395\Documents\New project\ozon_saas_erp` and runs at `http://127.0.0.1:8899`.

## Features

- Ozon shop binding with Seller API `Client-Id` and `API-Key`
- Manual and scheduled Ozon order sync
- Platform fee / tax rule management stored in SQLite
- CEL logistics-rate import and automatic logistics calculation
- Order revenue, platform fee, tax, logistics fee, and profit calculation
- Doubao AI assistant settings and chat/listing tools
- Admin user management and app settings

## Local Run

Double-click `start.bat`, or run:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8899
```

Then open `http://127.0.0.1:8899`.

## Notes

The login page intentionally does not display the admin account or password. Ask the project owner directly for the initial credentials, then change the password after deployment.

The CEL shipping workbook has been imported locally into the database as logistics rules. The extracted rules are also available locally as `data/cel_ozon_rates.json`.

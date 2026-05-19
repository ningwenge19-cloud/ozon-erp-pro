import json
import re
import sqlite3
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "ozon_erp.db"
XLSX_PATH = ROOT / "data" / "CEL产品资费表 V4.8.xlsx"


def clean(value):
    return str(value or "").strip()


def parse_weight(text):
    text = clean(text).lower().replace(" ", "")
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
    if "-" in text and len(nums) >= 2:
        return nums[0], nums[1]
    if "≤" in text or "<=" in text or "不超过" in text or len(nums) == 1:
        return 0, nums[0] if nums else 999999
    if len(nums) >= 2:
        return nums[0], nums[1]
    return 0, 999999


def parse_formula(text):
    text = clean(text).replace(" ", "")
    base = 0.0
    per_kg = 0.0
    kg_match = re.search(r"(\d+(?:\.\d+)?)元/kg", text, re.I)
    gram_match = re.search(r"(\d+(?:\.\d+)?)元/克", text, re.I)
    ticket_match = re.search(r"\+?(\d+(?:\.\d+)?)元/票", text, re.I)
    if kg_match:
        per_kg = float(kg_match.group(1))
    if gram_match:
        per_kg = float(gram_match.group(1)) * 1000
    if ticket_match:
        base = float(ticket_match.group(1))
    return base, per_kg


def iter_ozon_rows(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    for ws in wb.worksheets:
        if "OZON" not in ws.title.upper():
            continue
        current_category = ""
        current_weight = ""
        for row in ws.iter_rows(min_row=3, values_only=True):
            cells = [clean(x) for x in row]
            if not any(cells):
                continue
            if ws.title in ("OZON-rFBS", "OZON-FBP"):
                category, channel, _delivery, days, formula, _logic, _return, weight = cells[:8]
            else:
                channel, days, formula, weight = cells[:4]
                category = channel
            if category:
                current_category = category.replace("\n", " ")
            if weight:
                current_weight = weight
            if not channel or "CEL" not in channel or not formula:
                continue
            base, per_kg = parse_formula(formula)
            if base == 0 and per_kg == 0:
                continue
            min_w, max_w = parse_weight(current_weight)
            normalized_channel = " ".join(channel.split())
            yield {
                "name": normalized_channel[:80],
                "category": current_category[:80],
                "sku_pattern": "",
                "channel_name": normalized_channel,
                "source_sheet": ws.title,
                "formula_text": formula,
                "delivery_days": days,
                "base_fee_cny": base,
                "fee_per_kg_cny": per_kg,
                "min_weight_kg": min_w,
                "max_weight_kg": max_w,
                "fee_cny": 0,
                "active": 1,
            }


def main():
    if not XLSX_PATH.exists():
        raise SystemExit(f"Missing file: {XLSX_PATH}")
    rules = list(iter_ozon_rows(XLSX_PATH))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("DELETE FROM logistics_rules WHERE user_id=1 AND source_sheet LIKE 'OZON%'")
    for rule in rules:
        conn.execute(
            """
            INSERT INTO logistics_rules(user_id,name,category,sku_pattern,channel_name,source_sheet,formula_text,delivery_days,base_fee_cny,fee_per_kg_cny,min_weight_kg,max_weight_kg,fee_cny,active,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
            """,
            (
                1,
                rule["name"],
                rule["category"],
                rule["sku_pattern"],
                rule["channel_name"],
                rule["source_sheet"],
                rule["formula_text"],
                rule["delivery_days"],
                rule["base_fee_cny"],
                rule["fee_per_kg_cny"],
                rule["min_weight_kg"],
                rule["max_weight_kg"],
                rule["fee_cny"],
                rule["active"],
            ),
        )
    conn.commit()
    conn.close()
    print(json.dumps({"imported": len(rules)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""
run_analysis.py

Loads the simulated CSVs into SQLite, runs the analysis queries in
sql/02_analysis_queries.sql, and writes:
  data/supplier_retail.db        (gitignored)
  dashboard/data.json            (feeds the dashboard)
  excel/pivot_*.csv              (pivot-ready tables, see excel/EXCEL_GUIDE.md)
Standard library only. Run generate_data.py first.
"""
import csv
import json
import os
import re
import sqlite3

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
D = lambda *p: os.path.join(ROOT, *p)

db_path = D("data", "supplier_retail.db")
if os.path.exists(db_path):
    os.remove(db_path)
con = sqlite3.connect(db_path)
con.row_factory = sqlite3.Row
con.executescript(open(D("sql", "01_schema.sql")).read())


def load(table, fname, cols, conv):
    with open(D("data", fname)) as f:
        rows = [[conv.get(c, str)(r[c]) for c in cols] for r in csv.DictReader(f)]
    con.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", rows)
    print(f"loaded {len(rows):,} rows into {table}")


I, F = int, float
load("dim_item", "dim_item.csv", ["item_id", "item_name", "category", "brand", "base_price", "unit_cost"], {"item_id": I, "base_price": F, "unit_cost": F})
load("dim_store", "dim_store.csv", ["store_id", "store_name", "region", "format", "cluster"], {"store_id": I})
load("dim_date", "dim_date.csv", ["week_start", "week_num", "month", "year"], {"week_num": I, "year": I})
load("dim_promo", "dim_promo.csv", ["promo_id", "item_id", "start_week", "weeks", "promo_type", "discount_pct"], {"promo_id": I, "item_id": I, "weeks": I, "discount_pct": F})
load("planogram", "planogram.csv", ["cluster", "item_id", "facings", "linear_ft"], {"item_id": I, "facings": I, "linear_ft": F})
load("fact_pos", "fact_pos_weekly.csv", ["week_start", "item_id", "store_id", "units", "net_sales", "cost", "in_stock_days", "promo_flag"],
     {"item_id": I, "store_id": I, "units": I, "net_sales": F, "cost": F, "in_stock_days": I, "promo_flag": I})
con.commit()

sql = open(D("sql", "02_analysis_queries.sql")).read()
blocks = re.split(r"^-- name: (\w+)\s*$", sql, flags=re.M)
queries = dict(zip(blocks[1::2], blocks[2::2]))

out = {}
for name, q in queries.items():
    if name == "promo_by_type" or name == "promo_by_item":
        pass
    rows = con.execute(q).fetchall()
    out[name] = [dict(r) for r in rows]
    print(f"query {name}: {len(rows)} rows")
    if name == "promo_weeks":
        con.execute("DROP TABLE IF EXISTS promo_weeks_tbl")
        con.execute("CREATE TABLE promo_weeks_tbl AS " + re.sub(r"^--.*$", "", q, flags=re.M).strip().rstrip(";"))
        con.commit()

# drop the large per-week promo rows from the dashboard payload; keep a compact event view
out["promo_weeks"] = [{"item_id": r["item_id"], "week_num": r["week_num"], "promo_type": r["promo_type"], "lift": r["lift"], "net_incr_profit": r["net_incr_profit"]} for r in out["promo_weeks"]]

# monthly chain trend for charts
out["monthly"] = [dict(r) for r in con.execute(
    "SELECT d.month, SUM(f.net_sales) AS sales, SUM(f.units) AS units "
    "FROM fact_pos f JOIN dim_date d USING (week_start) GROUP BY d.month ORDER BY d.month")]
out["meta"] = {
    "items": con.execute("SELECT COUNT(*) FROM dim_item").fetchone()[0],
    "stores": con.execute("SELECT COUNT(*) FROM dim_store").fetchone()[0],
    "weeks": con.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0],
    "pos_rows": con.execute("SELECT COUNT(*) FROM fact_pos").fetchone()[0],
    "first_week": con.execute("SELECT MIN(week_start) FROM dim_date").fetchone()[0],
    "last_week": con.execute("SELECT MAX(week_start) FROM dim_date").fetchone()[0],
    "promo_events": con.execute("SELECT COUNT(*) FROM dim_promo").fetchone()[0],
}
with open(D("dashboard", "data.json"), "w") as f:
    json.dump(out, f, separators=(",", ":"))
print("wrote dashboard/data.json")


def dump(name, rows):
    with open(D("excel", name), "w", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows([{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in rows])
    print(f"wrote excel/{name}")


dump("pivot_item_month.csv", [dict(r) for r in con.execute(
    "SELECT d.month, i.category, i.item_name, s.region, SUM(f.units) AS units, ROUND(SUM(f.net_sales),2) AS net_sales, "
    "ROUND(SUM(f.cost),2) AS cost, SUM(f.in_stock_days) AS in_stock_days, 7*COUNT(*) AS possible_days "
    "FROM fact_pos f JOIN dim_item i USING (item_id) JOIN dim_store s USING (store_id) JOIN dim_date d USING (week_start) "
    "GROUP BY d.month, i.item_id, s.region ORDER BY d.month, i.category, i.item_name, s.region")])
dump("pivot_category.csv", out["category"])
dump("pivot_items.csv", out["items"])
dump("pivot_space.csv", out["space"])
dump("pivot_instock.csv", out["instock_by_item"])
dump("pivot_promo_by_item.csv", out["promo_by_item"])
con.close()

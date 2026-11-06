"""
generate_data.py

Generates SIMULATED weekly point-of-sale data for a made-up consumer goods
supplier selling through a made-up big-box retailer. Nothing here is real:
the supplier, brands, items, stores and numbers are all invented, and the
data does not come from any real retailer or data provider.

Seeded, so every run produces identical files. Standard library only.

Writes ../data/:
  dim_item.csv, dim_store.csv, dim_date.csv, dim_promo.csv
  planogram.csv           shelf space (facings, linear feet) per item per store cluster
  fact_pos_weekly.csv     item x store x week (large; not committed)
  fact_pos_monthly.csv    item x store x month rollup (committed, Power BI ready)
"""

import csv
import math
import os
import random
from collections import defaultdict
from datetime import date, timedelta

SEED = 20261106
random.seed(SEED)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(OUT, exist_ok=True)

N_WEEKS = 156                      # 3 years of weeks
START = date(2023, 11, 5)          # a Sunday; weeks run Sun-Sat, week_start = Sunday
N_STORES = 40

# category -> (seasonality peak month, seasonal amplitude, (price low, price high), margin range)
CATEGORIES = {
    "Cleaning":       (3,  0.10, (3.5, 9.0),  (0.30, 0.42)),
    "Laundry":        (6,  0.05, (6.0, 16.0), (0.28, 0.38)),
    "Personal Care":  (7,  0.12, (3.0, 8.5),  (0.38, 0.52)),
    "Health & Wellness": (1, 0.25, (4.5, 14.0), (0.35, 0.50)),
    "Pet":            (12, 0.06, (5.0, 22.0), (0.30, 0.40)),
    "Seasonal Home":  (12, 0.60, (4.0, 18.0), (0.33, 0.45)),
}
ITEMS_PER_CAT = {"Cleaning": 6, "Laundry": 5, "Personal Care": 6, "Health & Wellness": 5, "Pet": 4, "Seasonal Home": 4}

ADJ = ["Fresh", "Bright", "Pure", "Gentle", "Power", "Daily", "Active", "Ultra", "Easy", "Classic", "Clear", "Zest"]
NOUN = {
    "Cleaning": ["Surface Spray", "Glass Cleaner", "Disinfectant Wipes", "Floor Cleaner", "Bathroom Foam", "Kitchen Degreaser"],
    "Laundry": ["Detergent", "Fabric Softener", "Stain Remover", "Dryer Sheets", "Laundry Pods"],
    "Personal Care": ["Body Wash", "Hand Soap", "Shampoo", "Conditioner", "Deodorant", "Lotion"],
    "Health & Wellness": ["Cold Relief", "Vitamin C Chews", "Pain Relief Gel", "Allergy Tablets", "Sleep Aid"],
    "Pet": ["Dog Treats", "Cat Litter", "Pet Shampoo", "Chew Toy Set"],
    "Seasonal Home": ["Holiday Candle", "Air Freshener Set", "Storage Bins", "Door Mat"],
}
BRANDS = ["Hollis & Vale", "Brightfield", "NorthPeak Home", "Tandem Care"]

REGIONS = ["Northwest", "Southwest", "Central", "Southeast", "Northeast", "Mid-Atlantic"]
FORMATS = [("Supercenter", 1.35), ("Standard", 1.0), ("Neighborhood", 0.62)]


def build_items():
    items, iid = [], 1
    for cat, n in ITEMS_PER_CAT.items():
        _, _, (plo, phi), (mlo, mhi) = CATEGORIES[cat]
        names = random.sample(NOUN[cat], n)
        for nm in names:
            price = round(random.uniform(plo, phi) * 4) / 4 - 0.01
            margin = random.uniform(mlo, mhi)
            items.append({
                "item_id": iid,
                "item_name": f"{random.choice(ADJ)} {nm}",
                "category": cat,
                "brand": random.choice(BRANDS),
                "base_price": round(price, 2),
                "unit_cost": round(price * (1 - margin), 2),
                "base_velocity": round(random.lognormvariate(1.3, 0.55), 2),  # units/store/week
                "facing_width_in": random.choice([3, 4, 5, 6]),
                "stockout_prob": round(random.uniform(0.02, 0.12), 3),
                "trend": round(random.uniform(-0.08, 0.12), 3),               # annual growth
            })
            iid += 1
    # make item names unique
    seen = set()
    for it in items:
        base, k = it["item_name"], 2
        while it["item_name"] in seen:
            it["item_name"] = f"{base} {k}"
            k += 1
        seen.add(it["item_name"])
    return items


def build_stores():
    stores = []
    for sid in range(1, N_STORES + 1):
        fmt, size = random.choices(FORMATS, weights=[0.3, 0.5, 0.2])[0]
        region = REGIONS[(sid - 1) % len(REGIONS)]
        stores.append({
            "store_id": sid,
            "store_name": f"Store {1000 + sid}",
            "region": region,
            "format": fmt,
            "size_index": round(size * random.uniform(0.85, 1.15), 3),
            "cluster": {"Supercenter": "A", "Standard": "B", "Neighborhood": "C"}[fmt],
        })
    return stores


def build_planogram(items, stores):
    """Facings per item per store cluster. Bigger formats give more facings.
    Facings are assigned semi-independently of velocity, so some items are
    over- or under-spaced: that is what the space analysis looks for."""
    rows = []
    for cl, mult in (("A", 1.6), ("B", 1.0), ("C", 0.6)):
        for it in items:
            base = random.choice([1, 2, 2, 3, 3, 4])
            facings = max(1, round(base * mult))
            width_ft = it["facing_width_in"] * facings / 12
            rows.append({"cluster": cl, "item_id": it["item_id"], "facings": facings, "linear_ft": round(width_ft, 2)})
    return rows


def week_start(w):
    return START + timedelta(weeks=w)


def main():
    items = build_items()
    stores = build_stores()
    plano = build_planogram(items, stores)
    plano_ft = {(p["cluster"], p["item_id"]): p for p in plano}

    # promo calendar: each item gets ~5 promo events/yr, 1-3 weeks each, chain-wide
    promos, promo_wk = [], defaultdict(dict)   # (item) -> {week: (type, disc)}
    pid = 1
    for it in items:
        w = random.randint(0, 8)
        while w < N_WEEKS:
            length = random.choice([1, 2, 2, 3])
            ptype = random.choice(["TPR", "TPR", "Feature", "Display"])
            disc = {"TPR": random.choice([0.10, 0.15, 0.20]), "Feature": random.choice([0.15, 0.20, 0.25]), "Display": random.choice([0.10, 0.15])}[ptype]
            lift = {"TPR": random.uniform(1.25, 1.6), "Feature": random.uniform(1.6, 2.4), "Display": random.uniform(1.4, 2.0)}[ptype]
            for k in range(length):
                if w + k < N_WEEKS:
                    promo_wk[it["item_id"]][w + k] = (ptype, disc, lift)
            promos.append({"promo_id": pid, "item_id": it["item_id"], "start_week": week_start(w).isoformat(),
                           "weeks": length, "promo_type": ptype, "discount_pct": disc})
            pid += 1
            w += length + random.randint(5, 14)

    cat_info = {c: CATEGORIES[c] for c in CATEGORIES}
    weekly_path = os.path.join(OUT, "fact_pos_weekly.csv")
    monthly = defaultdict(lambda: [0, 0.0, 0.0, 0, 0, 0])  # units, sales, cost, instock_days, days, promo_weeks

    with open(weekly_path, "w", newline="") as fw:
        wr = csv.writer(fw)
        wr.writerow(["week_start", "item_id", "store_id", "units", "net_sales", "cost", "in_stock_days", "promo_flag"])
        for w in range(N_WEEKS):
            ws = week_start(w)
            mid = ws + timedelta(days=3)
            yrs = w / 52.0
            for it in items:
                peak, amp, _, _ = cat_info[it["category"]]
                season = 1 + amp * math.cos(2 * math.pi * (mid.month - peak) / 12)
                growth = (1 + it["trend"]) ** yrs
                promo = promo_wk[it["item_id"]].get(w)
                for st in stores:
                    p = plano_ft[(st["cluster"], it["item_id"])]
                    space_effect = 0.75 + 0.25 * p["facings"]**0.5   # more facings help, with diminishing returns
                    mean = it["base_velocity"] * st["size_index"] * season * growth * space_effect
                    price = it["base_price"]
                    flag = 0
                    if promo:
                        ptype, disc, lift = promo
                        mean *= lift
                        price = round(price * (1 - disc), 2)
                        flag = 1
                    # days in stock: usually 7, sometimes a stockout
                    if random.random() < it["stockout_prob"]:
                        days = random.choice([0, 1, 2, 3, 4, 5, 6])
                    else:
                        days = 7
                    mean *= days / 7
                    units = max(0, int(random.gauss(mean, math.sqrt(max(mean, 0.5)) * 0.9) + 0.5))
                    if days == 0:
                        units = 0
                    sales = round(units * price, 2)
                    cost = round(units * it["unit_cost"], 2)
                    wr.writerow([ws.isoformat(), it["item_id"], st["store_id"], units, sales, cost, days, flag])
                    key = (mid.strftime("%Y-%m"), it["item_id"], st["store_id"])
                    m = monthly[key]
                    m[0] += units; m[1] += sales; m[2] += cost; m[3] += days; m[4] += 7; m[5] += flag

    def write(name, rows, cols):
        with open(os.path.join(OUT, name), "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            wr.writeheader()
            wr.writerows(rows)
        print(f"wrote {len(rows):,} rows -> data/{name}")

    write("dim_item.csv", items, ["item_id", "item_name", "category", "brand", "base_price", "unit_cost"])
    write("dim_store.csv", stores, ["store_id", "store_name", "region", "format", "cluster"])
    write("planogram.csv", plano, ["cluster", "item_id", "facings", "linear_ft"])
    write("dim_promo.csv", promos, ["promo_id", "item_id", "start_week", "weeks", "promo_type", "discount_pct"])
    dates = [{"week_start": week_start(w).isoformat(), "week_num": w + 1, "month": (week_start(w) + timedelta(days=3)).strftime("%Y-%m"),
              "year": (week_start(w) + timedelta(days=3)).year} for w in range(N_WEEKS)]
    write("dim_date.csv", dates, ["week_start", "week_num", "month", "year"])
    mrows = [{"month": k[0], "item_id": k[1], "store_id": k[2], "units": v[0], "net_sales": round(v[1], 2), "cost": round(v[2], 2),
              "in_stock_days": v[3], "total_days": v[4], "promo_weeks": v[5]} for k, v in sorted(monthly.items())]
    write("fact_pos_monthly.csv", mrows, ["month", "item_id", "store_id", "units", "net_sales", "cost", "in_stock_days", "total_days", "promo_weeks"])
    print(f"weekly fact rows: {N_WEEKS * len(items) * len(stores):,} (data/fact_pos_weekly.csv, not committed)")


if __name__ == "__main__":
    main()

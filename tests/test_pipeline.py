"""Checks that the committed data and dashboard numbers reconcile. Run from the repo root:
    python3 tests/test_pipeline.py
Needs data/fact_pos_monthly.csv and dashboard/data.json (run the ETL first)."""
import csv, json, os, unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
P = lambda *a: os.path.join(ROOT, *a)


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.data = json.load(open(P("dashboard", "data.json")))
        self.monthly = list(csv.DictReader(open(P("data", "fact_pos_monthly.csv"))))
        self.months = sorted({r["month"] for r in self.monthly})

    def test_total_sales_matches_weekly_trend(self):
        # monthly rollup total vs weekly trend total
        total = sum(float(r["net_sales"]) for r in self.monthly)
        weekly_total = sum(w["sales"] for w in self.data["weekly_trend"])
        self.assertAlmostEqual(total, weekly_total, delta=1.0)

    def test_category_shares_sum_to_one(self):
        self.assertAlmostEqual(sum(c["share"] for c in self.data["category"]), 1.0, places=6)

    def test_category_sales_sum_to_kpi(self):
        self.assertAlmostEqual(sum(c["ltm_sales"] for c in self.data["category"]), self.data["kpis"][0]["ltm_sales"], delta=0.01)

    def test_item_shares_per_category(self):
        by = {}
        for i in self.data["items"]:
            by[i["category"]] = by.get(i["category"], 0) + i["share_of_category"]
        for c, v in by.items():
            self.assertAlmostEqual(v, 1.0, places=6, msg=c)

    def test_instock_between_0_and_1(self):
        self.assertTrue(0 < self.data["kpis"][0]["ltm_instock"] <= 1)
        for r in self.data["instock_by_item"]:
            self.assertTrue(0 < r["instock"] <= 1)

    def test_monthly_instock_days_valid(self):
        for r in self.monthly:
            self.assertLessEqual(int(r["in_stock_days"]), int(r["total_days"]))

    def test_no_negative_sales(self):
        self.assertTrue(all(float(r["net_sales"]) >= 0 and int(r["units"]) >= 0 for r in self.monthly))


if __name__ == "__main__":
    unittest.main(verbosity=2)

# Excel guide (pivot tables and formulas)

All data is simulated. The `pivot_*.csv` files in this folder are ready to open in Excel. No `.xlsx` workbook is included yet; these steps rebuild the analysis in Excel from the CSVs.

## Files
| File | Grain | Use |
|---|---|---|
| `pivot_item_month.csv` | month x item x region | main pivot source (units, net_sales, cost, in_stock_days, possible_days) |
| `pivot_category.csv` | category | check totals against your pivot |
| `pivot_items.csv` | item | rank, share of category, YoY from SQL (to check your formulas) |
| `pivot_space.csv` | item | sales per linear foot and space index |
| `pivot_instock.csv` | item | in-stock % and estimated lost sales |
| `pivot_promo_by_item.csv` | item | promo lift and net incremental profit |

## 1. Category sales and YoY (PivotTable)
1. Open `pivot_item_month.csv`, Insert > PivotTable.
2. Rows: `category`. Values: Sum of `net_sales`. Filter: `month` (select the last 12 months, 2025-11 to 2026-10).
3. Duplicate the pivot for the prior 12 months (2024-11 to 2025-10).
4. Add a column: `=Current/Prior - 1` for YoY. Compare to `pivot_category.csv` (`yoy`).

## 2. Share of category and rank
In a table from `pivot_items.csv` (or a pivot of item sales):
- Share of category: `=D2/SUMIFS($D:$D,$B:$B,B2)` (D = ltm_sales, B = category)
- Rank within category: `=COUNTIFS($B:$B,B2,$D:$D,">"&D2)+1`

## 3. Margin % and in-stock %
- Add calculated fields or helper columns: `gross margin % = (net_sales - cost) / net_sales`; `in-stock % = in_stock_days / possible_days`.

## 4. Sales per linear foot (lookup)
- From `pivot_space.csv`: `=sales_per_ft / cat_sales_per_ft` is the space index.
- To rebuild it: `planogram.csv` in `/data` has `linear_ft` by store cluster; multiply by the number of stores per cluster (`COUNTIF` on `dim_store.csv`) and divide item sales by that total. Use `INDEX/MATCH` (or XLOOKUP if available) to pull `linear_ft`.

## 5. Where Power Query fits (not included)
Loading the CSVs through Power Query (Get Data > From Text/CSV) and merging `dim_item` and `dim_store` into the fact would remove the need for the pre-joined pivot file. That workflow is not built or tested here; it is a suggested next step for Max.

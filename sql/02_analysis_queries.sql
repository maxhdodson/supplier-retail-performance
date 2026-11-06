-- 02_analysis_queries.sql
-- Analytical queries behind the dashboard. All data is simulated.
-- Each block starts with "-- name: <id>"; etl/run_analysis.py runs them in order.
--
-- Time windows: the data has 156 weeks. "LTM" = last 52 weeks (week_num 105-156),
-- "PY" = the 52 weeks before that (week_num 53-104). Week 1 to 52 is not used
-- for year-over-year comparisons.

-- name: kpis
-- Headline numbers for the last 52 weeks vs the prior 52.
WITH w AS (
    SELECT d.week_num, f.units, f.net_sales, f.cost, f.in_stock_days, f.promo_flag
    FROM fact_pos f JOIN dim_date d USING (week_start)
), agg AS (
    SELECT
        SUM(CASE WHEN week_num > 104 THEN net_sales END)                       AS ltm_sales,
        SUM(CASE WHEN week_num BETWEEN 53 AND 104 THEN net_sales END)          AS py_sales,
        SUM(CASE WHEN week_num > 104 THEN units END)                           AS ltm_units,
        SUM(CASE WHEN week_num BETWEEN 53 AND 104 THEN units END)              AS py_units,
        SUM(CASE WHEN week_num > 104 THEN net_sales - cost END)                AS ltm_margin,
        SUM(CASE WHEN week_num > 104 THEN in_stock_days END) * 1.0
            / (7 * SUM(CASE WHEN week_num > 104 THEN 1 END))                   AS ltm_instock,
        SUM(CASE WHEN week_num > 104 AND promo_flag = 1 THEN net_sales END) * 1.0
            / SUM(CASE WHEN week_num > 104 THEN net_sales END)                 AS ltm_promo_share
    FROM w
)
SELECT ltm_sales, py_sales, ltm_sales * 1.0 / py_sales - 1 AS sales_yoy,
       ltm_units, py_units, ltm_units * 1.0 / py_units - 1 AS units_yoy,
       ltm_margin, ltm_margin / ltm_sales AS gm_pct, ltm_instock, ltm_promo_share
FROM agg;

-- name: category
-- Category sales, YoY, margin and share of total (window SUM() OVER ()).
WITH c AS (
    SELECT i.category,
           SUM(CASE WHEN d.week_num > 104 THEN f.net_sales END)               AS ltm_sales,
           SUM(CASE WHEN d.week_num BETWEEN 53 AND 104 THEN f.net_sales END)  AS py_sales,
           SUM(CASE WHEN d.week_num > 104 THEN f.net_sales - f.cost END)      AS ltm_margin,
           SUM(CASE WHEN d.week_num > 104 THEN f.units END)                   AS ltm_units
    FROM fact_pos f JOIN dim_item i USING (item_id) JOIN dim_date d USING (week_start)
    GROUP BY i.category
)
SELECT category, ltm_sales, py_sales,
       ltm_sales * 1.0 / py_sales - 1                AS yoy,
       ltm_margin / ltm_sales                        AS gm_pct,
       ltm_units,
       ltm_sales * 1.0 / SUM(ltm_sales) OVER ()      AS share
FROM c ORDER BY ltm_sales DESC;

-- name: items
-- Item ranking within category: share of category and rank (window functions).
WITH s AS (
    SELECT i.item_id, i.item_name, i.category, i.brand,
           SUM(CASE WHEN d.week_num > 104 THEN f.net_sales END)               AS ltm_sales,
           SUM(CASE WHEN d.week_num BETWEEN 53 AND 104 THEN f.net_sales END)  AS py_sales,
           SUM(CASE WHEN d.week_num > 104 THEN f.net_sales - f.cost END)      AS ltm_margin,
           SUM(CASE WHEN d.week_num > 104 THEN f.units END)                   AS ltm_units
    FROM fact_pos f JOIN dim_item i USING (item_id) JOIN dim_date d USING (week_start)
    GROUP BY i.item_id
)
SELECT item_id, item_name, category, brand, ltm_sales, py_sales,
       ltm_sales * 1.0 / py_sales - 1                                        AS yoy,
       ltm_margin / ltm_sales                                                AS gm_pct,
       ltm_units,
       ltm_sales * 1.0 / SUM(ltm_sales) OVER (PARTITION BY category)         AS share_of_category,
       RANK() OVER (PARTITION BY category ORDER BY ltm_sales DESC)           AS rank_in_category,
       RANK() OVER (ORDER BY ltm_sales DESC)                                 AS rank_overall
FROM s ORDER BY ltm_sales DESC;

-- name: weekly_trend
-- Chain weekly sales, 4-week moving average, and same week last year (LAG 52).
WITH wk AS (
    SELECT d.week_num, d.week_start, SUM(f.net_sales) AS sales, SUM(f.units) AS units,
           SUM(f.in_stock_days) * 1.0 / (7 * COUNT(*)) AS instock
    FROM fact_pos f JOIN dim_date d USING (week_start)
    GROUP BY d.week_num, d.week_start
)
SELECT week_num, week_start, sales, units, instock,
       AVG(sales) OVER (ORDER BY week_num ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) AS sales_ma4,
       LAG(sales, 52) OVER (ORDER BY week_num)                                      AS sales_ly,
       sales * 1.0 / LAG(sales, 52) OVER (ORDER BY week_num) - 1                    AS yoy
FROM wk ORDER BY week_num;

-- name: promo_weeks
-- Item-week chain totals with a non-promo baseline: the average units of the
-- same item's NON-promo weeks within 4 weeks either side (AVG ignores NULLs).
-- Net incremental profit = promo-week gross profit minus the gross profit the
-- baseline units would have earned at the regular price.
WITH iw AS (
    SELECT f.item_id, d.week_num, d.week_start,
           SUM(f.units) AS units, SUM(f.net_sales) AS sales, SUM(f.cost) AS cost,
           MAX(f.promo_flag) AS promo
    FROM fact_pos f JOIN dim_date d USING (week_start)
    GROUP BY f.item_id, d.week_num, d.week_start
), b AS (
    SELECT *,
           AVG(CASE WHEN promo = 0 THEN units END) OVER (
               PARTITION BY item_id ORDER BY week_num ROWS BETWEEN 4 PRECEDING AND 4 FOLLOWING) AS base_units
    FROM iw
)
SELECT b.item_id, b.week_num, b.week_start, b.units, b.sales, b.cost, b.base_units,
       p.promo_type, p.discount_pct,
       b.units * 1.0 / b.base_units - 1                                         AS lift,
       (b.sales - b.cost) - b.base_units * (i.base_price - i.unit_cost)         AS net_incr_profit,
       b.units * i.base_price * p.discount_pct                                  AS discount_cost
FROM b
JOIN dim_item i USING (item_id)
JOIN dim_promo p ON p.item_id = b.item_id
     AND b.week_start >= p.start_week
     AND b.week_start < date(p.start_week, '+' || (p.weeks * 7) || ' days')
WHERE b.promo = 1 AND b.base_units IS NOT NULL AND b.base_units > 0
ORDER BY b.item_id, b.week_num;

-- name: promo_by_type
-- Average lift and net incremental profit by promo type.
WITH pw AS ( SELECT * FROM promo_weeks_tbl )
SELECT promo_type,
       COUNT(*)                          AS promo_weeks,
       AVG(lift)                         AS avg_lift,
       SUM(net_incr_profit)              AS net_incr_profit,
       SUM(discount_cost)                AS discount_cost,
       SUM(net_incr_profit) / SUM(discount_cost) AS profit_per_discount_dollar
FROM pw GROUP BY promo_type ORDER BY avg_lift DESC;

-- name: promo_by_item
WITH pw AS ( SELECT * FROM promo_weeks_tbl )
SELECT i.item_name, i.category, COUNT(*) AS promo_weeks, AVG(pw.lift) AS avg_lift,
       SUM(pw.net_incr_profit) AS net_incr_profit, SUM(pw.discount_cost) AS discount_cost
FROM pw JOIN dim_item i USING (item_id)
GROUP BY i.item_id ORDER BY net_incr_profit DESC;

-- name: instock_by_item
-- In-stock % and estimated lost sales, last 52 weeks.
-- Lost units for a store-week = days out of stock x the item's units per in-stock
-- day in the same region and week, valued at the item's regular price
-- (a simple estimate, see README).
WITH r AS (
    SELECT f.item_id, f.week_start, s.region,
           SUM(f.units) * 1.0 / NULLIF(SUM(f.in_stock_days), 0) AS ipd
    FROM fact_pos f JOIN dim_store s USING (store_id)
    GROUP BY f.item_id, f.week_start, s.region
), lost AS (
    SELECT f.item_id,
           SUM(f.in_stock_days) * 1.0 / (7 * COUNT(*))                    AS instock,
           SUM(f.net_sales)                                               AS sales,
           SUM((7 - f.in_stock_days) * r.ipd)                             AS lost_units,
           SUM(f.units)                                                   AS units
    FROM fact_pos f
    JOIN dim_store s USING (store_id)
    JOIN dim_date d USING (week_start)
    JOIN r ON r.item_id = f.item_id AND r.week_start = f.week_start AND r.region = s.region
    WHERE d.week_num > 104
    GROUP BY f.item_id
)
SELECT i.item_name, i.category, l.instock, l.sales, l.lost_units, l.units,
       l.lost_units * i.base_price                      AS est_lost_sales,
       l.lost_units * 1.0 / (l.units + l.lost_units)    AS lost_unit_pct
FROM lost l JOIN dim_item i USING (item_id)
ORDER BY est_lost_sales DESC;

-- name: space
-- Sales per linear foot of shelf by item, indexed to its category (planogram view).
-- Linear feet are summed over the stores that carry each cluster's planogram.
WITH ft AS (
    SELECT s.cluster, COUNT(*) AS stores FROM dim_store s GROUP BY s.cluster
), item_ft AS (
    SELECT p.item_id, SUM(p.linear_ft * ft.stores) AS store_feet, SUM(p.facings * ft.stores) AS store_facings
    FROM planogram p JOIN ft USING (cluster) GROUP BY p.item_id
), sales AS (
    SELECT f.item_id, SUM(f.net_sales) AS ltm_sales, SUM(f.net_sales - f.cost) AS ltm_margin
    FROM fact_pos f JOIN dim_date d USING (week_start) WHERE d.week_num > 104 GROUP BY f.item_id
), x AS (
    SELECT i.item_id, i.item_name, i.category, s.ltm_sales, s.ltm_margin, t.store_feet, t.store_facings,
           s.ltm_sales / t.store_feet                                      AS sales_per_ft,
           s.ltm_margin / t.store_feet                                     AS margin_per_ft,
           SUM(s.ltm_sales) OVER (PARTITION BY i.category)
             / SUM(t.store_feet) OVER (PARTITION BY i.category)            AS cat_sales_per_ft
    FROM dim_item i JOIN sales s USING (item_id) JOIN item_ft t USING (item_id)
)
SELECT *, sales_per_ft / cat_sales_per_ft AS space_index,
       CASE WHEN sales_per_ft / cat_sales_per_ft >= 1.25 THEN 'Add space'
            WHEN sales_per_ft / cat_sales_per_ft <= 0.75 THEN 'Review space'
            ELSE 'Balanced' END AS space_flag
FROM x ORDER BY space_index DESC;

-- name: region
-- Regional sales per store, indexed to the chain average, with YoY.
WITH r AS (
    SELECT s.region, COUNT(DISTINCT s.store_id) AS stores,
           SUM(CASE WHEN d.week_num > 104 THEN f.net_sales END)               AS ltm_sales,
           SUM(CASE WHEN d.week_num BETWEEN 53 AND 104 THEN f.net_sales END)  AS py_sales,
           SUM(CASE WHEN d.week_num > 104 THEN f.in_stock_days END) * 1.0
               / (7 * SUM(CASE WHEN d.week_num > 104 THEN 1 END))             AS instock
    FROM fact_pos f JOIN dim_store s USING (store_id) JOIN dim_date d USING (week_start)
    GROUP BY s.region
)
SELECT region, stores, ltm_sales, ltm_sales * 1.0 / py_sales - 1 AS yoy, instock,
       ltm_sales / stores                                                    AS sales_per_store,
       (ltm_sales / stores) / (SUM(ltm_sales) OVER () * 1.0 / SUM(stores) OVER ()) AS index_vs_chain
FROM r ORDER BY index_vs_chain DESC;

-- CMPE341 report queries (Chapter 5). Run against rentacar_db, e.g.:
--   docker compose exec db psql -U postgres -d rentacar_db -f /queries/queries.sql
-- The admin can also see the results at GET /api/reports/<name>.

-- QUERY 1 (JOIN): every rental with its customer and car.
SELECT r.id           AS rental_id,
       c.name         AS customer,
       ca.brand || ' ' || ca.model AS car,
       r.start_date,
       r.end_date,
       r.total_price,
       r.status
FROM rentals   AS r
JOIN customers AS c  ON c.id  = r.customer_id
JOIN cars      AS ca ON ca.id = r.car_id
ORDER BY r.start_date;

-- QUERY 2 (GROUP BY + ORDER BY): paid revenue per month.
SELECT to_char(payment_date, 'YYYY-MM') AS month,
       COUNT(*)                         AS payment_count,
       SUM(amount)                      AS revenue
FROM payments
WHERE payment_status = 'Paid'
GROUP BY to_char(payment_date, 'YYYY-MM')
ORDER BY month;

-- QUERY 3 (SUBQUERY): cars whose daily price is above the fleet average.
SELECT id, brand, model, price_per_day
FROM cars
WHERE price_per_day > (SELECT AVG(price_per_day) FROM cars)
ORDER BY price_per_day DESC;

-- EXTRA (subquery + aggregate): rentals that still have an unpaid balance.
SELECT r.id AS rental_id,
       c.name AS customer,
       r.total_price,
       r.total_price - COALESCE((SELECT SUM(p.amount)
                                 FROM payments p
                                 WHERE p.rental_id = r.id
                                   AND p.payment_status = 'Paid'), 0) AS remaining
FROM rentals r
JOIN customers c ON c.id = r.customer_id
WHERE r.status <> 'Cancelled'
  AND r.total_price > COALESCE((SELECT SUM(p.amount)
                                FROM payments p
                                WHERE p.rental_id = r.id
                                  AND p.payment_status = 'Paid'), 0)
ORDER BY remaining DESC;

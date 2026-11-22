-- CMPE341: Three meaningful SQL queries
-- Execute in pgAdmin Query Tool connected to rentacar_db.

-- QUERY 1: JOIN - rental details with customer and car information.
SELECT r.rental_id, c.full_name AS customer, ca.brand, ca.model,
       r.start_date, r.end_date
FROM rentals AS r
JOIN customers AS c ON c.customer_id = r.customer_id
JOIN cars AS ca ON ca.car_id = r.car_id
ORDER BY r.rental_id;

-- QUERY 2: GROUP BY + ORDER BY - payments summarized by method.
SELECT payment_method, COUNT(*) AS payment_count,
       SUM(amount) AS total_amount
FROM payments
GROUP BY payment_method
ORDER BY total_amount DESC;

-- QUERY 3: SUBQUERY - cars with a price higher than average.
SELECT car_id, brand, model, price_per_day
FROM cars
WHERE price_per_day > (SELECT AVG(price_per_day) FROM cars)
ORDER BY price_per_day DESC;

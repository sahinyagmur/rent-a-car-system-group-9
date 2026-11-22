-- RENT A CAR MANAGEMENT SYSTEM
-- SAMPLE DATA
-- Run only on a new, empty database after schema.sql.
-- Do not run on the existing rentacar_db database.

-- 1. ROLES
INSERT INTO roles (role_name) VALUES
('Admin'),
('Manager'),
('Employee');

-- 2. CARS
INSERT INTO cars
(brand, model, license_plate, year, price_per_day, status)
VALUES
('BMW', '320i', '06 DEMO 101', 2023, 5000, 'Available'),
('Mercedes-Benz', 'C200', '06 DEMO 102', 2024, 6500, 'Available'),
('Toyota', 'Corolla', '06 DEMO 103', 2022, 2500, 'Maintenance');

-- 3. CUSTOMERS
INSERT INTO customers (full_name, email, phone) VALUES
('Demo Customer One', 'demo1@example.com', '05000000001'),
('Demo Customer Two', 'demo2@example.com', '05000000002'),
('Demo Customer Three', 'demo3@example.com', '05000000003');

-- 4. RENTALS
INSERT INTO rentals
(customer_id, car_id, start_date, end_date)
VALUES
(
    (SELECT customer_id FROM customers
     WHERE email = 'demo1@example.com'),
    (SELECT car_id FROM cars
     WHERE license_plate = '06 DEMO 101'),
    '2026-12-01', '2026-12-03'
),
(
    (SELECT customer_id FROM customers
     WHERE email = 'demo2@example.com'),
    (SELECT car_id FROM cars
     WHERE license_plate = '06 DEMO 102'),
    '2026-12-05', '2026-12-06'
),
(
    (SELECT customer_id FROM customers
     WHERE email = 'demo3@example.com'),
    (SELECT car_id FROM cars
     WHERE license_plate = '06 DEMO 101'),
    '2026-12-10', '2026-12-12'
);

-- 5. PAYMENTS
-- Match each payment to the correct rental.

INSERT INTO payments
(rental_id, amount, payment_method, payment_status)
VALUES
(
    (SELECT r.rental_id
     FROM rentals r
     JOIN customers c ON r.customer_id = c.customer_id
     WHERE c.email = 'demo1@example.com'
       AND r.start_date = '2026-12-01'),
    15000, 'Card', 'Paid'
),
(
    (SELECT r.rental_id
     FROM rentals r
     JOIN customers c ON r.customer_id = c.customer_id
     WHERE c.email = 'demo2@example.com'
       AND r.start_date = '2026-12-05'),
    13000, 'Cash', 'Pending'
),
(
    (SELECT r.rental_id
     FROM rentals r
     JOIN customers c ON r.customer_id = c.customer_id
     WHERE c.email = 'demo3@example.com'
       AND r.start_date = '2026-12-10'),
    10000, 'Card', 'Paid'
);

-- 6. USERS
-- Password hashes must be generated with Werkzeug scrypt.
-- Insert demo users separately using the Python setup script.
-- Do not store plaintext passwords in this SQL file.

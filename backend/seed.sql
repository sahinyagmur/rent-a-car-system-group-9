-- SAMPLE DATA. Run on a new database right after schema.sql.
-- docker compose runs this file automatically on the first start.
--
-- Test accounts (passwords hashed with werkzeug scrypt):
--   admin / Admin123!      -> role admin
--   demo1 / Customer123!   -> role customer
--   demo2 / Customer123!   -> role customer

-- 1. ROLES
INSERT INTO roles (role_name) VALUES ('admin'), ('customer'), ('employee');

-- 2. USERS
INSERT INTO users (username, password_hash, role_id) VALUES
('admin', 'scrypt:32768:8:1$oDT1tSikJkEZkHPh$1a6dcef0eca14ef0e93992611ade4258c19d3c1975d91c825edc1127bb1ceb3d0a411fbf2fdb3a03343440d7820d57a8fb37b4781ac336f5bf38f0b8e3a73923',
    (SELECT id FROM roles WHERE role_name = 'admin')),
('demo1', 'scrypt:32768:8:1$6jA1zyOL25jqa82U$37843ee0ea1d3489d30fc9d5e756ddb6af781b4330365c852a8ce406818e32e1b83a46e2bece45e97bb8b90affab433244e071a96445cf3651a4ea27bbea926f',
    (SELECT id FROM roles WHERE role_name = 'customer')),
('demo2', 'scrypt:32768:8:1$6jA1zyOL25jqa82U$37843ee0ea1d3489d30fc9d5e756ddb6af781b4330365c852a8ce406818e32e1b83a46e2bece45e97bb8b90affab433244e071a96445cf3651a4ea27bbea926f',
    (SELECT id FROM roles WHERE role_name = 'customer'));

-- 3. CARS
INSERT INTO cars (brand, model, license_plate, year, price_per_day, status) VALUES
('BMW',           '320i',    '06 DEMO 101', 2023, 5000, 'Available'),
('Mercedes-Benz', 'C200',    '06 DEMO 102', 2024, 6500, 'Available'),
('Toyota',        'Corolla', '06 DEMO 103', 2022, 2500, 'Maintenance'),
('Renault',       'Clio',    '06 DEMO 104', 2023, 1800, 'Available'),
('Fiat',          'Egea',    '06 DEMO 105', 2024, 1900, 'Available'),
('Volkswagen',    'Passat',  '06 DEMO 106', 2023, 4200, 'Available'),
('Hyundai',       'i20',     '06 DEMO 107', 2022, 1700, 'Available'),
('Audi',          'A4',      '06 DEMO 108', 2024, 5800, 'Available'),
('Peugeot',       '3008',    '06 DEMO 109', 2023, 3900, 'Rented');

-- 4. CUSTOMERS (the third one is a walk-in customer without a login account)
INSERT INTO customers (user_id, name, email, phone, driver_license_no) VALUES
((SELECT id FROM users WHERE username = 'demo1'), 'Demo Customer One',   'demo1@example.com', '05000000001', 'DL-100001'),
((SELECT id FROM users WHERE username = 'demo2'), 'Demo Customer Two',   'demo2@example.com', '05000000002', 'DL-100002'),
(NULL,                                            'Demo Customer Three', 'demo3@example.com', '05000000003', 'DL-100003');

-- 5. RENTALS  (total_price = inclusive day count x price_per_day at booking time)
INSERT INTO rentals (customer_id, car_id, start_date, end_date, total_price, status) VALUES
((SELECT id FROM customers WHERE email = 'demo3@example.com'), (SELECT id FROM cars WHERE license_plate = '06 DEMO 103'), '2026-10-05', '2026-10-08', 10000, 'Completed'),
((SELECT id FROM customers WHERE email = 'demo1@example.com'), (SELECT id FROM cars WHERE license_plate = '06 DEMO 105'), '2026-11-10', '2026-11-12',  5700, 'Completed'),
((SELECT id FROM customers WHERE email = 'demo2@example.com'), (SELECT id FROM cars WHERE license_plate = '06 DEMO 109'), '2026-11-24', '2026-11-28', 19500, 'Active'),
((SELECT id FROM customers WHERE email = 'demo1@example.com'), (SELECT id FROM cars WHERE license_plate = '06 DEMO 101'), '2026-12-01', '2026-12-03', 15000, 'Pending'),
((SELECT id FROM customers WHERE email = 'demo2@example.com'), (SELECT id FROM cars WHERE license_plate = '06 DEMO 102'), '2026-12-05', '2026-12-06', 13000, 'Pending'),
((SELECT id FROM customers WHERE email = 'demo3@example.com'), (SELECT id FROM cars WHERE license_plate = '06 DEMO 106'), '2026-11-15', '2026-11-16',  8400, 'Cancelled');

-- 6. PAYMENTS (different months, for the monthly revenue report)
INSERT INTO payments (rental_id, payment_date, amount, payment_method, payment_status) VALUES
((SELECT r.id FROM rentals r JOIN cars c ON c.id = r.car_id WHERE c.license_plate = '06 DEMO 103' AND r.start_date = '2026-10-05'), '2026-10-08', 10000, 'Cash', 'Paid'),
((SELECT r.id FROM rentals r JOIN cars c ON c.id = r.car_id WHERE c.license_plate = '06 DEMO 105' AND r.start_date = '2026-11-10'), '2026-11-12',  5700, 'Card', 'Paid'),
((SELECT r.id FROM rentals r JOIN cars c ON c.id = r.car_id WHERE c.license_plate = '06 DEMO 109' AND r.start_date = '2026-11-24'), '2026-11-24', 10000, 'Card', 'Paid'),
((SELECT r.id FROM rentals r JOIN cars c ON c.id = r.car_id WHERE c.license_plate = '06 DEMO 101' AND r.start_date = '2026-12-01'), '2026-11-25',  5000, 'Card', 'Pending');

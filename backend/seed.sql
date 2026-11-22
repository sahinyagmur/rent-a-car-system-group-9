-- SAMPLE DATA: Use on a new/empty database after schema.sql.
INSERT INTO cars (brand,model,license_plate,year,price_per_day,status) VALUES
('BMW','320i','06 DEMO 101',2023,5000,'Available'),
('Mercedes-Benz','C200','06 DEMO 102',2024,6500,'Available'),
('Toyota','Corolla','06 DEMO 103',2022,2500,'Maintenance');
INSERT INTO customers (name,email,phone) VALUES
('Demo Customer One','demo1@example.com','05000000001'),
('Demo Customer Two','demo2@example.com','05000000002'),
('Demo Customer Three','demo3@example.com','05000000003');
INSERT INTO rentals (customer_id,car_id,start_date,end_date) VALUES
((SELECT id FROM customers WHERE email='demo1@example.com'),(SELECT id FROM cars WHERE license_plate='06 DEMO 101'),'2026-12-01','2026-12-03'),
((SELECT id FROM customers WHERE email='demo2@example.com'),(SELECT id FROM cars WHERE license_plate='06 DEMO 102'),'2026-12-05','2026-12-06'),
((SELECT id FROM customers WHERE email='demo3@example.com'),(SELECT id FROM cars WHERE license_plate='06 DEMO 101'),'2026-12-10','2026-12-12');
INSERT INTO payments (rental_id,amount,payment_method,payment_status) VALUES
((SELECT id FROM rentals ORDER BY id DESC LIMIT 1),15000,'Card','Paid'),
((SELECT id FROM rentals ORDER BY id DESC LIMIT 1 OFFSET 1),13000,'Cash','Pending'),
((SELECT id FROM rentals ORDER BY id DESC LIMIT 1 OFFSET 2),10000,'Card','Paid');

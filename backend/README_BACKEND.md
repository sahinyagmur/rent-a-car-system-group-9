# Rent a Car — Backend integration (22 Nov 2026)

## Contents
- `app.py`: Flask API for Cars, Customers, Rentals, Payments.
- `schema.sql`: initial schema for a NEW empty database.
- `migrate_existing.sql`: migration from the previously shared `cars(..., available)` database; **backup first**.
- `seed.sql`: 3 demo rows per table for a NEW empty database only.
- `.env.example`: copy to `.env` in the `backend/` directory and set your local PostgreSQL password. **Never commit `.env`.**

## Start
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# edit .env to set DB_PASSWORD
python app.py
```
For an existing DB, first back it up and execute `migrate_existing.sql` using DBeaver/psql, **not** `schema.sql` or `seed.sql`. For a new DB run `schema.sql` then `seed.sql`. If Person 2 has already created tables, reconcile schema before running either SQL script.

## Endpoint contract
All four resources: `cars`, `customers`, `rentals`, `payments`.

| HTTP method | URL | Response |
|---|---|---|
| GET | `/api/<resource>` | `{ "status":"success", "<resource>":[...] }` |
| GET | `/api/<resource>/<id>` | `{ "status":"success", "car/customer/rental/payment": {...} }` |
| POST | `/api/<resource>` | `{ "status":"success", "record": {...} }` (201) |
| PUT/PATCH | `/api/<resource>/<id>` | `{ "status":"success", "record": {...} }` |
| DELETE | `/api/<resource>/<id>` | `{ "status":"success", "deleted_id": 1 }` |

PUT is implemented as **partial update**, same as PATCH. `id` is database-generated and is not accepted in POST/PUT payloads.

### Request JSON examples
**POST /api/cars**
```json
{"brand":"BMW","model":"320i","license_plate":"06 ABC 123","year":2023,"price_per_day":5000,"status":"Available"}
```
Allowed car statuses: `Available`, `Rented`, `Maintenance`. If omitted in POST, status defaults to `Available`.

**POST /api/customers**
```json
{"name":"Ada Example","email":"ada@example.com","phone":"05000000000"}
```

**POST /api/rentals**
```json
{"customer_id":1,"car_id":1,"start_date":"2026-12-01","end_date":"2026-12-03"}
```
Dates are inclusive. Existing customer and car are required; Maintenance cars and overlapping rental date ranges are rejected. `Rented` status is informational and does not by itself prevent a booking on nonoverlapping dates. The car status is **not automatically changed** when a rental is created/deleted; this must be agreed with Person 2.

**POST /api/payments**
```json
{"rental_id":1,"amount":15000,"payment_method":"Card","payment_status":"Paid"}
```
Allowed methods: `Cash`, `Card`; payment statuses: `Paid`, `Pending`. A rental must exist before creating its payment.

### Frontend mapping
- Cars JS `licensePlate` -> API `license_plate`; `pricePerDay` -> `price_per_day`.
- Customers JS `name` -> API `name` (form ID `fullName` stays unchanged).
- Rentals JS `customerId` -> `customer_id`; `carId` -> `car_id`; `startDate` -> `start_date`; `endDate` -> `end_date`.
- Payments JS `rentalId` -> `rental_id`; `method` -> `payment_method`; `status` -> `payment_status`.
- GET response is an object containing an array (`response.cars`, etc.), **not a bare array**.
- Frontend HTML in the shared repository is still demo-only and must be updated to use `fetch` to these URLs. Serve pages from the same Flask origin or configure CORS appropriately; opening HTML via `file://` can cause origin/CORS issues.

### Important limits
- This is a **four-entity provisional schema**. The professor requires 5–10 entities: reconcile with Person 2's ER/EER before final submission.
- `migrate_existing.sql` keeps legacy `available` for compatibility and sets its default to TRUE. Legacy `available` and new `status` can diverge; use `status` as the API source of truth until the final ER/EER migration removes the old column.
- The SQL migration assumes the old cars table exactly matches the shared `app.py`. It does not migrate an unrelated Person 2 schema.
- No login/authentication is implemented; index.html remains demo.
- Do not deploy this development API publicly without authentication, rate limits, CORS/origin controls, and production configuration.
- Syntax was checked, but a live PostgreSQL integration test has **not** been run here.

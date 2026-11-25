# Backend (Flask + PostgreSQL)

`app.py` serves the JSON API under `/api` and the frontend files from the repository root, from one origin.

## Run

With Docker (recommended), from the repository root:

```
docker compose up --build        # http://localhost:5000
```

Without Docker (needs a local PostgreSQL with `schema.sql` + `seed.sql` loaded):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env           # set DB_PASSWORD and SECRET_KEY
python app.py                    # http://127.0.0.1:5000
```

## Files

| File | Purpose |
|---|---|
| `app.py` | API, authentication, business rules, static file serving |
| `schema.sql` | Tables and constraints (new empty database only) |
| `seed.sql` | Sample data and test accounts |
| `queries.sql` | Report queries for Chapter 5 |
| `Dockerfile` | Web image (gunicorn) |
| `FRONTEND_INTEGRATION.md` | The contract between frontend and backend (detailed spec) |

## Authentication

Session cookie (signed with `SECRET_KEY`, HttpOnly, SameSite=Lax). Passwords: werkzeug scrypt hashes.

| Endpoint | Body | Result |
|---|---|---|
| `POST /api/auth/login` | `username`, `password` | `user` + session |
| `POST /api/auth/register` | `name`, `email`, `phone`, `driver_license_no`, `username`, `password` | creates user (role customer) + customer in one transaction |
| `POST /api/auth/logout` | – | clears session |
| `GET /api/auth/me` | – | current `user` or 401 |

`user` = `{id, username, role, customer_id, name}`; role is `admin` or `customer`.

## Resources

Responses: list `{"status":"success","cars":[...]}`, one `{"status":"success","car":{...}}`, create/update `{"status":"success","record":{...}}`, delete `{"status":"success","deleted_id":1}`, error `{"status":"error","error":"Message."}`. Updates use `PATCH` (partial; `PUT` behaves the same).

| Resource | Guest | Customer | Admin |
|---|---|---|---|
| `cars` | read | read | full CRUD |
| `customers` | – | read/update own (name, email, phone) | full CRUD |
| `rentals` | – | read own, create for self, cancel own Pending | full CRUD |
| `payments` | – | read own | full CRUD |

Extra endpoints:

- `GET /api/cars/available?start=YYYY-MM-DD&end=YYYY-MM-DD` — cars free for the dates (not in Maintenance, no overlapping Pending/Active rental)
- `GET /api/cars/<id>/booked` — date ranges of Pending/Active rentals (dates only)
- `GET /api/reports/rental-details | monthly-revenue | above-average-cars` — report queries (admin)
- `GET /api/health` — API + database check

## Business rules

- `total_price` = inclusive days × `price_per_day`, calculated by the server (customers can't send it; admins may override). Recalculated when dates or car change.
- Pending/Active rentals of the same car can't overlap; Maintenance cars can't be booked. The car row is locked during the check so two bookings can't race.
- Rental status flow: `Pending → Active | Cancelled`, `Active → Completed`.
- A payment can't make the paid total exceed the rental's `total_price`. Rentals include `paid_amount` and `remaining`.
- Deleting a car/customer/rental that is still referenced returns 409 (foreign keys are `ON DELETE RESTRICT`).
- `users` and `roles` are not exposed through the API; password hashes are never returned.

## Configuration (environment variables)

`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`, `SESSION_COOKIE_SECURE` (true behind HTTPS). Docker Compose reads them from `.env` in the repository root.

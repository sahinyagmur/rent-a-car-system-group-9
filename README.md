# rent-a-car-system-group-9

CMPE341 Database Design & Management — Rent a Car system, Group 9.

A car rental website: customers browse cars, check availability for their dates, book and track their rentals; the admin manages cars, customers, rentals and payments. PostgreSQL database, Flask backend, plain HTML/CSS/JS frontend.

**Live site: https://rentcar9.site** (the server's IP address http://13.50.166.44 redirects to the domain)

## Run it (one command)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```
docker compose up --build
```

Open **http://localhost:5000**.

The first start creates the database tables (`backend/schema.sql`) and loads sample data (`backend/seed.sql`). To start again from a clean database: `docker compose down -v`, then `docker compose up --build`.

## Test accounts

The same accounts work on the live site and on a local `docker compose up`.

| Role | Username | Password | Can do |
|---|---|---|---|
| Admin | `admin` | `Admin123!` | Admin panel at `/admin`: insert, update, delete cars, customers, rentals, payments; dashboard and reports |
| Customer | `demo1` | `Customer123!` | Book cars, see and cancel own rentals, edit own profile |
| Customer | `demo2` | `Customer123!` | Same as demo1 |

New customers can also sign up at `/register`. Passwords are stored as scrypt hashes (werkzeug).

The `roles` table has three rows: `admin`, `customer` and `employee`. The `employee` role is reserved for future use (counter staff accounts); no user has it yet and it has no permissions in the app.

## Pages

| URL | Page |
|---|---|
| `/` | Home with date search |
| `/cars` | Car catalog with availability for chosen dates |
| `/car-detail.html?id=1` | Car details and price calculation |
| `/login`, `/register` | Authentication |
| `/booking.html` | Booking confirmation (customer) |
| `/my-rentals` | Own rentals, paid and remaining amounts (customer) |
| `/profile` | Own profile (customer) |
| `/admin` | Admin dashboard, cars, customers, rentals, payments |

## Database

Six tables: `roles`, `users`, `cars`, `customers`, `rentals`, `payments` — see `backend/schema.sql`.

Report queries (JOIN, GROUP BY + ORDER BY, subquery) are in `backend/queries.sql`. Run them against the running database:

```
docker compose exec db psql -U postgres -d rentacar_db -f /queries/queries.sql
```

## Configuration

Copy `.env.example` to `.env` and change the values (database password, `SECRET_KEY`, port). Without `.env`, development defaults are used — **always set real values on the server**. `.env` is git-ignored.

## Deployment (Linux server)

On a fresh Ubuntu 22.04/24.04 VM with ports 22 (SSH) and 80 (HTTP) open:

```
git clone https://github.com/sahinyagmur/rent-a-car-system-group-9.git
cd rent-a-car-system-group-9
sudo bash deploy/setup-server.sh
```

The script installs Docker, creates `.env` with a random database password and `SECRET_KEY`, and starts the app on port 80. Open `http://<server public IP>/`. To update after new commits, run `sudo bash deploy/setup-server.sh` again (it keeps `.env` and the database).

HTTPS with a domain (ports 80 and 443 open, the domain's A record pointing to the server): `sudo bash deploy/setup-server.sh --domain yourdomain.com`.

Our live server: AWS EC2 t3.micro (Ubuntu, region eu-north-1), Elastic IP `13.50.166.44`, domain **https://rentcar9.site**. Step-by-step guide: `deploy/DEPLOY.md`.

## Frontend preview without Docker

```
node tools/dev-server.js
```

Open http://localhost:5500. On this port the site runs in demo mode: data is kept in your browser, no database needed. On any other origin (Flask/Docker) it uses the real API.

## Project structure

```
index.html, cars.html, ...   customer-facing pages
admin/                       admin panel pages
css/style.css                shared design system
js/api.js                    the only file that calls the API (mock or live)
js/app.js                    session, header/footer, UI helpers
js/admin.js                  shared admin list/form code
backend/app.py               Flask API + serves the frontend
backend/schema.sql, seed.sql database tables and sample data
backend/queries.sql          report queries
backend/Dockerfile           web image
docker-compose.yml           database + web app
```

API reference: `backend/README_BACKEND.md`.

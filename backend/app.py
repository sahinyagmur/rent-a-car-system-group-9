"""Rent a Car — Flask API + static frontend (CMPE341 Group 9).

One process serves:
  * the JSON API under /api (contract: backend/FRONTEND_INTEGRATION.md)
  * the HTML/CSS/JS frontend from the repository root

Configuration comes from environment variables (see .env.example).
"""
import os
import re
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import wraps

import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, request, send_from_directory, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import safe_join


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(REPO_ROOT, ".env"))

app = Flask(__name__, static_folder=None)

secret = os.getenv("SECRET_KEY")
if not secret:
    secret = os.urandom(32).hex()
    print("WARNING: SECRET_KEY is not set; sessions will reset on every restart.")

app.config.update(
    SECRET_KEY=secret,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    MAX_CONTENT_LENGTH=64 * 1024,
)
app.json.sort_keys = False

ACTIVE_STATUSES = ("Pending", "Active")          # rentals that block a car
STATUS_FLOW = {                                   # allowed rental status changes
    "Pending": {"Active", "Cancelled"},
    "Active": {"Completed"},
    "Completed": set(),
    "Cancelled": set(),
}


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


# ============================================================
# 2. DATABASE
# ============================================================

def connect():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "rentacar_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=RealDictCursor,
    )


@contextmanager
def transaction():
    """Yield a cursor; commit on success, roll back on any exception."""
    conn = connect()
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()


def to_json(row):
    if row is None:
        return None
    out = {}
    for key, value in dict(row).items():
        if key == "password_hash":
            continue
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, date):
            value = value.isoformat()
        out[key] = value
    return out


def ok(status=200, **payload):
    return jsonify(status="success", **payload), status


# ============================================================
# 3. ERROR HANDLING
# ============================================================

UNIQUE_MESSAGES = {
    "cars_license_plate_key": "License plate already exists.",
    "customers_email_key": "E-mail already registered.",
    "customers_driver_license_no_key": "Driver license number already registered.",
    "customers_user_id_key": "This user account is already linked to a customer.",
    "users_username_key": "Username is taken.",
}

DELETE_MESSAGES = {
    "cars": "Car has rentals and cannot be deleted.",
    "customers": "Customer has rentals and cannot be deleted.",
    "rentals": "Rental has payments and cannot be deleted.",
}


@app.errorhandler(ApiError)
def handle_api_error(exc):
    return jsonify(status="error", error=exc.message), exc.status


@app.errorhandler(psycopg2.Error)
def handle_db_error(exc):
    if isinstance(exc, errors.UniqueViolation):
        name = getattr(exc.diag, "constraint_name", "")
        return jsonify(status="error", error=UNIQUE_MESSAGES.get(name, "This value already exists.")), 409
    if isinstance(exc, errors.ForeignKeyViolation):
        if request.method == "DELETE":
            resource = request.path.split("/")[2] if request.path.count("/") >= 2 else ""
            msg = DELETE_MESSAGES.get(resource, "Record is in use and cannot be deleted.")
        else:
            msg = "Referenced record does not exist."
        return jsonify(status="error", error=msg), 409
    if isinstance(exc, (errors.CheckViolation, errors.NotNullViolation)):
        return jsonify(status="error", error="Invalid data for this record."), 400
    if isinstance(exc, psycopg2.OperationalError):
        app.logger.exception("Database unavailable")
        return jsonify(status="error", error="Database is not reachable."), 503
    app.logger.exception("Database error")
    return jsonify(status="error", error="Database error."), 500


@app.errorhandler(HTTPException)
def handle_http_error(exc):
    if request.path.startswith("/api/") or request.path == "/api":
        messages = {404: "Not found.", 405: "Method not allowed.", 413: "Request is too large."}
        return jsonify(status="error", error=messages.get(exc.code, exc.description)), exc.code
    if exc.code == 404:
        return not_found_page()
    return exc


# ============================================================
# 4. INPUT VALIDATION
# ============================================================

EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
PHONE_RE = re.compile(r"[0-9 +()\-]{10,30}")
USERNAME_RE = re.compile(r"[A-Za-z0-9_.]{3,50}")


def v_text(max_len, transform=None):
    def check(name, value):
        if not isinstance(value, str) or not value.strip():
            raise ApiError(f"{name} is required.")
        value = value.strip()
        if len(value) > max_len:
            raise ApiError(f"{name} must be at most {max_len} characters.")
        return transform(value) if transform else value
    return check


def v_email(name, value):
    value = v_text(255, str.lower)(name, value)
    if not EMAIL_RE.fullmatch(value):
        raise ApiError("Enter a valid e-mail address.")
    return value


def v_phone(name, value):
    value = v_text(30)(name, value)
    if not PHONE_RE.fullmatch(value):
        raise ApiError("Enter a valid phone number.")
    return value


def v_int(low=1, high=None):
    def check(name, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ApiError(f"{name} must be a whole number.")
        if value < low or (high is not None and value > high):
            raise ApiError(f"{name} is out of range.")
        return value
    return check


def v_money(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ApiError(f"{name} must be a number.")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ApiError(f"{name} must be a number.")
    if not number.is_finite() or number < 0 or number > Decimal("9999999999.99") \
            or number.as_tuple().exponent < -2:
        raise ApiError(f"{name} must be a positive amount with at most 2 decimals.")
    return number


def v_date(name, value):
    try:
        if not isinstance(value, str):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        raise ApiError(f"{name} must be a date (YYYY-MM-DD).")


def v_choice(*options):
    def check(name, value):
        if value not in options:
            raise ApiError(f"{name} must be one of: {', '.join(options)}.")
        return value
    return check


FIELDS = {
    "cars": {
        "brand": v_text(100), "model": v_text(100),
        "license_plate": v_text(30, str.upper),
        "year": v_int(1886, 2100), "price_per_day": v_money,
        "status": v_choice("Available", "Rented", "Maintenance"),
    },
    "customers": {
        "name": v_text(150), "email": v_email, "phone": v_phone,
        "driver_license_no": v_text(30, str.upper),
    },
    "rentals": {
        "customer_id": v_int(), "car_id": v_int(),
        "start_date": v_date, "end_date": v_date,
        "total_price": v_money,
        "status": v_choice("Pending", "Active", "Completed", "Cancelled"),
    },
    "payments": {
        "rental_id": v_int(), "payment_date": v_date, "amount": v_money,
        "payment_method": v_choice("Cash", "Card"),
        "payment_status": v_choice("Paid", "Pending"),
    },
}

REQUIRED = {
    "cars": ("brand", "model", "license_plate", "year", "price_per_day"),
    "customers": ("name", "email", "phone", "driver_license_no"),
    "rentals": ("customer_id", "car_id", "start_date", "end_date"),
    "payments": ("rental_id", "amount", "payment_method", "payment_status"),
}

SINGULAR = {"cars": "car", "customers": "customer", "rentals": "rental", "payments": "payment"}


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Send a JSON object.")
    return data


def clean(resource, data, partial=False, allowed=None, required=None):
    """Validate a JSON body against FIELDS[resource]; return {column: value}."""
    allowed = set(allowed or FIELDS[resource])
    unknown = set(data) - allowed - {"id"}
    if unknown:
        raise ApiError("Unknown or read-only fields: " + ", ".join(sorted(unknown)))
    if not partial:
        missing = [f for f in (required or REQUIRED[resource]) if data.get(f) in (None, "")]
        if missing:
            raise ApiError("Missing fields: " + ", ".join(missing))
    out = {}
    for key, value in data.items():
        if key == "id" or (value is None and key not in REQUIRED[resource]):
            continue
        out[key] = FIELDS[resource][key](key.replace("_", " ").capitalize(), value)
    if partial and not out:
        raise ApiError("Nothing to update.")
    return out


# ============================================================
# 5. AUTHENTICATION
# ============================================================

USER_SQL = """
    SELECT u.id, u.username, u.password_hash, r.role_name AS role,
           c.id AS customer_id, COALESCE(c.name, u.username) AS name
    FROM users u
    JOIN roles r ON r.id = u.role_id
    LEFT JOIN customers c ON c.user_id = u.id
"""

# Compared against when the username doesn't exist, so both cases take equal time
DUMMY_HASH = generate_password_hash("not-a-real-password", method="scrypt")


def public_user(row):
    return {k: row[k] for k in ("id", "username", "role", "customer_id", "name")}


def current_user():
    if "user" not in g:
        g.user = None
        uid = session.get("user_id")
        if uid:
            with transaction() as cur:
                cur.execute(USER_SQL + " WHERE u.id = %s", (uid,))
                row = cur.fetchone()
            g.user = public_user(row) if row else None
            if not row:
                session.clear()
    return g.user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            raise ApiError("Please log in.", 401)
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            raise ApiError("Please log in.", 401)
        if user["role"] != "admin":
            raise ApiError("Not allowed.", 403)
        return view(*args, **kwargs)
    return wrapper


def is_admin():
    user = current_user()
    return bool(user) and user["role"] == "admin"


def own_customer_id():
    """customer_id of the logged-in customer (raises if the account has none)."""
    user = current_user()
    if not user or user["customer_id"] is None:
        raise ApiError("This account has no customer profile.", 403)
    return user["customer_id"]


@app.post("/api/auth/login")
def auth_login():
    data = body()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    with transaction() as cur:
        cur.execute(USER_SQL + " WHERE u.username = %s", (username,))
        row = cur.fetchone()
    valid = check_password_hash(row["password_hash"] if row else DUMMY_HASH, password)
    if not row or not valid:
        raise ApiError("Wrong username or password.", 401)
    session.clear()
    session["user_id"] = row["id"]
    return ok(user=public_user(row))


@app.post("/api/auth/register")
def auth_register():
    data = body()
    username = str(data.get("username", "")).strip()
    password = data.get("password")
    if not USERNAME_RE.fullmatch(username):
        raise ApiError("Username: 3–50 letters, digits, dot or underscore.")
    if not isinstance(password, str) or len(password) < 8:
        raise ApiError("Password must be at least 8 characters.")
    customer = clean("customers", {k: data.get(k) for k in REQUIRED["customers"]})

    with transaction() as cur:
        cur.execute(
            """INSERT INTO users (username, password_hash, role_id)
               VALUES (%s, %s, (SELECT id FROM roles WHERE role_name = 'customer'))
               RETURNING id""",
            (username, generate_password_hash(password, method="scrypt")),
        )
        user_id = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO customers (user_id, name, email, phone, driver_license_no)
               VALUES (%s, %s, %s, %s, %s)""",
            (user_id, customer["name"], customer["email"], customer["phone"], customer["driver_license_no"]),
        )
        cur.execute(USER_SQL + " WHERE u.id = %s", (user_id,))
        row = cur.fetchone()
    session.clear()
    session["user_id"] = user_id
    return ok(201, user=public_user(row))


@app.post("/api/auth/logout")
def auth_logout():
    session.clear()
    return ok()


@app.get("/api/auth/me")
@login_required
def auth_me():
    return ok(user=current_user())


@app.get("/api/health")
def health():
    with transaction() as cur:
        cur.execute("SELECT 1")
    return ok(message="API and database are running")


# ============================================================
# 6. CARS
# ============================================================

def get_or_404(cur, table, record_id, lock=False):
    cur.execute(f"SELECT * FROM {table} WHERE id = %s" + (" FOR UPDATE" if lock else ""), (record_id,))
    row = cur.fetchone()
    if not row:
        raise ApiError(f"{SINGULAR[table].capitalize()} not found.", 404)
    return row


@app.get("/api/cars")
def cars_list():
    with transaction() as cur:
        cur.execute("SELECT * FROM cars ORDER BY id")
        return ok(cars=[to_json(r) for r in cur.fetchall()])


@app.get("/api/cars/available")
def cars_available():
    start = v_date("Start date", request.args.get("start"))
    end = v_date("End date", request.args.get("end"))
    if end < start:
        raise ApiError("End date must be on or after start date.")
    with transaction() as cur:
        cur.execute(
            """SELECT * FROM cars c
               WHERE c.status <> 'Maintenance'
                 AND NOT EXISTS (
                     SELECT 1 FROM rentals r
                     WHERE r.car_id = c.id AND r.status IN %s
                       AND r.start_date <= %s AND %s <= r.end_date)
               ORDER BY c.id""",
            (ACTIVE_STATUSES, end, start),
        )
        return ok(cars=[to_json(r) for r in cur.fetchall()])


@app.get("/api/cars/<int:car_id>/booked")
def car_booked(car_id):
    with transaction() as cur:
        get_or_404(cur, "cars", car_id)
        cur.execute(
            """SELECT start_date, end_date FROM rentals
               WHERE car_id = %s AND status IN %s ORDER BY start_date""",
            (car_id, ACTIVE_STATUSES),
        )
        return ok(ranges=[to_json(r) for r in cur.fetchall()])


@app.get("/api/cars/<int:car_id>")
def car_get(car_id):
    with transaction() as cur:
        return ok(car=to_json(get_or_404(cur, "cars", car_id)))


# ============================================================
# 7. GENERIC INSERT / UPDATE / DELETE HELPERS
# ============================================================

def insert(cur, table, values):
    cols = list(values)
    cur.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING *",
        [values[c] for c in cols],
    )
    return cur.fetchone()


def update(cur, table, record_id, values):
    cols = list(values)
    cur.execute(
        f"UPDATE {table} SET {', '.join(c + ' = %s' for c in cols)} WHERE id = %s RETURNING *",
        [values[c] for c in cols] + [record_id],
    )
    return cur.fetchone()


def delete(cur, table, record_id):
    cur.execute(f"DELETE FROM {table} WHERE id = %s RETURNING id", (record_id,))
    if not cur.fetchone():
        raise ApiError(f"{SINGULAR[table].capitalize()} not found.", 404)


@app.post("/api/cars")
@admin_required
def car_create():
    values = clean("cars", body())
    with transaction() as cur:
        return ok(201, record=to_json(insert(cur, "cars", values)))


@app.patch("/api/cars/<int:car_id>")
@app.put("/api/cars/<int:car_id>")
@admin_required
def car_update(car_id):
    values = clean("cars", body(), partial=True)
    with transaction() as cur:
        get_or_404(cur, "cars", car_id)
        return ok(record=to_json(update(cur, "cars", car_id, values)))


@app.delete("/api/cars/<int:car_id>")
@admin_required
def car_delete(car_id):
    with transaction() as cur:
        delete(cur, "cars", car_id)
    return ok(deleted_id=car_id)


# ============================================================
# 8. CUSTOMERS
# ============================================================

def check_customer_access(customer_id):
    if not is_admin() and own_customer_id() != customer_id:
        raise ApiError("Customer not found.", 404)   # don't reveal other customers


@app.get("/api/customers")
@login_required
def customers_list():
    with transaction() as cur:
        if is_admin():
            cur.execute("SELECT * FROM customers ORDER BY id")
        else:
            cur.execute("SELECT * FROM customers WHERE id = %s", (own_customer_id(),))
        return ok(customers=[to_json(r) for r in cur.fetchall()])


@app.get("/api/customers/<int:customer_id>")
@login_required
def customer_get(customer_id):
    check_customer_access(customer_id)
    with transaction() as cur:
        return ok(customer=to_json(get_or_404(cur, "customers", customer_id)))


@app.post("/api/customers")
@admin_required
def customer_create():
    values = clean("customers", body())          # walk-in customer, no login account
    with transaction() as cur:
        return ok(201, record=to_json(insert(cur, "customers", values)))


@app.patch("/api/customers/<int:customer_id>")
@app.put("/api/customers/<int:customer_id>")
@login_required
def customer_update(customer_id):
    check_customer_access(customer_id)
    allowed = None if is_admin() else ("name", "email", "phone")
    values = clean("customers", body(), partial=True, allowed=allowed)
    with transaction() as cur:
        get_or_404(cur, "customers", customer_id)
        return ok(record=to_json(update(cur, "customers", customer_id, values)))


@app.delete("/api/customers/<int:customer_id>")
@admin_required
def customer_delete(customer_id):
    # The customer and their login account are deleted together, in one transaction,
    # so no orphan account is left that can log in without a profile. A customer with
    # rentals can't be deleted (FK RESTRICT); then nothing is deleted.
    with transaction() as cur:
        customer = get_or_404(cur, "customers", customer_id, lock=True)
        delete(cur, "customers", customer_id)
        if customer["user_id"] is not None:
            cur.execute(
                """DELETE FROM users
                   WHERE id = %s
                     AND role_id = (SELECT id FROM roles WHERE role_name = 'customer')""",
                (customer["user_id"],),
            )
    return ok(deleted_id=customer_id)


# ============================================================
# 9. RENTALS
# ============================================================

RENTAL_SELECT = """
    SELECT r.*,
           COALESCE(SUM(p.amount) FILTER (WHERE p.payment_status = 'Paid'), 0) AS paid_amount,
           GREATEST(r.total_price - COALESCE(SUM(p.amount) FILTER (WHERE p.payment_status = 'Paid'), 0), 0) AS remaining
    FROM rentals r
    LEFT JOIN payments p ON p.rental_id = r.id
"""


def check_rental(cur, rental, exclude_id=None):
    """Business rules shared by create and update. Locks the car row."""
    if rental["end_date"] < rental["start_date"]:
        raise ApiError("End date must be on or after start date.")
    get_or_404(cur, "customers", rental["customer_id"])
    car = get_or_404(cur, "cars", rental["car_id"], lock=True)   # serialises bookings per car
    if rental["status"] in ACTIVE_STATUSES:
        if car["status"] == "Maintenance":
            raise ApiError("This car is under maintenance.", 409)
        cur.execute(
            """SELECT 1 FROM rentals
               WHERE car_id = %s AND status IN %s AND id <> %s
                 AND start_date <= %s AND %s <= end_date LIMIT 1""",
            (rental["car_id"], ACTIVE_STATUSES, exclude_id or 0, rental["end_date"], rental["start_date"]),
        )
        if cur.fetchone():
            raise ApiError("This car is already booked for those dates.", 409)
    return car


def price_for(car, start, end):
    return car["price_per_day"] * ((end - start).days + 1)


def rental_out(cur, rental_id):
    cur.execute(RENTAL_SELECT + " WHERE r.id = %s GROUP BY r.id", (rental_id,))
    return to_json(cur.fetchone())


@app.get("/api/rentals")
@login_required
def rentals_list():
    with transaction() as cur:
        if is_admin():
            cur.execute(RENTAL_SELECT + " GROUP BY r.id ORDER BY r.id")
        else:
            cur.execute(RENTAL_SELECT + " WHERE r.customer_id = %s GROUP BY r.id ORDER BY r.id",
                        (own_customer_id(),))
        return ok(rentals=[to_json(r) for r in cur.fetchall()])


@app.get("/api/rentals/<int:rental_id>")
@login_required
def rental_get(rental_id):
    with transaction() as cur:
        rental = get_or_404(cur, "rentals", rental_id)
        check_customer_access(rental["customer_id"])
        return ok(rental=rental_out(cur, rental_id))


@app.post("/api/rentals")
@login_required
def rental_create():
    data = body()
    if is_admin():
        values = clean("rentals", data)
        values.setdefault("status", "Pending")
    else:
        # Customers can only book for themselves; price and status are set here
        data = {k: v for k, v in data.items() if k in ("car_id", "start_date", "end_date")}
        values = clean("rentals", data, required=("car_id", "start_date", "end_date"))
        values.update(customer_id=own_customer_id(), status="Pending")
        values.pop("total_price", None)
        if values["start_date"] < date.today():
            raise ApiError("Pick-up date can't be in the past.")
    with transaction() as cur:
        car = check_rental(cur, values)
        if values.get("total_price") is None:
            values["total_price"] = price_for(car, values["start_date"], values["end_date"])
        row = insert(cur, "rentals", values)
        return ok(201, record=rental_out(cur, row["id"]))


@app.patch("/api/rentals/<int:rental_id>")
@app.put("/api/rentals/<int:rental_id>")
@login_required
def rental_update(rental_id):
    data = body()
    with transaction() as cur:
        current = get_or_404(cur, "rentals", rental_id, lock=True)

        if not is_admin():
            check_customer_access(current["customer_id"])
            if set(data) - {"id"} != {"status"} or data.get("status") != "Cancelled":
                raise ApiError("You can only cancel your booking.", 403)
            if current["status"] != "Pending":
                raise ApiError("Only pending bookings can be cancelled.", 409)
            update(cur, "rentals", rental_id, {"status": "Cancelled"})
            return ok(record=rental_out(cur, rental_id))

        values = clean("rentals", data, partial=True)
        new_status = values.get("status", current["status"])
        if new_status != current["status"] and new_status not in STATUS_FLOW[current["status"]]:
            raise ApiError(f"Status can't change from {current['status']} to {new_status}.")

        merged = {**current, **values}
        car = check_rental(cur, merged, exclude_id=rental_id)
        moved = any(merged[k] != current[k] for k in ("car_id", "start_date", "end_date"))
        if moved and "total_price" not in values:
            values["total_price"] = price_for(car, merged["start_date"], merged["end_date"])
        update(cur, "rentals", rental_id, values)
        return ok(record=rental_out(cur, rental_id))


@app.delete("/api/rentals/<int:rental_id>")
@admin_required
def rental_delete(rental_id):
    with transaction() as cur:
        delete(cur, "rentals", rental_id)
    return ok(deleted_id=rental_id)


# ============================================================
# 10. PAYMENTS
# ============================================================

def check_payment(cur, payment, exclude_id=None):
    rental = get_or_404(cur, "rentals", payment["rental_id"], lock=True)
    if payment["payment_status"] != "Paid":
        return
    cur.execute(
        """SELECT COALESCE(SUM(amount), 0) AS paid FROM payments
           WHERE rental_id = %s AND payment_status = 'Paid' AND id <> %s""",
        (payment["rental_id"], exclude_id or 0),
    )
    if cur.fetchone()["paid"] + payment["amount"] > rental["total_price"]:
        raise ApiError("Payment exceeds the remaining balance of this rental.")


@app.get("/api/payments")
@login_required
def payments_list():
    with transaction() as cur:
        if is_admin():
            cur.execute("SELECT * FROM payments ORDER BY id")
        else:
            cur.execute(
                """SELECT p.* FROM payments p JOIN rentals r ON r.id = p.rental_id
                   WHERE r.customer_id = %s ORDER BY p.id""",
                (own_customer_id(),),
            )
        return ok(payments=[to_json(r) for r in cur.fetchall()])


@app.get("/api/payments/<int:payment_id>")
@login_required
def payment_get(payment_id):
    with transaction() as cur:
        payment = get_or_404(cur, "payments", payment_id)
        rental = get_or_404(cur, "rentals", payment["rental_id"])
        check_customer_access(rental["customer_id"])
        return ok(payment=to_json(payment))


@app.post("/api/payments")
@admin_required
def payment_create():
    values = clean("payments", body())
    with transaction() as cur:
        check_payment(cur, values)
        return ok(201, record=to_json(insert(cur, "payments", values)))


@app.patch("/api/payments/<int:payment_id>")
@app.put("/api/payments/<int:payment_id>")
@admin_required
def payment_update(payment_id):
    values = clean("payments", body(), partial=True)
    with transaction() as cur:
        current = get_or_404(cur, "payments", payment_id, lock=True)
        check_payment(cur, {**current, **values}, exclude_id=payment_id)
        return ok(record=to_json(update(cur, "payments", payment_id, values)))


@app.delete("/api/payments/<int:payment_id>")
@admin_required
def payment_delete(payment_id):
    with transaction() as cur:
        delete(cur, "payments", payment_id)
    return ok(deleted_id=payment_id)


# ============================================================
# 11. REPORTS (the three report queries, admin only)
# ============================================================

REPORTS = {
    "rental-details": """
        SELECT r.id AS rental_id, c.name AS customer, ca.brand || ' ' || ca.model AS car,
               r.start_date, r.end_date, r.total_price, r.status
        FROM rentals r
        JOIN customers c ON c.id = r.customer_id
        JOIN cars ca ON ca.id = r.car_id
        ORDER BY r.start_date""",
    "monthly-revenue": """
        SELECT to_char(payment_date, 'YYYY-MM') AS month, COUNT(*) AS payment_count, SUM(amount) AS revenue
        FROM payments WHERE payment_status = 'Paid'
        GROUP BY to_char(payment_date, 'YYYY-MM') ORDER BY month""",
    "above-average-cars": """
        SELECT id, brand, model, price_per_day FROM cars
        WHERE price_per_day > (SELECT AVG(price_per_day) FROM cars)
        ORDER BY price_per_day DESC""",
}


@app.get("/api/reports/<name>")
@admin_required
def report(name):
    if name not in REPORTS:
        raise ApiError("Unknown report.", 404)
    with transaction() as cur:
        cur.execute(REPORTS[name])
        return ok(rows=[to_json(r) for r in cur.fetchall()])


# ============================================================
# 12. FRONTEND (static files from the repository root)
# ============================================================

STATIC_TYPES = {".html", ".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico"}
BLOCKED_DIRS = {"backend", "tools"}


def not_found_page():
    return send_from_directory(REPO_ROOT, "404.html"), 404


def servable(path):
    parts = [p for p in path.split("/") if p]
    if parts and (parts[0] in BLOCKED_DIRS or any(p.startswith(".") for p in parts)):
        return None
    full = safe_join(REPO_ROOT, path)
    return full


@app.get("/")
@app.get("/<path:path>")
def frontend(path=""):
    if path == "api" or path.startswith("api/"):
        raise ApiError("Not found.", 404)
    full = servable(path)
    if full is None:
        return not_found_page()
    if os.path.isdir(full):
        if path and not path.endswith("/"):
            return redirect("/" + path + "/", 301)
        if os.path.isfile(os.path.join(full, "index.html")):
            return send_from_directory(full, "index.html")
    elif os.path.isfile(full) and os.path.splitext(full)[1].lower() in STATIC_TYPES:
        return send_from_directory(REPO_ROOT, path)
    elif os.path.isfile(full + ".html"):
        return send_from_directory(REPO_ROOT, path + ".html")
    return not_found_page()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )

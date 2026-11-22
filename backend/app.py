import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import psycopg2
from psycopg2 import errors, sql
from psycopg2.extras import RealDictCursor

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash


# ============================================================
# 1. APPLICATION CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)


# ============================================================
# 2. DATABASE CONNECTION
# ============================================================

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "rentacar_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD")
    )


# ============================================================
# 3. TABLE CONFIGURATION
# ============================================================

PRIMARY_KEYS = {
    "cars": "car_id",
    "customers": "customer_id",
    "rentals": "rental_id",
    "payments": "payment_id",
    "users": "user_id",
    "roles": "role_id"
}


CONFIG = {
    "cars": {
        "fields": (
            "brand",
            "model",
            "license_plate",
            "year",
            "price_per_day",
            "status"
        ),
        "required": (
            "brand",
            "model",
            "license_plate",
            "year",
            "price_per_day"
        ),
        "defaults": {
            "status": "Available"
        }
    },

    "customers": {
        "fields": (
            "full_name",
            "email",
            "phone"
        ),
        "required": (
            "full_name",
            "email",
            "phone"
        ),
        "defaults": {}
    },

    "rentals": {
        "fields": (
            "customer_id",
            "car_id",
            "start_date",
            "end_date"
        ),
        "required": (
            "customer_id",
            "car_id",
            "start_date",
            "end_date"
        ),
        "defaults": {}
    },

    "payments": {
        "fields": (
            "rental_id",
            "amount",
            "payment_method",
            "payment_status"
        ),
        "required": (
            "rental_id",
            "amount",
            "payment_method",
            "payment_status"
        ),
        "defaults": {}
    },

    "users": {
        "fields": (
            "username",
            "password",
            "role_id"
        ),
        "required": (
            "username",
            "password",
            "role_id"
        ),
        "defaults": {}
    },

    "roles": {
        "fields": (
            "role_name",
        ),
        "required": (
            "role_name",
        ),
        "defaults": {}
    }
}


# ============================================================
# 4. JSON SERIALIZATION
# ============================================================

def serialize(row):
    if row is None:
        return None

    result = {}

    for key, value in dict(row).items():

        # Never expose password hashes in API responses
        if key == "password_hash":
            continue

        if isinstance(value, Decimal):
            result[key] = float(value)

        elif isinstance(value, date):
            result[key] = value.isoformat()

        else:
            result[key] = value

    return result


# ============================================================
# 5. INPUT VALIDATION
# ============================================================

def validate_data(table, data, partial=False):

    if not isinstance(data, dict):
        return None, "A JSON object is required."

    config = CONFIG[table]

    allowed_fields = set(config["fields"])

    unknown_fields = set(data) - allowed_fields

    if unknown_fields:
        return (
            None,
            "Unknown fields: " + ", ".join(sorted(unknown_fields))
        )

    if partial and not data:
        return None, "At least one field is required."

    if not partial:

        missing_fields = set(config["required"]) - set(data)

        if missing_fields:
            return (
                None,
                "Missing fields: " + ", ".join(sorted(missing_fields))
            )

    cleaned = {}

    text_fields = {
        "brand",
        "model",
        "license_plate",
        "full_name",
        "email",
        "phone",
        "username",
        "role_name"
    }

    integer_fields = {
        "year",
        "customer_id",
        "car_id",
        "rental_id",
        "role_id"
    }

    for field, value in data.items():

        # Text fields
        if field in text_fields:

            if not isinstance(value, str) or not value.strip():
                return None, f"{field} must be a non-empty string."

            cleaned[field] = value.strip()

        # Password
        elif field == "password":

            if not isinstance(value, str) or len(value) < 8:
                return None, "Password must contain at least 8 characters."

            cleaned[field] = value

        # Integer fields
        elif field in integer_fields:

            if type(value) is not int:
                return None, f"{field} must be an integer."

            if field == "year":

                if not 1886 <= value <= 2100:
                    return None, "Invalid vehicle year."

            elif value < 1:
                return None, f"{field} must be positive."

            cleaned[field] = value

        # Decimal fields
        elif field in ("price_per_day", "amount"):

            if type(value) not in (int, float, str):
                return None, f"{field} must be numeric."

            try:
                number = Decimal(str(value))

            except InvalidOperation:
                return None, f"Invalid {field}."

            if (
                not number.is_finite()
                or number < 0
                or number > Decimal("9999999999.99")
                or number.as_tuple().exponent < -2
            ):
                return None, f"Invalid {field}."

            cleaned[field] = number

        # Date fields
        elif field in ("start_date", "end_date"):

            if not isinstance(value, str):
                return None, f"{field} must be YYYY-MM-DD."

            try:
                parsed = date.fromisoformat(value)

                if parsed.isoformat() != value:
                    raise ValueError()

            except ValueError:
                return None, f"{field} must be YYYY-MM-DD."

            cleaned[field] = value

        # Car status
        elif field == "status":

            if value not in (
                "Available",
                "Rented",
                "Maintenance"
            ):
                return None, "Invalid car status."

            cleaned[field] = value

        # Payment method
        elif field == "payment_method":

            if value not in ("Cash", "Card"):
                return None, "Invalid payment method."

            cleaned[field] = value

        # Payment status
        elif field == "payment_status":

            if value not in ("Paid", "Pending"):
                return None, "Invalid payment status."

            cleaned[field] = value

    # Email validation
    if "email" in cleaned:

        if not re.fullmatch(
            r"[^\s@]+@[^\s@]+\.[^\s@]+",
            cleaned["email"]
        ):
            return None, "Invalid email address."

    return cleaned, None


# ============================================================
# 6. DATABASE ERROR HANDLING
# ============================================================

def db_error(exc):

    if isinstance(exc, errors.UniqueViolation):

        return jsonify(
            error="A record with this unique value already exists."
        ), 409

    if isinstance(exc, errors.ForeignKeyViolation):

        return jsonify(
            error="Referenced record does not exist or is in use."
        ), 409

    if isinstance(exc, errors.CheckViolation):

        return jsonify(
            error="Database constraint violation."
        ), 400

    if isinstance(exc, errors.NotNullViolation):

        return jsonify(
            error="A required database field is missing."
        ), 400

    app.logger.exception("Database error")

    return jsonify(error="Database error"), 500


# ============================================================
# 7. RENTAL BUSINESS RULES
# ============================================================

def rental_rule(cur, values, exclude_id=None):

    start_date = values["start_date"]
    end_date = values["end_date"]

    customer_id = values["customer_id"]
    car_id = values["car_id"]

    # Validate rental dates
    if end_date < start_date:

        return "End date cannot be before start date."

    # Check customer
    cur.execute(
        """
        SELECT customer_id
        FROM customers
        WHERE customer_id = %s
        """,
        (customer_id,)
    )

    if cur.fetchone() is None:
        return "Customer not found."

    # Check car
    cur.execute(
        """
        SELECT status
        FROM cars
        WHERE car_id = %s
        FOR UPDATE
        """,
        (car_id,)
    )

    car = cur.fetchone()

    if car is None:
        return "Car not found."

    if car["status"] == "Maintenance":
        return "Car is under maintenance."

    # Check overlapping rentals
    cur.execute(
        """
        SELECT rental_id
        FROM rentals
        WHERE car_id = %s
          AND start_date <= %s
          AND end_date >= %s
          AND (%s IS NULL OR rental_id <> %s)
        LIMIT 1
        """,
        (
            car_id,
            end_date,
            start_date,
            exclude_id,
            exclude_id
        )
    )

    if cur.fetchone():
        return "Car already has a rental in this date range."

    return None


# ============================================================
# 8. HOME ENDPOINT
# ============================================================

@app.get("/")
def home():

    return jsonify(
        status="success",
        message="Rent a Car Management System API is running",
        tables=list(CONFIG.keys())
    )


# ============================================================
# 9. GET ALL RECORDS
# ============================================================

@app.get("/api/<table>")
def list_records(table):

    if table not in CONFIG:
        return jsonify(error="Not found"), 404

    primary_key = PRIMARY_KEYS[table]

    try:

        with get_db_connection() as conn:

            with conn.cursor(
                cursor_factory=RealDictCursor
            ) as cur:

                query = sql.SQL(
                    "SELECT * FROM {} ORDER BY {}"
                ).format(
                    sql.Identifier(table),
                    sql.Identifier(primary_key)
                )

                cur.execute(query)

                rows = [
                    serialize(row)
                    for row in cur.fetchall()
                ]

        return jsonify(
            status="success",
            **{table: rows}
        )

    except psycopg2.Error as exc:
        return db_error(exc)


# ============================================================
# 10. GET SINGLE RECORD
# ============================================================

@app.get("/api/<table>/<int:record_id>")
def get_record(table, record_id):

    if table not in CONFIG:
        return jsonify(error="Not found"), 404

    primary_key = PRIMARY_KEYS[table]

    try:

        with get_db_connection() as conn:

            with conn.cursor(
                cursor_factory=RealDictCursor
            ) as cur:

                query = sql.SQL(
                    "SELECT * FROM {} WHERE {} = %s"
                ).format(
                    sql.Identifier(table),
                    sql.Identifier(primary_key)
                )

                cur.execute(query, (record_id,))

                row = cur.fetchone()

        if row is None:
            return jsonify(error="Record not found"), 404

        singular_names = {
            "cars": "car",
            "customers": "customer",
            "rentals": "rental",
            "payments": "payment",
            "users": "user",
            "roles": "role"
        }

        return jsonify(
            status="success",
            **{singular_names[table]: serialize(row)}
        )

    except psycopg2.Error as exc:
        return db_error(exc)


# ============================================================
# 11. POST - CREATE RECORD
# ============================================================

@app.post("/api/<table>")
def create_record(table):

    if table not in CONFIG:
        return jsonify(error="Not found"), 404

    data, error = validate_data(
        table,
        request.get_json(silent=True)
    )

    if error:
        return jsonify(error=error), 400

    data = {
        **CONFIG[table]["defaults"],
        **data
    }

    # Hash password before saving a user
    if table == "users":

        password = data.pop("password")

        data["password_hash"] = generate_password_hash(
            password,
            method="scrypt"
        )

    try:

        with get_db_connection() as conn:

            with conn.cursor(
                cursor_factory=RealDictCursor
            ) as cur:

                if table == "rentals":

                    rule = rental_rule(cur, data)

                    if rule:
                        return jsonify(error=rule), 409

                fields = list(data.keys())

                columns = sql.SQL(", ").join(
                    sql.Identifier(field)
                    for field in fields
                )

                placeholders = sql.SQL(", ").join(
                    sql.Placeholder()
                    for _ in fields
                )

                query = sql.SQL(
                    "INSERT INTO {} ({}) VALUES ({}) RETURNING *"
                ).format(
                    sql.Identifier(table),
                    columns,
                    placeholders
                )

                values = [
                    data[field]
                    for field in fields
                ]

                cur.execute(query, values)

                row = serialize(cur.fetchone())

        return jsonify(
            status="success",
            message="Created successfully",
            record=row
        ), 201

    except psycopg2.Error as exc:
        return db_error(exc)


# ============================================================
# 12. PUT / PATCH - UPDATE RECORD
# ============================================================

@app.route(
    "/api/<table>/<int:record_id>",
    methods=["PUT", "PATCH"]
)
def update_record(table, record_id):

    if table not in CONFIG:
        return jsonify(error="Not found"), 404

    data, error = validate_data(
        table,
        request.get_json(silent=True),
        partial=True
    )

    if error:
        return jsonify(error=error), 400

    # Hash a new password if provided
    if table == "users" and "password" in data:

        password = data.pop("password")

        data["password_hash"] = generate_password_hash(
            password,
            method="scrypt"
        )

    primary_key = PRIMARY_KEYS[table]

    try:

        with get_db_connection() as conn:

            with conn.cursor(
                cursor_factory=RealDictCursor
            ) as cur:

                select_query = sql.SQL(
                    "SELECT * FROM {} WHERE {} = %s FOR UPDATE"
                ).format(
                    sql.Identifier(table),
                    sql.Identifier(primary_key)
                )

                cur.execute(select_query, (record_id,))

                existing = cur.fetchone()

                if existing is None:
                    return jsonify(error="Record not found"), 404

                # Validate updated rental
                if table == "rentals":

                    existing_data = serialize(existing)

                    combined = {
                        field: data.get(
                            field,
                            existing_data[field]
                        )
                        for field in CONFIG[table]["fields"]
                    }

                    rule = rental_rule(
                        cur,
                        combined,
                        record_id
                    )

                    if rule:
                        return jsonify(error=rule), 409

                fields = list(data.keys())

                assignments = sql.SQL(", ").join(
                    sql.SQL("{} = %s").format(
                        sql.Identifier(field)
                    )
                    for field in fields
                )

                update_query = sql.SQL(
                    "UPDATE {} SET {} WHERE {} = %s RETURNING *"
                ).format(
                    sql.Identifier(table),
                    assignments,
                    sql.Identifier(primary_key)
                )

                values = [
                    data[field]
                    for field in fields
                ]

                values.append(record_id)

                cur.execute(update_query, values)

                row = serialize(cur.fetchone())

        return jsonify(
            status="success",
            message="Updated successfully",
            record=row
        )

    except psycopg2.Error as exc:
        return db_error(exc)


# ============================================================
# 13. DELETE RECORD
# ============================================================

@app.delete("/api/<table>/<int:record_id>")
def delete_record(table, record_id):

    if table not in CONFIG:
        return jsonify(error="Not found"), 404

    primary_key = PRIMARY_KEYS[table]

    try:

        with get_db_connection() as conn:

            with conn.cursor(
                cursor_factory=RealDictCursor
            ) as cur:

                query = sql.SQL(
                    "DELETE FROM {} WHERE {} = %s RETURNING {}"
                ).format(
                    sql.Identifier(table),
                    sql.Identifier(primary_key),
                    sql.Identifier(primary_key)
                )

                cur.execute(query, (record_id,))

                row = cur.fetchone()

        if row is None:
            return jsonify(error="Record not found"), 404

        return jsonify(
            status="success",
            message="Deleted successfully",
            deleted_id=record_id
        )

    except psycopg2.Error as exc:
        return db_error(exc)


# ============================================================
# 14. RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
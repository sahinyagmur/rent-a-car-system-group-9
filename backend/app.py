import os

import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)


# PostgreSQL connection
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="rentacar_db",
        user="postgres",
        password=os.getenv("DB_PASSWORD")
    )


# Convert database row to JSON
def car_to_dict(row):
    return {
        "id": row[0],
        "brand": row[1],
        "model": row[2],
        "year": row[3],
        "price_per_day": float(row[4]),
        "available": row[5]
    }


# Validate car information
def validate_car(data, partial=False):
    if not isinstance(data, dict):
        return "A JSON object is required."

    allowed = {
        "brand",
        "model",
        "year",
        "price_per_day",
        "available"
    }

    if not partial:
        required = {
            "brand",
            "model",
            "year",
            "price_per_day"
        }

        missing = required - data.keys()

        if missing:
            return f"Missing fields: {', '.join(sorted(missing))}"

    if partial and not data:
        return "At least one field is required."

    unknown = data.keys() - allowed

    if unknown:
        return f"Unknown fields: {', '.join(sorted(unknown))}"

    for field in ("brand", "model"):
        if field in data:
            if (
                not isinstance(data[field], str)
                or not data[field].strip()
            ):
                return f"{field} must be a non-empty string."

    if "year" in data:
        if (
            type(data["year"]) is not int
            or not 1886 <= data["year"] <= 2100
        ):
            return "year must be a valid integer."

    if "price_per_day" in data:
        price = data["price_per_day"]

        if (
            type(price) not in (int, float)
            or not 0 <= price <= 99999999.99
        ):
            return "price_per_day must be a non-negative number."

    if "available" in data:
        if type(data["available"]) is not bool:
            return "available must be true or false."

    return None


# HOME
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "success",
        "message": "Rent a Car API is running"
    }), 200


# GET - List all cars
@app.route("/api/cars", methods=["GET"])
def get_cars():
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, brand, model, year,
                   price_per_day, available
            FROM cars
            ORDER BY id
        """)

        rows = cursor.fetchall()
        cursor.close()

        return jsonify({
            "status": "success",
            "cars": [car_to_dict(row) for row in rows]
        }), 200

    except psycopg2.Error:
        app.logger.exception("Database error")
        return jsonify({
            "error": "Database error"
        }), 500

    finally:
        if conn:
            conn.close()


# GET - Get car by ID
@app.route("/api/cars/<int:car_id>", methods=["GET"])
def get_car(car_id):
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, brand, model, year,
                   price_per_day, available
            FROM cars
            WHERE id = %s
        """, (car_id,))

        row = cursor.fetchone()
        cursor.close()

        if row is None:
            return jsonify({
                "error": "Car not found"
            }), 404

        return jsonify({
            "status": "success",
            "car": car_to_dict(row)
        }), 200

    except psycopg2.Error:
        app.logger.exception("Database error")
        return jsonify({
            "error": "Database error"
        }), 500

    finally:
        if conn:
            conn.close()


# POST - Add new car
@app.route("/api/cars", methods=["POST"])
def add_car():
    data = request.get_json(silent=True)

    error = validate_car(data)

    if error:
        return jsonify({
            "error": error
        }), 400

    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO cars
                (brand, model, year, price_per_day, available)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, brand, model, year,
                      price_per_day, available
        """, (
            data["brand"].strip(),
            data["model"].strip(),
            data["year"],
            data["price_per_day"],
            data.get("available", True)
        ))

        new_car = cursor.fetchone()

        conn.commit()
        cursor.close()

        return jsonify({
            "status": "success",
            "message": "Car added successfully",
            "car": car_to_dict(new_car)
        }), 201

    except psycopg2.Error:
        if conn:
            conn.rollback()

        app.logger.exception("Database error")

        return jsonify({
            "error": "Database error"
        }), 500

    finally:
        if conn:
            conn.close()


# PUT - Update car
@app.route("/api/cars/<int:car_id>", methods=["PUT"])
def update_car(car_id):
    data = request.get_json(silent=True)

    error = validate_car(data, partial=True)

    if error:
        return jsonify({
            "error": error
        }), 400

    fields = []
    values = []

    for field in (
        "brand",
        "model",
        "year",
        "price_per_day",
        "available"
    ):
        if field in data:
            fields.append(f"{field} = %s")

            value = data[field]

            if field in ("brand", "model"):
                value = value.strip()

            values.append(value)

    values.append(car_id)

    query = f"""
        UPDATE cars
        SET {', '.join(fields)}
        WHERE id = %s
        RETURNING id, brand, model, year,
                  price_per_day, available
    """

    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(query, values)

        updated_car = cursor.fetchone()

        conn.commit()
        cursor.close()

        if updated_car is None:
            return jsonify({
                "error": "Car not found"
            }), 404

        return jsonify({
            "status": "success",
            "message": "Car updated successfully",
            "car": car_to_dict(updated_car)
        }), 200

    except psycopg2.Error:
        if conn:
            conn.rollback()

        app.logger.exception("Database error")

        return jsonify({
            "error": "Database error"
        }), 500

    finally:
        if conn:
            conn.close()


# DELETE - Delete car
@app.route("/api/cars/<int:car_id>", methods=["DELETE"])
def delete_car(car_id):
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM cars
            WHERE id = %s
            RETURNING id
        """, (car_id,))

        deleted_car = cursor.fetchone()

        conn.commit()
        cursor.close()

        if deleted_car is None:
            return jsonify({
                "error": "Car not found"
            }), 404

        return jsonify({
            "status": "success",
            "message": "Car deleted successfully",
            "deleted_id": car_id
        }), 200

    except psycopg2.Error:
        if conn:
            conn.rollback()

        app.logger.exception("Database error")

        return jsonify({
            "error": "Database error"
        }), 500

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    app.run(debug=True)
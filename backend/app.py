import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import psycopg2
from psycopg2 import errors, sql
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
app = Flask(__name__)


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '5432')),
        dbname=os.getenv('DB_NAME', 'rentacar_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD'),
    )


CONFIG = {
    'cars': {
        'fields': ('brand', 'model', 'license_plate', 'year', 'price_per_day', 'status'),
        'required': ('brand', 'model', 'license_plate', 'year', 'price_per_day'),
        'defaults': {'status': 'Available'},
    },
    'customers': {
        'fields': ('name', 'email', 'phone'),
        'required': ('name', 'email', 'phone'),
        'defaults': {},
    },
    'rentals': {
        'fields': ('customer_id', 'car_id', 'start_date', 'end_date'),
        'required': ('customer_id', 'car_id', 'start_date', 'end_date'),
        'defaults': {},
    },
    'payments': {
        'fields': ('rental_id', 'amount', 'payment_method', 'payment_status'),
        'required': ('rental_id', 'amount', 'payment_method', 'payment_status'),
        'defaults': {},
    },
}


def validate_data(table, data, partial=False):
    if not isinstance(data, dict):
        return None, 'A JSON object is required.'
    cfg = CONFIG[table]
    unknown = set(data) - set(cfg['fields'])
    if unknown:
        return None, 'Unknown fields: ' + ', '.join(sorted(unknown))
    if partial and not data:
        return None, 'At least one field is required.'
    if not partial:
        missing = set(cfg['required']) - set(data)
        if missing:
            return None, 'Missing fields: ' + ', '.join(sorted(missing))
    cleaned = dict(data)
    for field, value in data.items():
        if field in ('brand', 'model', 'license_plate', 'name', 'email', 'phone'):
            if not isinstance(value, str) or not value.strip():
                return None, f'{field} must be a non-empty string.'
            cleaned[field] = value.strip()
        elif field in ('year', 'customer_id', 'car_id', 'rental_id'):
            if type(value) is not int or (field == 'year' and not 1886 <= value <= 2100) or (field != 'year' and value < 1):
                return None, f'{field} must be a valid integer.'
        elif field in ('price_per_day', 'amount'):
            if type(value) not in (int, float, str):
                return None, f'{field} must be a non-negative number.'
            try:
                number = Decimal(str(value))
            except InvalidOperation:
                return None, f'{field} must be a non-negative number.'
            if not number.is_finite() or number < 0 or number > Decimal('9999999999.99') or number.as_tuple().exponent < -2:
                return None, f'{field} must have at most two decimal places and be non-negative.'
            cleaned[field] = number
        elif field in ('start_date', 'end_date'):
            if not isinstance(value, str):
                return None, f'{field} must be YYYY-MM-DD.'
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError()
            except ValueError:
                return None, f'{field} must be YYYY-MM-DD.'
        elif field == 'status' and value not in ('Available', 'Rented', 'Maintenance'):
            return None, 'status must be Available, Rented, or Maintenance.'
        elif field == 'payment_method' and value not in ('Cash', 'Card'):
            return None, 'payment_method must be Cash or Card.'
        elif field == 'payment_status' and value not in ('Paid', 'Pending'):
            return None, 'payment_status must be Paid or Pending.'
    if 'email' in cleaned and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', cleaned['email']):
        return None, 'email must be valid.'
    return cleaned, None


def serialize(row):
    if row is None:
        return None
    return {key: (float(value) if isinstance(value, Decimal) else value.isoformat() if isinstance(value, date) else value)
            for key, value in dict(row).items()}


def db_error(exc):
    if isinstance(exc, errors.UniqueViolation):
        return jsonify(error='A record with this unique value already exists.'), 409
    if isinstance(exc, errors.ForeignKeyViolation):
        return jsonify(error='Referenced record does not exist, or this record is in use.'), 409
    if isinstance(exc, errors.CheckViolation):
        return jsonify(error='Value violates a database constraint.'), 400
    app.logger.exception('Database error')
    return jsonify(error='Database error'), 500


def rental_rule(cur, values, exclude_id=None):
    """Reject invalid dates, missing references, unavailable cars, and overlapping bookings."""
    if values['end_date'] < values['start_date']:
        return 'End date cannot be before start date.'
    cur.execute('SELECT id FROM customers WHERE id = %s', (values['customer_id'],))
    if cur.fetchone() is None:
        return 'Customer not found.'
    cur.execute('SELECT status FROM cars WHERE id = %s FOR UPDATE', (values['car_id'],))
    car = cur.fetchone()
    if car is None:
        return 'Car not found.'
    if car['status'] == 'Maintenance':
        return 'Car is under maintenance.'
    # Rented is an informational status; booking conflicts are decided by dates.
    cur.execute('''
        SELECT id FROM rentals
        WHERE car_id = %s AND start_date <= %s AND end_date >= %s
          AND (%s IS NULL OR id <> %s)
        LIMIT 1
    ''', (values['car_id'], values['end_date'], values['start_date'], exclude_id, exclude_id))
    if cur.fetchone():
        return 'Car already has a rental in the selected date range.'
    return None


@app.get('/')
def home():
    return jsonify(status='success', message='Rent a Car API is running')


@app.get('/api/<table>')
def list_records(table):
    if table not in CONFIG:
        return jsonify(error='Not found'), 404
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql.SQL('SELECT * FROM {} ORDER BY id').format(sql.Identifier(table)))
                rows = [serialize(row) for row in cur.fetchall()]
        return jsonify(status='success', **{table: rows})
    except psycopg2.Error as exc:
        return db_error(exc)


@app.get('/api/<table>/<int:record_id>')
def get_record(table, record_id):
    if table not in CONFIG:
        return jsonify(error='Not found'), 404
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql.SQL('SELECT * FROM {} WHERE id = %s').format(sql.Identifier(table)), (record_id,))
                row = cur.fetchone()
        if row is None:
            return jsonify(error='Record not found'), 404
        return jsonify(status='success', **{table[:-1] if table != 'cars' else 'car': serialize(row)})
    except psycopg2.Error as exc:
        return db_error(exc)


@app.post('/api/<table>')
def create_record(table):
    if table not in CONFIG:
        return jsonify(error='Not found'), 404
    data, error = validate_data(table, request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400
    data = {**CONFIG[table]['defaults'], **data}
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if table == 'rentals':
                    rule = rental_rule(cur, data)
                    if rule:
                        return jsonify(error=rule), 409
                fields = list(data)
                query = sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING *').format(
                    sql.Identifier(table),
                    sql.SQL(', ').join(map(sql.Identifier, fields)),
                    sql.SQL(', ').join(sql.Placeholder() for _ in fields),
                )
                cur.execute(query, [data[f] for f in fields])
                row = serialize(cur.fetchone())
        return jsonify(status='success', message='Created successfully', record=row), 201
    except psycopg2.Error as exc:
        return db_error(exc)


@app.route('/api/<table>/<int:record_id>', methods=['PUT', 'PATCH'])
def update_record(table, record_id):
    if table not in CONFIG:
        return jsonify(error='Not found'), 404
    data, error = validate_data(table, request.get_json(silent=True), partial=True)
    if error:
        return jsonify(error=error), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql.SQL('SELECT * FROM {} WHERE id = %s FOR UPDATE').format(sql.Identifier(table)), (record_id,))
                existing = cur.fetchone()
                if existing is None:
                    return jsonify(error='Record not found'), 404
                if table == 'rentals':
                    combined = {key: data.get(key, serialize(existing)[key]) for key in CONFIG[table]['fields']}
                    rule = rental_rule(cur, combined, record_id)
                    if rule:
                        return jsonify(error=rule), 409
                fields = list(data)
                assignments = sql.SQL(', ').join(sql.SQL('{} = %s').format(sql.Identifier(f)) for f in fields)
                query = sql.SQL('UPDATE {} SET {} WHERE id = %s RETURNING *').format(sql.Identifier(table), assignments)
                cur.execute(query, [data[f] for f in fields] + [record_id])
                row = serialize(cur.fetchone())
        return jsonify(status='success', message='Updated successfully', record=row)
    except psycopg2.Error as exc:
        return db_error(exc)


@app.delete('/api/<table>/<int:record_id>')
def delete_record(table, record_id):
    if table not in CONFIG:
        return jsonify(error='Not found'), 404
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql.SQL('DELETE FROM {} WHERE id = %s RETURNING id').format(sql.Identifier(table)), (record_id,))
                row = cur.fetchone()
        if row is None:
            return jsonify(error='Record not found'), 404
        return jsonify(status='success', message='Deleted successfully', deleted_id=record_id)
    except psycopg2.Error as exc:
        return db_error(exc)


if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')

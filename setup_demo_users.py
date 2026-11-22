"""Populate missing demo users using Werkzeug-compatible password hashes.

Run from the backend directory after configuring .env and applying schema.sql.
Passwords are randomly generated and printed once; do not commit them.
"""
import os
import secrets
import string

import psycopg2
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

roles = [('admin_demo', 'Admin'), ('manager_demo', 'Manager'), ('employee_demo', 'Employee')]
chars = string.ascii_letters + string.digits + '!@#$%'

with psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=os.getenv('DB_PORT', '5432'),
    dbname=os.getenv('DB_NAME', 'rentacar_db'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD'),
) as conn:
    with conn.cursor() as cur:
        for username, role_name in roles:
            cur.execute('SELECT user_id FROM users WHERE username = %s', (username,))
            if cur.fetchone():
                print(f'{username}: already exists; unchanged')
                continue
            cur.execute('SELECT role_id FROM roles WHERE role_name = %s', (role_name,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f'Missing role {role_name}; run seed.sql first on a fresh database')
            password = ''.join(secrets.choice(chars) for _ in range(20))
            cur.execute('INSERT INTO users (username, password_hash, role_id) VALUES (%s, %s, %s)',
                        (username, generate_password_hash(password, method='scrypt'), row[0]))
            print(f'{username}: created; temporary password: {password}')
print('Done. Do not share or commit the displayed passwords.')

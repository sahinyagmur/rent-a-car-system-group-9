"""Account management from the command line (passwords are typed, never stored in files).

With Docker (on the server add sudo):
    docker compose exec web python manage.py set-password admin
    docker compose exec web python manage.py create-admin <username>
    docker compose exec web python manage.py rename-user admin <new_username>
    docker compose exec web python manage.py list-users

Without Docker: run the same commands with `python manage.py ...` inside backend/.
"""
import getpass
import sys

from werkzeug.security import generate_password_hash

from app import USERNAME_RE, transaction


def ask_password():
    password = getpass.getpass("New password: ")
    if len(password) < 8:
        sys.exit("Password must be at least 8 characters.")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords don't match.")
    return generate_password_hash(password, method="scrypt")


def check_username(username):
    if not USERNAME_RE.fullmatch(username):
        sys.exit("Username: 3-50 letters, digits, dot or underscore.")


def set_password(username):
    with transaction() as cur:
        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        if not cur.fetchone():
            sys.exit(f"No user named {username}.")
    hashed = ask_password()
    with transaction() as cur:
        cur.execute("UPDATE users SET password_hash = %s WHERE username = %s RETURNING id", (hashed, username))
        if not cur.fetchone():
            sys.exit(f"No user named {username}.")
    print(f"Password changed for {username}.")


def create_admin(username):
    check_username(username)
    hashed = ask_password()
    with transaction() as cur:
        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            sys.exit(f"{username} already exists. Use set-password instead.")
        cur.execute(
            """INSERT INTO users (username, password_hash, role_id)
               VALUES (%s, %s, (SELECT id FROM roles WHERE role_name = 'admin'))""",
            (username, hashed),
        )
    print(f"Admin {username} created.")


def rename_user(old, new):
    check_username(new)
    with transaction() as cur:
        cur.execute("SELECT 1 FROM users WHERE username = %s", (new,))
        if cur.fetchone():
            sys.exit(f"{new} already exists.")
        cur.execute("UPDATE users SET username = %s WHERE username = %s RETURNING id", (new, old))
        if not cur.fetchone():
            sys.exit(f"No user named {old}.")
    print(f"Renamed {old} to {new}.")


def list_users():
    with transaction() as cur:
        cur.execute("""SELECT u.id, u.username, r.role_name FROM users u
                       JOIN roles r ON r.id = u.role_id ORDER BY u.id""")
        for row in cur.fetchall():
            print(f"{row['id']:>4}  {row['username']:<30} {row['role_name']}")


COMMANDS = {
    "set-password": (set_password, 1),
    "create-admin": (create_admin, 1),
    "rename-user": (rename_user, 2),
    "list-users": (list_users, 0),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS or len(sys.argv) - 2 != COMMANDS[sys.argv[1]][1]:
        sys.exit(__doc__)
    func, _ = COMMANDS[sys.argv[1]]
    func(*sys.argv[2:])

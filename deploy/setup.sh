#!/usr/bin/env bash
# Installs and starts the Rent a Car app on a fresh Ubuntu 22.04/24.04 server.
# Safe to run again: it updates the code and restarts the containers,
# and keeps the existing .env (passwords) and database.
#
#   git clone https://github.com/sahinyagmur/rent-a-car-system-group-9.git
#   cd rent-a-car-system-group-9
#   bash deploy/setup.sh
set -euo pipefail

cd "$(dirname "$0")/.."
APP_DIR="$(pwd)"
echo "==> App directory: $APP_DIR"

# 1. Docker + Compose from Ubuntu packages
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "==> Installing Docker"
  sudo apt-get update -y
  sudo apt-get install -y docker.io docker-compose-v2 git curl openssl
  sudo systemctl enable --now docker
fi

# 2. Latest code
if [ -d .git ]; then
  echo "==> Updating code"
  git pull --ff-only
fi

# 3. Production settings: random DB password and session secret, site on port 80
if [ ! -f .env ]; then
  echo "==> Creating .env with random secrets"
  umask 077
  cat > .env <<EOF
DB_NAME=rentacar_db
DB_USER=postgres
DB_PASSWORD=$(openssl rand -hex 24)
SECRET_KEY=$(openssl rand -hex 32)
WEB_PORT=80
SESSION_COOKIE_SECURE=false
EOF
else
  echo "==> Keeping existing .env"
fi

# 4. Build and start (containers restart automatically after a reboot)
echo "==> Starting containers"
sudo docker compose up -d --build
sudo docker compose ps

# 5. Health check
echo "==> Waiting for the app"
for _ in $(seq 1 30); do
  if curl -fsS http://localhost/api/health; then
    echo
    echo "==> Done. Open http://<this server's public IP>/ in a browser."
    exit 0
  fi
  sleep 2
done
echo "!! App did not answer. Logs:"
sudo docker compose logs --tail 50 web
exit 1

#!/usr/bin/env bash
# One-time (and re-runnable) server setup for Ubuntu 22.04 / 24.04.
#
#   git clone https://github.com/sahinyagmur/rent-a-car-system-group-9.git
#   cd rent-a-car-system-group-9
#   sudo bash deploy/setup-server.sh
#
# Installs Docker, creates .env with random secrets (only if it doesn't exist),
# and starts the database + web app on port 80. Running it again pulls the
# latest code and restarts the app; the database data is kept.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash deploy/setup-server.sh" >&2
  exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "==> Installing Docker and git"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 git openssl
systemctl enable --now docker

# Small VMs (1 GB RAM) can run out of memory while building; add 1 GB swap once.
if [ ! -f /swapfile ] && [ "$(awk '/MemTotal/ {print $2}' /proc/meminfo)" -lt 2000000 ]; then
  echo "==> Adding 1 GB swap"
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

if [ ! -f .env ]; then
  echo "==> Creating .env with random secrets"
  cat > .env <<EOF
DB_NAME=rentacar_db
DB_USER=postgres
DB_PASSWORD=$(openssl rand -hex 24)
SECRET_KEY=$(openssl rand -hex 32)
WEB_PORT=80
SESSION_COOKIE_SECURE=false
EOF
  chmod 600 .env
else
  echo "==> Keeping existing .env"
fi

if [ -d .git ]; then
  echo "==> Pulling latest code"
  sudo -u "${SUDO_USER:-root}" git pull --ff-only || git pull --ff-only
fi

echo "==> Building and starting containers"
docker compose up -d --build

echo "==> Waiting for the app"
for i in $(seq 1 30); do
  if curl -fs http://localhost/api/health >/dev/null; then break; fi
  sleep 2
done
curl -fs http://localhost/api/health && echo

IP="$(curl -fs https://api.ipify.org || hostname -I | awk '{print $1}')"
echo
echo "Done. Open:  http://$IP"
echo "If it doesn't open, allow inbound TCP port 80 in the cloud firewall (network security group)."

# Deployment (Chapter 7)

Target: an Ubuntu virtual machine with a public IP, running `docker compose`. Tested setup: **Azure for Students**, Ubuntu Server 24.04 LTS, size **B1s** (1 vCPU, 1 GB RAM — included in the free student offer).

## 1. Create the VM (Azure portal)

1. Activate **Azure for Students** with the university e-mail (no credit card; includes credit + free B1s hours).
2. *Virtual machines → Create → Azure virtual machine*
   - Image: **Ubuntu Server 24.04 LTS – x64**
   - Size: **Standard_B1s**
   - Authentication: **SSH public key**, username `azureuser`, key pair name `rentacar-key` → download the `.pem` file when asked and keep it safe (never commit it)
   - Inbound ports: **SSH (22)** and **HTTP (80)**
3. *Review + create → Create*. Note the **Public IP address**.

If you forgot port 80: VM → *Networking → Add inbound port rule* → port 80, TCP, Allow.

## 2. Connect with SSH (Windows PowerShell)

```powershell
ssh -i $HOME\Downloads\rentacar-key.pem azureuser@<PUBLIC_IP>
```

(If Windows complains the key is too open: right-click the file → Properties → Security → leave only your user with Read.)

## 3. Install and start the app (on the server)

```bash
git clone https://github.com/sahinyagmur/rent-a-car-system-group-9.git
cd rent-a-car-system-group-9
sudo bash deploy/setup-server.sh
```

The script installs Docker, writes `.env` with random `DB_PASSWORD` / `SECRET_KEY`, and runs `docker compose up -d --build` on port 80. Open `http://<PUBLIC_IP>` and log in with the test accounts from the main README.

## 4. Updating after new commits

```bash
cd ~/rent-a-car-system-group-9
sudo bash deploy/setup-server.sh      # pulls, rebuilds, restarts; data is kept
```

Useful commands: `sudo docker compose ps`, `sudo docker compose logs -f web`, reset the database to the sample data: `sudo docker compose down -v && sudo docker compose up -d`.

## 5. Domain (bonus, optional)

1. Buy a cheap domain (≤ 50 TL) from any registrar.
2. In the registrar's DNS settings add an **A record**: host `@` (and `www`) → `<PUBLIC_IP>`.
3. After a few minutes `http://yourdomain` opens the same site. No server change is needed.

Optional HTTPS later: put Caddy in front of the web container; then set `SESSION_COOKIE_SECURE=true` in `.env`.

## Screenshots for the report

VM overview page (public IP), the networking rules (ports 22/80), the SSH session running `setup-server.sh`, `sudo docker compose ps`, and the site opened by IP (and by domain).

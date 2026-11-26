# Deployment (Chapter 7)

Target: an Ubuntu virtual machine with a public IP, running `docker compose`.

**Our live setup:** **AWS (Amazon Web Services) Free Tier**, Amazon EC2 instance in region **eu-north-1 (Stockholm)**:

| Item | Value |
|---|---|
| Instance type | `t3.micro` (2 vCPU, 1 GB RAM, Free Tier eligible) |
| Operating system | Ubuntu Server 24.04 LTS (x86_64) |
| Disk | 8 GB gp3 (EBS) |
| Public IP | Elastic IP `13.50.166.44` (fixed, does not change when the instance restarts) |
| Firewall | Security group: 22 (SSH, only from our own IP), 80 (HTTP) and 443 (HTTPS) from anywhere |
| SSH login | key pair `rentacar-key` (`.pem` file), user `ubuntu` |
| Domain | **https://rentcar9.site** (Hostinger) |

## 1. Create the VM (AWS console)

1. Create an AWS account (Free Tier) and open the **EC2** console. Choose region **Europe (Stockholm) eu-north-1** (top right).
2. *Instances → Launch instances*
   - Name: `rentacar-server`
   - AMI: **Ubuntu Server 24.04 LTS (HVM), SSD Volume Type – 64-bit (x86)**
   - Instance type: **t3.micro** (Free Tier eligible)
   - Key pair: *Create new key pair* → name `rentacar-key`, type RSA, format `.pem` → the file downloads once; keep it safe and **never commit it**
   - Network settings → *Create security group* and allow:
     - **SSH (22)** – source **My IP**
     - **HTTP (80)** – source Anywhere (0.0.0.0/0)
     - **HTTPS (443)** – source Anywhere (needed for the domain with HTTPS)
   - Storage: 8 GB gp3 (default)
3. *Launch instance*.
4. Give the server a fixed IP: *Network & Security → Elastic IPs → Allocate Elastic IP address*, then *Actions → Associate Elastic IP address* → choose the instance. Without this the public IP changes after a stop/start. (An Elastic IP is free while it is attached to a running instance.)

If the site doesn't open later, check the security group: *Instance → Security tab → security group → Edit inbound rules*.

If SSH suddenly times out, your home IP address has probably changed: edit the SSH (22) rule and set the source to **My IP** again.

## 2. Connect with SSH (Windows PowerShell)

```powershell
ssh -i $HOME\.ssh\rentacar-key.pem ubuntu@13.50.166.44
```

(Use the path where you saved the `.pem` file. If Windows complains the key is too open: right-click the file → Properties → Security → leave only your user with Read.)

## 3. Install and start the app (on the server)

```bash
git clone https://github.com/sahinyagmur/rent-a-car-system-group-9.git
cd rent-a-car-system-group-9
sudo bash deploy/setup-server.sh
```

The script installs Docker, Docker Compose and git, adds 1 GB swap on small (1 GB RAM) servers, writes `.env` with random `DB_PASSWORD` / `SECRET_KEY`, and runs `docker compose up -d --build` on port 80. Open `http://<PUBLIC_IP>` and log in with the test accounts from the main README.

Three containers run on the server: `db` (PostgreSQL 16, not reachable from the internet), `web` (Flask + gunicorn) and, with a domain, `caddy` (HTTPS).

## 4. Updating after new commits

```bash
cd ~/rent-a-car-system-group-9
sudo bash deploy/setup-server.sh      # pulls, rebuilds, restarts; data is kept
```

Useful commands: `sudo docker compose ps`, `sudo docker compose logs -f web`, reset the database to the sample data: `sudo docker compose down -v && sudo docker compose up -d`.

## Accounts and passwords

- `.env` holds the **database password** and **SECRET_KEY** (random, created by the script). The app and the database both read the same file, so you never type them. Don't delete `.env` while keeping the database: PostgreSQL keeps the password it was created with. If `.env` is lost, reset with `sudo docker compose down -v` (deletes the data) and run the script again.
- **Site accounts** (admin/customers) are in the database. Change them on the server — the command asks for the password, it never ends up in a file:

  ```bash
  sudo docker compose exec web python manage.py list-users
  sudo docker compose exec web python manage.py set-password admin
  sudo docker compose exec web python manage.py rename-user admin <new_name>
  sudo docker compose exec web python manage.py create-admin <username>
  ```

  The graders need a working test login for each role (guideline: README). If you change the `admin` password on the live site, put the new test credentials in the README you submit, or create a separate personal admin with `create-admin` and keep `admin` / `Admin123!` as the test account.

## 5. Domain (bonus, optional)

1. Buy a cheap domain (≤ 50 TL) from any registrar.
2. In the registrar's DNS settings add an **A record**: host `@` (and `www`) → `<PUBLIC_IP>`.
3. After a few minutes `http://yourdomain` opens the same site.

   Our DNS records at Hostinger: `A  @ → 13.50.166.44` and `CNAME  www → rentcar9.site`.
4. Turn on HTTPS (free Let's Encrypt certificate, `www.` redirects to the bare domain, `http` redirects to `https`). Ports 80 and 443 must be open in the firewall:

   ```bash
   cd ~/rent-a-car-system-group-9 && git pull
   sudo bash deploy/setup-server.sh --domain yourdomain.com
   ```

   This adds `DOMAIN`, `WEB_PORT=127.0.0.1:5000` and `SESSION_COOKIE_SECURE=true` to `.env` and starts the `caddy` service (`deploy/Caddyfile`). Later runs of the script keep HTTPS on.

   With HTTPS on, `http://13.50.166.44` (the IP) and `www.rentcar9.site` redirect to **https://rentcar9.site**.

## Screenshots for the report (Chapter 7)

- EC2 *Instances* page: instance `t3.micro`, state *Running*, region eu-north-1, the public IP / Elastic IP
- *Elastic IPs* page showing `13.50.166.44` associated with the instance
- Security group inbound rules (22, 80, 443)
- The SSH session (`ssh ... ubuntu@13.50.166.44`) running `sudo bash deploy/setup-server.sh`
- `sudo docker compose ps` showing `db`, `web`, `caddy` running
- The site opened with the IP address in the browser (it redirects to the domain) and with **https://rentcar9.site**
- Hostinger DNS records page (A and CNAME)

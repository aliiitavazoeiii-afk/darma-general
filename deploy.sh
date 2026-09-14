#!/usr/bin/env bash
set -euo pipefail

DOMAIN="samaneh.filmjadiid.ir"
REPO="https://github.com/aliiitavazoeiii-afk/darma-general.git"
BRANCH="dia"
APP_DIR="/opt/dia-gallery"

if [ "$(id -u)" -ne 0 ]; then
  echo "این اسکریپت را با root اجرا کن." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl git openssl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" merge --ff-only "origin/$BRANCH"
else
  git clone --branch "$BRANCH" --single-branch "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

if [ ! -f .env ]; then
  SECRET_KEY=$(openssl rand -hex 32)
  DB_PASSWORD=$(openssl rand -hex 24)
  ADMIN_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-20)
  cat > .env <<ENV
DEBUG=0
SECRET_KEY=$SECRET_KEY
ALLOWED_HOSTS=$DOMAIN
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
DB_NAME=dia_gallery
DB_USER=dia_gallery
DB_PASSWORD=$DB_PASSWORD
DB_HOST=db
DB_PORT=5432
APP_ADMIN_USERNAME=diaadmin
APP_ADMIN_PASSWORD=$ADMIN_PASSWORD
ENV
  chmod 600 .env
  echo
  echo "=============================================="
  echo "Dia Gallery admin username: diaadmin"
  echo "Dia Gallery initial password: $ADMIN_PASSWORD"
  echo "این رمز را الان در جای امن ذخیره کن."
  echo "=============================================="
  echo
fi

# Safety: this stack has its own Compose project and named volumes.
docker compose -p dia-gallery config >/dev/null
docker compose -p dia-gallery up -d --build

echo
echo "=== DIA GALLERY SERVICES ==="
docker compose -p dia-gallery ps
echo
echo "=== DJANGO CHECK ==="
docker compose -p dia-gallery exec -T web python manage.py check
echo
echo "=== DIA DATA SAFETY CHECK ==="
docker compose -p dia-gallery exec -T web python manage.py shell -c 'from dia_core.models import Product,SaleDay,StockBalance,Account; print({"products":Product.objects.count(),"sale_days":SaleDay.objects.count(),"stock_rows":StockBalance.objects.count(),"accounts":Account.objects.count()})'
echo
echo "Site: https://$DOMAIN"
echo "SUCCESS: DIA GALLERY BASE DEPLOYED"

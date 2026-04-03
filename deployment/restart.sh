#!/bin/bash
# restart.sh — Safe restart after git pull.
#
# Rebuilds images, runs migrations, and restarts all services.
# Never touches SSL certs or the nginx config — those are only
# managed by setup-ssl.sh on first deploy.
#
# Usage:
#   ./deployment/restart.sh          # restart with rebuild
#   ./deployment/restart.sh --pull   # git pull first, then restart

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Must be run from project root
cd "$(dirname "$0")/.."

if [ ! -f ".env.production" ]; then
    echo -e "${RED}Error: .env.production not found. Run from project root.${NC}"
    exit 1
fi

set -a; . .env.production; set +a

COMPOSE="docker compose -f docker-compose.production.yml --env-file .env.production"

# ---------------------------------------------------------------
# Optional git pull
# ---------------------------------------------------------------
if [ "$1" = "--pull" ]; then
    echo -e "${YELLOW}Pulling latest code...${NC}"
    git pull origin main
fi

# ---------------------------------------------------------------
# Ensure nginx working config exists and has HTTPS block
# ---------------------------------------------------------------
if [ ! -f "deployment/nginx-production.conf" ]; then
    echo -e "${YELLOW}nginx config missing — restoring from template...${NC}"
    cp deployment/nginx-production.conf.template deployment/nginx-production.conf
fi

if ! grep -q "listen 443 ssl" deployment/nginx-production.conf; then
    echo -e "${RED}ERROR: nginx config is missing the HTTPS server block.${NC}"
    echo ""
    echo "This means SSL was never fully configured, or the config was reset."
    echo "Run the full SSL setup first:"
    echo ""
    echo "  DOMAIN=$DOMAIN ./deployment/setup-ssl.sh"
    echo ""
    echo "Then re-run this script."
    exit 1
fi

# ---------------------------------------------------------------
# Verify SSL certs exist (either standard or -0001 path)
# ---------------------------------------------------------------
CERT_DIR="deployment/certbot/conf/live"
CERT_FOUND=false

for cert_path in "$CERT_DIR/$DOMAIN" "$CERT_DIR/${DOMAIN}-0001"; do
    if [ -f "$cert_path/fullchain.pem" ] || \
       ([ -L "$cert_path" ] && [ -f "$(readlink -f "$cert_path")/fullchain.pem" ]); then
        CERT_FOUND=true
        break
    fi
done

if [ "$CERT_FOUND" = false ]; then
    echo -e "${RED}ERROR: SSL certificate not found for $DOMAIN.${NC}"
    echo ""
    echo "Expected cert at one of:"
    echo "  $CERT_DIR/$DOMAIN/fullchain.pem"
    echo "  $CERT_DIR/${DOMAIN}-0001/fullchain.pem"
    echo ""
    echo "Run SSL setup first:"
    echo "  DOMAIN=$DOMAIN ./deployment/setup-ssl.sh"
    exit 1
fi

echo -e "${GREEN}SSL certificate found.${NC}"

# ---------------------------------------------------------------
# Rebuild images
# ---------------------------------------------------------------
echo -e "${YELLOW}Building Docker images...${NC}"
$COMPOSE build

# ---------------------------------------------------------------
# Restart services
# ---------------------------------------------------------------
echo -e "${YELLOW}Restarting services...${NC}"
$COMPOSE up -d

# ---------------------------------------------------------------
# Run database migrations
# ---------------------------------------------------------------
echo -e "${YELLOW}Waiting for backend to be ready...${NC}"
sleep 8

echo -e "${YELLOW}Running database migrations...${NC}"
$COMPOSE exec -T backend alembic upgrade head || {
    echo -e "${RED}Warning: migrations failed or backend not ready yet.${NC}"
    echo "Check logs: $COMPOSE logs backend"
}

# ---------------------------------------------------------------
# Verify nginx is up
# ---------------------------------------------------------------
echo -e "${YELLOW}Checking nginx...${NC}"
sleep 3

NGINX_STATUS=$($COMPOSE ps nginx --format '{{.Status}}' 2>/dev/null || $COMPOSE ps nginx | tail -1)
if $COMPOSE ps nginx | grep -q "Up"; then
    echo -e "${GREEN}nginx is running.${NC}"
else
    echo -e "${RED}nginx failed to start. Checking logs...${NC}"
    $COMPOSE logs nginx --tail 20
    echo ""
    echo "Common fix: the nginx config references a cert path that doesn't match"
    echo "what's in deployment/certbot/conf/live/. Check cert directory:"
    echo "  ls deployment/certbot/conf/live/"
    echo "And verify deployment/nginx-production.conf ssl_certificate lines match."
    exit 1
fi

# ---------------------------------------------------------------
# Done
# ---------------------------------------------------------------
echo ""
echo -e "${GREEN}Restart complete!${NC}"
echo ""
$COMPOSE ps
echo ""
echo -e "${GREEN}Site: https://$DOMAIN${NC}"

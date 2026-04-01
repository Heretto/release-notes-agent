#!/bin/bash
# Automated SSL setup using Let's Encrypt / Certbot
#
# Reads DOMAIN and SSL_EMAIL from .env.production (or environment).
# Designed to be called from deploy.sh or run standalone.
#
# Usage:
#   ./deployment/setup-ssl.sh                  # uses DOMAIN from .env.production
#   DOMAIN=example.com ./deployment/setup-ssl.sh   # override

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Load .env.production if present and DOMAIN is not already set
if [ -z "$DOMAIN" ] && [ -f ".env.production" ]; then
    set -a
    . .env.production
    set +a
fi

if [ -z "$DOMAIN" ]; then
    echo -e "${RED}Error: DOMAIN is not set.${NC}"
    echo "Set it in .env.production or pass it as an environment variable:"
    echo "  DOMAIN=example.com ./deployment/setup-ssl.sh"
    exit 1
fi

# Validate domain
if ! echo "$DOMAIN" | grep -qP '^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$'; then
    echo -e "${RED}Error: Invalid domain name: $DOMAIN${NC}"
    exit 1
fi

EMAIL="${SSL_EMAIL:-admin@$DOMAIN}"
COMPOSE="docker compose -f docker-compose.production.yml --env-file .env.production"
CERT_PATH="deployment/certbot/conf/live/$DOMAIN"

echo -e "${YELLOW}Setting up SSL for: $DOMAIN${NC}"

# ---------------------------------------------------------------
# Step 1: Check if cert already exists
# ---------------------------------------------------------------
if [ -f "$CERT_PATH/fullchain.pem" ]; then
    echo -e "${GREEN}SSL certificate already exists for $DOMAIN${NC}"
    echo "  To force renewal: rm -rf deployment/certbot/conf/live/$DOMAIN"
    echo "  Then re-run this script."
    exit 0
fi

# ---------------------------------------------------------------
# Step 2: Create directories
# ---------------------------------------------------------------
mkdir -p deployment/certbot/www deployment/certbot/conf

# ---------------------------------------------------------------
# Step 3: Start a temporary HTTP-only nginx for the ACME challenge
# ---------------------------------------------------------------
echo -e "${YELLOW}Starting temporary HTTP-only nginx for certificate validation...${NC}"

# Create a minimal HTTP-only config for the ACME challenge
cat > deployment/nginx-acme-temp.conf << 'ACMEEOF'
server {
    listen 80;
    server_name _;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'SSL setup in progress...\n';
        add_header Content-Type text/plain;
    }
}
ACMEEOF

# Stop nginx if running (ignore errors)
$COMPOSE stop nginx 2>/dev/null || true

# Start a temporary nginx container with the ACME config
docker run -d --rm \
    --name release-notes-acme-nginx \
    -p 80:80 \
    -v "$(pwd)/deployment/nginx-acme-temp.conf:/etc/nginx/conf.d/default.conf:ro" \
    -v "$(pwd)/deployment/certbot/www:/var/www/certbot" \
    nginx:alpine

# Give it a moment to start
sleep 2

# Verify it's running
if ! curl -s -o /dev/null -w "%{http_code}" http://localhost/.well-known/acme-challenge/ | grep -q "403\|404\|200"; then
    echo -e "${RED}Temporary nginx failed to start. Check port 80 is available.${NC}"
    docker stop release-notes-acme-nginx 2>/dev/null || true
    rm -f deployment/nginx-acme-temp.conf
    exit 1
fi

# ---------------------------------------------------------------
# Step 4: Request the certificate
# ---------------------------------------------------------------
echo -e "${YELLOW}Requesting SSL certificate from Let's Encrypt...${NC}"

docker run --rm \
    -v "$(pwd)/deployment/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/deployment/certbot/www:/var/www/certbot" \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive

CERTBOT_EXIT=$?

# ---------------------------------------------------------------
# Step 5: Clean up temporary nginx
# ---------------------------------------------------------------
docker stop release-notes-acme-nginx 2>/dev/null || true
rm -f deployment/nginx-acme-temp.conf

if [ $CERTBOT_EXIT -ne 0 ]; then
    echo -e "${RED}Failed to obtain SSL certificate.${NC}"
    echo "Common issues:"
    echo "  - DNS for $DOMAIN doesn't point to this server"
    echo "  - Port 80 is blocked by a firewall"
    echo "  - Let's Encrypt rate limit reached"
    exit 1
fi

echo -e "${GREEN}SSL certificate obtained successfully!${NC}"

# ---------------------------------------------------------------
# Step 6: Set up auto-renewal cron job
# ---------------------------------------------------------------
CRON_CMD="0 3 * * * cd $(pwd) && docker run --rm -v $(pwd)/deployment/certbot/conf:/etc/letsencrypt -v $(pwd)/deployment/certbot/www:/var/www/certbot certbot/certbot renew --quiet && docker compose -f docker-compose.production.yml --env-file .env.production restart nginx >/dev/null 2>&1"

# Add cron job if not already present
if ! crontab -l 2>/dev/null | grep -q "certbot/certbot renew"; then
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    echo -e "${GREEN}Auto-renewal cron job installed (daily at 3am)${NC}"
else
    echo -e "${YELLOW}Auto-renewal cron job already exists${NC}"
fi

echo -e "${GREEN}SSL setup complete for $DOMAIN${NC}"

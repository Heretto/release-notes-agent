#!/bin/bash
# SSL Setup Script using Let's Encrypt

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if domain is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: No domain specified${NC}"
    echo "Usage: $0 <domain> [www.domain]"
    echo "Example: $0 example.com www.example.com"
    exit 1
fi

DOMAIN=$1
DOMAINS="$@"

# Validate domain names — only allow alphanumeric, hyphens, dots, and wildcards
for d in $DOMAINS; do
    if ! echo "$d" | grep -qP '^(\*\.)?[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$'; then
        echo -e "${RED}Error: Invalid domain name: $d${NC}"
        exit 1
    fi
done

# Check if Certbot is installed
if ! command -v certbot &> /dev/null; then
    echo -e "${YELLOW}Installing Certbot...${NC}"
    sudo apt-get update
    sudo apt-get install -y certbot python3-certbot-nginx
fi

# Check if nginx is running
if ! docker-compose -f docker-compose.production.yml ps | grep -q nginx; then
    echo -e "${RED}Nginx container is not running. Please start it first.${NC}"
    exit 1
fi

# Update nginx configuration with actual domain
echo -e "${YELLOW}Updating nginx configuration...${NC}"
sed -i "s/your-domain\\.com/$DOMAIN/g" deployment/nginx-production.conf

# Get SSL certificate
echo -e "${YELLOW}Obtaining SSL certificate for: $DOMAINS${NC}"

# Create webroot directory
mkdir -p deployment/certbot/www

# Get certificate using webroot method
docker run --rm \
    -v "$(pwd)/deployment/certbot/www:/var/www/certbot" \
    -v "$(pwd)/deployment/certbot/conf:/etc/letsencrypt" \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "${SSL_EMAIL:-admin@$DOMAIN}" \
    --agree-tos \
    --no-eff-email \
    -d "$(echo "$DOMAINS" | tr ' ' ',')"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}SSL certificate obtained successfully!${NC}"
    
    # Restart nginx to load new certificates
    echo -e "${YELLOW}Restarting nginx...${NC}"
    docker-compose -f docker-compose.production.yml restart nginx
    
    echo -e "${GREEN}SSL setup completed!${NC}"
    echo ""
    echo -e "${YELLOW}Certificate auto-renewal:${NC}"
    echo "Add this to your crontab (crontab -e):"
    echo "0 0,12 * * * docker run --rm -v \$(pwd)/deployment/certbot/www:/var/www/certbot -v \$(pwd)/deployment/certbot/conf:/etc/letsencrypt certbot/certbot renew --quiet && docker-compose -f docker-compose.production.yml restart nginx"
    
else
    echo -e "${RED}Failed to obtain SSL certificate${NC}"
    exit 1
fi
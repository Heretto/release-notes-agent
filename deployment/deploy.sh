#!/bin/bash
# Deployment script for Release Notes Agent

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="release-notes-agent"

echo -e "${GREEN}Starting deployment of $PROJECT_NAME${NC}"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command_exists docker; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo -e "${RED}Docker Compose plugin is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo -e "${RED}.env.production not found!${NC}"
    echo "Please copy .env.production.example to .env.production and configure it."
    exit 1
fi

# Load environment variables
set -a
# shellcheck source=/dev/null
. .env.production
set +a

# Validate required environment variables
required_vars=(
    "POSTGRES_PASSWORD"
    "APP_SECRET_KEY"
    "JWT_SECRET_KEY"
    "ENCRYPTION_KEY"
    "DOMAIN"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}Error: $var is not set in .env.production${NC}"
        exit 1
    fi
done

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p deployment/backups
mkdir -p deployment/ssl
mkdir -p deployment/certbot/www
mkdir -p deployment/certbot/conf
mkdir -p backend/logs
mkdir -p backend/uploads

# Pull latest code (optional)
if [ "$1" = "--pull" ]; then
    echo -e "${YELLOW}Pulling latest code from git...${NC}"
    git pull origin main
fi

# Build images
echo -e "${YELLOW}Building Docker images...${NC}"
docker compose -f docker-compose.production.yml --env-file .env.production build

# Run database migrations
echo -e "${YELLOW}Starting database...${NC}"
docker compose -f docker-compose.production.yml --env-file .env.production up -d postgres
sleep 5  # Wait for postgres to be ready

# Check if this is first deployment
if docker compose -f docker-compose.production.yml --env-file .env.production ps | grep -q "release-notes-backend"; then
    echo -e "${YELLOW}Stopping existing services...${NC}"
    docker compose -f docker-compose.production.yml --env-file .env.production stop
fi

# Start services (nginx may fail on first deploy if no cert yet — that's OK)
echo -e "${YELLOW}Starting services...${NC}"
docker compose -f docker-compose.production.yml --env-file .env.production up -d

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 10

# Check service status
echo -e "${YELLOW}Checking service status...${NC}"
docker compose -f docker-compose.production.yml --env-file .env.production ps

# Run database migrations in backend container
echo -e "${YELLOW}Applying database migrations...${NC}"
docker compose -f docker-compose.production.yml --env-file .env.production exec -T backend alembic upgrade head || true

# Provision SSL certificate if not already present
CERT_PATH="deployment/certbot/conf/live/$DOMAIN"
if [ -f "$CERT_PATH/fullchain.pem" ]; then
    echo -e "${GREEN}SSL certificate already exists for $DOMAIN${NC}"
else
    echo -e "${YELLOW}Provisioning SSL certificate for $DOMAIN...${NC}"
    bash deployment/setup-ssl.sh
fi

# Restart nginx to pick up the SSL config
echo -e "${YELLOW}Restarting nginx with SSL...${NC}"
docker compose -f docker-compose.production.yml --env-file .env.production up -d nginx

# Show status
echo -e "${GREEN}Deployment completed!${NC}"
docker compose -f docker-compose.production.yml --env-file .env.production ps

echo -e "${GREEN}Application is running at https://$DOMAIN${NC}"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  View logs: docker compose -f docker-compose.production.yml --env-file .env.production logs -f"
echo "  Stop:      docker compose -f docker-compose.production.yml --env-file .env.production stop"
echo "  Restart:   docker compose -f docker-compose.production.yml --env-file .env.production restart"
echo "  Status:    docker compose -f docker-compose.production.yml --env-file .env.production ps"

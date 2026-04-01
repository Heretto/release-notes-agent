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
DEPLOY_USER="appuser"
DEPLOY_PATH="/home/$DEPLOY_USER/app"

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

if ! command_exists docker-compose; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
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
docker-compose -f docker-compose.production.yml build

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
docker-compose -f docker-compose.production.yml up -d postgres
sleep 5  # Wait for postgres to be ready

# Check if this is first deployment
if docker-compose -f docker-compose.production.yml ps | grep -q "release-notes-backend"; then
    echo -e "${YELLOW}Stopping existing services...${NC}"
    docker-compose -f docker-compose.production.yml stop
fi

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose -f docker-compose.production.yml up -d

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 10

# Check service status
echo -e "${YELLOW}Checking service status...${NC}"
docker-compose -f docker-compose.production.yml ps

# Run database migrations in backend container
echo -e "${YELLOW}Applying database migrations...${NC}"
docker-compose -f docker-compose.production.yml exec -T backend alembic upgrade head || true

# Show logs
echo -e "${GREEN}Deployment completed!${NC}"
echo -e "${YELLOW}Showing recent logs...${NC}"
docker-compose -f docker-compose.production.yml logs --tail=50

echo -e "${GREEN}Application is now running!${NC}"
echo -e "Backend API: http://localhost:8000"
echo -e "Frontend: http://localhost"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  View logs: docker-compose -f docker-compose.production.yml logs -f"
echo "  Stop services: docker-compose -f docker-compose.production.yml stop"
echo "  Restart services: docker-compose -f docker-compose.production.yml restart"
echo "  View status: docker-compose -f docker-compose.production.yml ps"
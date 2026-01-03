#!/bin/bash
# Health Check and Monitoring Script

set -e

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost}"
ALERT_EMAIL="${ADMIN_EMAIL:-}"
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Status tracking
ALL_HEALTHY=true
ALERT_MESSAGE=""

# Function to check service health
check_service() {
    local service_name=$1
    local url=$2
    local expected_code=${3:-200}
    
    echo -n "Checking $service_name... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")
    
    if [ "$response" = "$expected_code" ]; then
        echo -e "${GREEN}OK${NC} (HTTP $response)"
        return 0
    else
        echo -e "${RED}FAILED${NC} (HTTP $response)"
        ALL_HEALTHY=false
        ALERT_MESSAGE="$ALERT_MESSAGE\n$service_name is down (HTTP $response)"
        return 1
    fi
}

# Function to check container status
check_container() {
    local container_name=$1
    
    echo -n "Checking container $container_name... "
    
    if docker ps | grep -q "$container_name"; then
        # Check if container is healthy
        health=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "none")
        
        if [ "$health" = "healthy" ] || [ "$health" = "none" ]; then
            echo -e "${GREEN}Running${NC} (Health: $health)"
            return 0
        else
            echo -e "${YELLOW}Running but unhealthy${NC} (Health: $health)"
            ALL_HEALTHY=false
            ALERT_MESSAGE="$ALERT_MESSAGE\n$container_name is unhealthy"
            return 1
        fi
    else
        echo -e "${RED}Not running${NC}"
        ALL_HEALTHY=false
        ALERT_MESSAGE="$ALERT_MESSAGE\n$container_name is not running"
        return 1
    fi
}

# Function to check disk usage
check_disk_usage() {
    local threshold=${1:-80}
    
    echo -n "Checking disk usage... "
    
    usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ "$usage" -lt "$threshold" ]; then
        echo -e "${GREEN}OK${NC} ($usage% used)"
        return 0
    else
        echo -e "${RED}WARNING${NC} ($usage% used)"
        ALL_HEALTHY=false
        ALERT_MESSAGE="$ALERT_MESSAGE\nDisk usage is high: $usage%"
        return 1
    fi
}

# Function to check memory usage
check_memory() {
    echo -n "Checking memory usage... "
    
    total_mem=$(free -m | awk 'NR==2 {print $2}')
    used_mem=$(free -m | awk 'NR==2 {print $3}')
    usage=$((used_mem * 100 / total_mem))
    
    if [ "$usage" -lt 90 ]; then
        echo -e "${GREEN}OK${NC} ($usage% used)"
        return 0
    else
        echo -e "${RED}WARNING${NC} ($usage% used)"
        ALL_HEALTHY=false
        ALERT_MESSAGE="$ALERT_MESSAGE\nMemory usage is high: $usage%"
        return 1
    fi
}

# Function to check database connection
check_database() {
    echo -n "Checking database connection... "
    
    if docker exec release-notes-db pg_isready -U "${POSTGRES_USER:-produser}" > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        ALL_HEALTHY=false
        ALERT_MESSAGE="$ALERT_MESSAGE\nDatabase connection failed"
        return 1
    fi
}

# Function to send alerts
send_alert() {
    local message=$1
    
    # Send email alert
    if [ ! -z "$ALERT_EMAIL" ] && command -v mail &> /dev/null; then
        echo -e "Health Check Alert\n$message" | mail -s "Health Check Failed - $(hostname)" "$ALERT_EMAIL"
    fi
    
    # Send Slack alert
    if [ ! -z "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚨 Health Check Failed on $(hostname)\n$message\"}" \
            "$SLACK_WEBHOOK" 2>/dev/null
    fi
}

# Main health check
echo -e "${YELLOW}=== Health Check Report ===${NC}"
echo "Time: $(date)"
echo ""

# Check containers
echo -e "${YELLOW}Container Status:${NC}"
check_container "release-notes-db"
check_container "release-notes-redis"
check_container "release-notes-backend"
check_container "release-notes-frontend"
check_container "release-notes-nginx"

echo ""

# Check services
echo -e "${YELLOW}Service Health:${NC}"
check_service "Backend API" "$BACKEND_URL/api/v1/health"
check_service "Frontend" "$FRONTEND_URL"

echo ""

# Check system resources
echo -e "${YELLOW}System Resources:${NC}"
check_disk_usage 80
check_memory
check_database

echo ""

# Check logs for errors (last 100 lines)
echo -e "${YELLOW}Recent Errors:${NC}"
error_count=$(docker-compose -f docker-compose.production.yml logs --tail=100 2>&1 | grep -c "ERROR" || true)
if [ "$error_count" -gt 0 ]; then
    echo -e "${YELLOW}Found $error_count error(s) in recent logs${NC}"
else
    echo -e "${GREEN}No errors in recent logs${NC}"
fi

echo ""

# Summary
if [ "$ALL_HEALTHY" = true ]; then
    echo -e "${GREEN}=== All checks passed ===${NC}"
    exit 0
else
    echo -e "${RED}=== Some checks failed ===${NC}"
    
    # Send alerts if configured
    if [ ! -z "$ALERT_MESSAGE" ]; then
        send_alert "$ALERT_MESSAGE"
    fi
    
    exit 1
fi
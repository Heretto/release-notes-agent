#!/bin/bash
# Database Restore Script for Release Notes Agent

set -e

# Configuration
BACKUP_DIR="/home/appuser/backups"
CONTAINER_NAME="release-notes-db"
DB_NAME="${POSTGRES_DB:-release_notes_production}"
DB_USER="${POSTGRES_USER:-produser}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if backup file is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: No backup file specified${NC}"
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    ls -lht "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    # Try to find in backup directory
    if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
    else
        echo -e "${RED}Error: Backup file not found: $BACKUP_FILE${NC}"
        exit 1
    fi
fi

echo -e "${YELLOW}WARNING: This will replace all data in the database!${NC}"
echo -e "${YELLOW}Backup file: $BACKUP_FILE${NC}"
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${RED}Restore cancelled${NC}"
    exit 1
fi

# Create a current backup before restore
echo -e "${YELLOW}Creating backup of current database...${NC}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
CURRENT_BACKUP="$BACKUP_DIR/before_restore_${TIMESTAMP}.sql.gz"
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" | gzip > "$CURRENT_BACKUP"
echo -e "${GREEN}Current database backed up to: $CURRENT_BACKUP${NC}"

# Stop application containers
echo -e "${YELLOW}Stopping application containers...${NC}"
docker-compose -f docker-compose.production.yml stop backend frontend nginx

# Drop and recreate database
echo -e "${YELLOW}Preparing database for restore...${NC}"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS ${DB_NAME};"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -c "CREATE DATABASE ${DB_NAME};"

# Restore database
echo -e "${YELLOW}Restoring database from backup...${NC}"
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME"
else
    docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE"
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Database restored successfully!${NC}"
    
    # Restart application containers
    echo -e "${YELLOW}Starting application containers...${NC}"
    docker-compose -f docker-compose.production.yml up -d
    
    # Wait for services to be ready
    sleep 10
    
    # Check service status
    docker-compose -f docker-compose.production.yml ps
    
    echo -e "${GREEN}Restore completed successfully!${NC}"
else
    echo -e "${RED}Restore failed!${NC}"
    echo -e "${YELLOW}Attempting to restore previous backup...${NC}"
    
    # Try to restore the backup we just created
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS ${DB_NAME};"
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -c "CREATE DATABASE ${DB_NAME};"
    gunzip -c "$CURRENT_BACKUP" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME"
    
    # Restart services
    docker-compose -f docker-compose.production.yml up -d
    
    exit 1
fi
#!/bin/bash
# Database Backup Script for Release Notes Agent

set -e

# Configuration
BACKUP_DIR="/home/appuser/backups"
CONTAINER_NAME="release-notes-db"
DB_NAME="${POSTGRES_DB:-release_notes_production}"
DB_USER="${POSTGRES_USER:-produser}"
MAX_BACKUPS=30  # Keep last 30 backups

# Validate DB_NAME and DB_USER to prevent injection in shell commands
if [[ ! "$DB_NAME" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "Error: Invalid DB_NAME '${DB_NAME}' — must be alphanumeric/underscores only" >&2
    exit 1
fi
if [[ ! "$DB_USER" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "Error: Invalid DB_USER '${DB_USER}' — must be alphanumeric/underscores only" >&2
    exit 1
fi

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate backup filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/backup_${DB_NAME}_${TIMESTAMP}.sql.gz"

echo -e "${YELLOW}Starting database backup...${NC}"

# Perform backup
if docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" | gzip > "$BACKUP_FILE"; then
    echo -e "${GREEN}Backup completed successfully: $BACKUP_FILE${NC}"
    
    # Get file size
    SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo -e "${GREEN}Backup size: $SIZE${NC}"
    
    # Upload to Google Cloud Storage (optional)
    if command -v gsutil >/dev/null 2>&1; then
        if [ ! -z "$GCS_BUCKET" ]; then
            echo -e "${YELLOW}Uploading to Google Cloud Storage...${NC}"
            if gsutil cp "$BACKUP_FILE" "gs://$GCS_BUCKET/backups/"; then
                echo -e "${GREEN}Backup uploaded to GCS successfully${NC}"
            else
                echo -e "${RED}Failed to upload backup to GCS${NC}"
            fi
        fi
    fi
    
    # Clean up old backups (keep only MAX_BACKUPS most recent)
    echo -e "${YELLOW}Cleaning up old backups...${NC}"
    cd "$BACKUP_DIR"
    ls -t backup_*.sql.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -f
    
    # List remaining backups
    echo -e "${GREEN}Current backups:${NC}"
    ls -lht backup_*.sql.gz 2>/dev/null | head -10 || echo "No backups found"
    
else
    echo -e "${RED}Backup failed!${NC}"
    exit 1
fi

# Send notification (optional - requires mail setup)
if command -v mail >/dev/null 2>&1; then
    if [ ! -z "$ADMIN_EMAIL" ]; then
        echo "Database backup completed: $BACKUP_FILE (Size: $SIZE)" | \
        mail -s "Backup Success: $DB_NAME" "$ADMIN_EMAIL"
    fi
fi

echo -e "${GREEN}Backup process completed!${NC}"
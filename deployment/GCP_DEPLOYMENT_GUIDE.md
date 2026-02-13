# Google Cloud Platform Deployment Guide

This guide will help you deploy the Release Notes Agent to Google Compute Engine.

## Prerequisites

1. Google Cloud account with billing enabled
2. `gcloud` CLI installed locally
3. Domain name (optional, for SSL)
4. Your application secrets and API keys

## Step 1: Set Up Google Cloud Project

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Create a new project (or use existing)
gcloud projects create $PROJECT_ID

# Set the project as default
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
```

## Step 2: Create a Compute Engine Instance

```bash
# Set your zone (e.g., us-central1-a)
export ZONE="us-central1-a"

# Create the VM instance
gcloud compute instances create release-notes-app \
  --zone=$ZONE \
  --machine-type=e2-standard-2 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-standard \
  --tags=http-server,https-server \
  --metadata-from-file startup-script=deployment/startup-script.sh
```

### Recommended Machine Types by Usage:
- **Development/Testing**: e2-micro (1 vCPU, 1GB RAM) - ~$6/month
- **Small Production**: e2-standard-2 (2 vCPU, 8GB RAM) - ~$50/month  
- **Medium Production**: e2-standard-4 (4 vCPU, 16GB RAM) - ~$100/month

## Step 3: Configure Firewall Rules

```bash
# Allow HTTP traffic
gcloud compute firewall-rules create allow-http \
  --allow tcp:80 \
  --source-ranges 0.0.0.0/0 \
  --target-tags http-server

# Allow HTTPS traffic  
gcloud compute firewall-rules create allow-https \
  --allow tcp:443 \
  --source-ranges 0.0.0.0/0 \
  --target-tags https-server

# Allow port 8000 for API (optional, if not using nginx)
gcloud compute firewall-rules create allow-api \
  --allow tcp:8000 \
  --source-ranges 0.0.0.0/0 \
  --target-tags http-server
```

## Step 4: Reserve a Static IP Address

```bash
# Reserve a static external IP
gcloud compute addresses create release-notes-ip \
  --region=${ZONE%-*}

# Get the IP address
gcloud compute addresses describe release-notes-ip \
  --region=${ZONE%-*} \
  --format="get(address)"
```

## Step 5: SSH into the Instance

```bash
gcloud compute ssh release-notes-app --zone=$ZONE
```

## Step 6: Install Docker and Docker Compose

Run these commands on the VM:

```bash
# Update packages
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add current user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

## Step 7: Clone and Configure the Application

```bash
# Install git
sudo apt-get install -y git

# Clone your repository
cd ~
git clone https://github.com/yourusername/release-notes-agent.git
cd release-notes-agent

# Create production environment file
cp .env.example .env.production
```

## Step 8: Configure Environment Variables

Edit the `.env.production` file:

```bash
nano .env.production
```

Set your production values:
```env
# Database
POSTGRES_USER=produser
POSTGRES_PASSWORD=your-secure-password-here
POSTGRES_DB=release_notes_production

# Application
APP_SECRET_KEY=your-production-secret-key
JWT_SECRET_KEY=your-production-jwt-key
ENCRYPTION_KEY=your-production-encryption-key

# API Keys
GOOGLE_AI_API_KEY=your-google-ai-key
JIRA_WEBHOOK_SECRET=your-jira-webhook-secret
HERETTO_BASE_URL=https://api.heretto.com

# CORS (update with your domain)
CORS_ORIGINS=https://your-domain.com

# App URL
APP_URL=https://your-domain.com
```

## Step 9: Deploy with Docker Compose

```bash
# Use the production docker-compose file
docker-compose -f docker-compose.production.yml up -d

# Check if services are running
docker-compose -f docker-compose.production.yml ps

# View logs
docker-compose -f docker-compose.production.yml logs -f
```

## Step 10: Set Up SSL with Let's Encrypt (Optional)

If you have a domain name:

```bash
# Install Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Install nginx
sudo apt-get install -y nginx

# Configure nginx (see nginx.conf in deployment folder)
sudo cp deployment/nginx-ssl.conf /etc/nginx/sites-available/release-notes
sudo ln -s /etc/nginx/sites-available/release-notes /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Get SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Reload nginx
sudo systemctl reload nginx
```

## Step 11: Set Up Database Backups

```bash
# Create backup script
chmod +x deployment/backup.sh

# Add to crontab for daily backups at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * /home/$USER/release-notes-agent/deployment/backup.sh") | crontab -
```

## Step 12: Set Up Monitoring

### Using Google Cloud Monitoring:

```bash
# Install the Cloud Monitoring agent
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install
```

### Using Built-in Health Checks:

```bash
# Create a health check endpoint
gcloud compute health-checks create http release-notes-health \
  --port=80 \
  --request-path=/health

# Create backend service with health check
gcloud compute backend-services create release-notes-backend \
  --protocol=HTTP \
  --health-checks=release-notes-health \
  --global
```

## Step 13: Initial Admin Setup

After deployment, create your first admin user:

```bash
# SSH into the VM
gcloud compute ssh release-notes-app --zone=$ZONE

# Run the admin creation script
cd ~/release-notes-agent
docker exec release-notes-backend python scripts/create_superuser.py \
  --email admin@your-domain.com \
  --password your-admin-password
```

## Maintenance Commands

### View Logs
```bash
docker-compose -f docker-compose.production.yml logs -f backend
docker-compose -f docker-compose.production.yml logs -f frontend
```

### Restart Services
```bash
docker-compose -f docker-compose.production.yml restart
```

### Update Application
```bash
cd ~/release-notes-agent
git pull origin main
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d
```

### Database Backup
```bash
./deployment/backup.sh
```

### Database Restore
```bash
./deployment/restore.sh backup_file.sql
```

## Security Best Practices

1. **Change all default passwords** in production
2. **Use Cloud SQL** instead of containerized PostgreSQL for production
3. **Enable Cloud Armor** for DDoS protection
4. **Use Cloud KMS** for encryption keys
5. **Set up Cloud IAP** for admin access
6. **Enable audit logging**
7. **Regular security updates**: 
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```

## Cost Optimization

1. **Use committed use discounts** for long-term deployments
2. **Set up budget alerts** in GCP Console
3. **Use Cloud Scheduler** to stop/start instances during off-hours
4. **Consider Preemptible VMs** for non-critical environments

## Troubleshooting

### Check Service Status
```bash
docker-compose -f docker-compose.production.yml ps
```

### View Container Logs
```bash
docker logs release-notes-backend
docker logs release-notes-frontend
```

### Database Connection Issues
```bash
docker exec release-notes-backend python -c "from app.models.database import engine; engine.connect()"
```

### Reset Database (WARNING: Deletes all data)
```bash
docker-compose -f docker-compose.production.yml down -v
docker-compose -f docker-compose.production.yml up -d
```

## Support

For issues or questions:
1. Check the logs first: `docker-compose logs`
2. Review the [troubleshooting guide](../README.md#troubleshooting)
3. Open an issue on GitHub
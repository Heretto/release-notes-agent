#!/bin/bash
# Quick Deploy Script for Google Cloud Platform

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Release Notes Agent - GCP Deployer   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get user input
echo -e "${YELLOW}Please provide the following information:${NC}"
echo ""

read -p "Project ID (new or existing): " PROJECT_ID
read -p "Region (e.g., us-central1): " REGION
read -p "Zone (e.g., us-central1-a): " ZONE
read -p "Machine type (e.g., e2-standard-2): " MACHINE_TYPE
read -p "Your domain (optional, press enter to skip): " DOMAIN

# Set defaults
REGION=${REGION:-us-central1}
ZONE=${ZONE:-us-central1-a}
MACHINE_TYPE=${MACHINE_TYPE:-e2-standard-2}

echo ""
echo -e "${YELLOW}Configuration Summary:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Zone: $ZONE"
echo "  Machine Type: $MACHINE_TYPE"
echo "  Domain: ${DOMAIN:-Not configured}"
echo ""

read -p "Continue with deployment? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo -e "${RED}Deployment cancelled${NC}"
    exit 1
fi

# Set project
echo -e "${YELLOW}Setting up GCP project...${NC}"
gcloud config set project $PROJECT_ID

# Enable APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable compute.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com

# Create firewall rules
echo -e "${YELLOW}Creating firewall rules...${NC}"
gcloud compute firewall-rules create allow-http \
    --allow tcp:80 \
    --source-ranges 0.0.0.0/0 \
    --target-tags http-server \
    --quiet 2>/dev/null || true

gcloud compute firewall-rules create allow-https \
    --allow tcp:443 \
    --source-ranges 0.0.0.0/0 \
    --target-tags https-server \
    --quiet 2>/dev/null || true

# Reserve static IP
echo -e "${YELLOW}Reserving static IP address...${NC}"
gcloud compute addresses create release-notes-ip \
    --region=$REGION \
    --quiet 2>/dev/null || true

IP_ADDRESS=$(gcloud compute addresses describe release-notes-ip \
    --region=$REGION \
    --format="get(address)")

echo -e "${GREEN}Static IP: $IP_ADDRESS${NC}"

# Create startup script
cat > /tmp/startup-script.sh << 'EOF'
#!/bin/bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker $USER

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install git
apt-get update
apt-get install -y git

# Setup is complete - user will SSH in to complete deployment
EOF

# Create VM instance
echo -e "${YELLOW}Creating VM instance...${NC}"
gcloud compute instances create release-notes-app \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --tags=http-server,https-server \
    --address=$IP_ADDRESS \
    --metadata-from-file startup-script=/tmp/startup-script.sh

# Wait for instance to be ready
echo -e "${YELLOW}Waiting for instance to be ready...${NC}"
sleep 30

# Create deployment instructions
cat > deployment-instructions.txt << EOF
═══════════════════════════════════════════════════════════════
DEPLOYMENT INSTRUCTIONS FOR RELEASE NOTES AGENT
═══════════════════════════════════════════════════════════════

Your GCP instance has been created successfully!

Instance Details:
  Name: release-notes-app
  IP Address: $IP_ADDRESS
  Zone: $ZONE

Next Steps:

1. SSH into your instance:
   gcloud compute ssh release-notes-app --zone=$ZONE

2. Once connected, run these commands:
   
   # Clone the repository
   git clone https://github.com/yourusername/release-notes-agent.git
   cd release-notes-agent
   
   # Copy and configure environment variables
   cp .env.production.example .env.production
   nano .env.production
   
   # Make scripts executable
   chmod +x deployment/*.sh
   
   # Deploy the application
   ./deployment/deploy.sh

3. If you have a domain ($DOMAIN), set up SSL:
   ./deployment/setup-ssl.sh $DOMAIN

4. Set up automated backups:
   crontab -e
   # Add: 0 2 * * * /home/\$USER/release-notes-agent/deployment/backup.sh

5. Access your application:
   - Without SSL: http://$IP_ADDRESS
   - With SSL: https://$DOMAIN

6. Create your first admin user:
   docker exec release-notes-backend python scripts/create_superuser.py \\
     --email admin@example.com \\
     --password your-secure-password

For monitoring:
  ./deployment/health-check.sh

For logs:
  docker-compose -f docker-compose.production.yml logs -f

═══════════════════════════════════════════════════════════════
EOF

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Deployment preparation completed!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Your instance is ready at IP: ${BLUE}$IP_ADDRESS${NC}"
echo ""
echo -e "${YELLOW}To connect to your instance:${NC}"
echo -e "${BLUE}gcloud compute ssh release-notes-app --zone=$ZONE${NC}"
echo ""
echo -e "${YELLOW}Full instructions have been saved to: ${BLUE}deployment-instructions.txt${NC}"
echo ""

if [ ! -z "$DOMAIN" ]; then
    echo -e "${YELLOW}Don't forget to:${NC}"
    echo "1. Point your domain ($DOMAIN) to IP address: $IP_ADDRESS"
    echo "2. Wait for DNS propagation (5-30 minutes)"
    echo "3. Set up SSL using the setup-ssl.sh script"
    echo ""
fi

echo -e "${GREEN}Good luck with your deployment!${NC}"
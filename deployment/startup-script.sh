#!/bin/bash
# GCP VM Startup Script for Release Notes Agent

set -e

# Update system
apt-get update
apt-get upgrade -y

# Install required packages
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw \
    fail2ban

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Install Docker Compose
DOCKER_COMPOSE_VERSION="2.24.0"
curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Configure firewall
ufw --force enable
ufw allow ssh
ufw allow http
ufw allow https
ufw reload

# Configure fail2ban for SSH protection
cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
EOF

systemctl restart fail2ban

# Set up swap (for smaller instances)
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
fi

# Configure Docker daemon for production
cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF

systemctl restart docker

# Create app user
if ! id -u appuser > /dev/null 2>&1; then
    useradd -m -s /bin/bash appuser
    usermod -aG docker appuser
fi

# Create directory structure
mkdir -p /home/appuser/app
mkdir -p /home/appuser/backups
mkdir -p /home/appuser/logs

# Set permissions
chown -R appuser:appuser /home/appuser

# Install monitoring agent (optional)
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
bash add-google-cloud-ops-agent-repo.sh --also-install

echo "Startup script completed successfully!"
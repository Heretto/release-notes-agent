# AI Release Notes Agent

An intelligent system for automating the creation of DITA-formatted release notes from Jira tickets using Google Gemini AI, with seamless integration to Heretto CCMS.

## Features

- 🎯 **Automated Release Notes Generation** - Extract Jira tickets and generate professional release notes
- 🤖 **AI-Powered Content** - Leverage Google Gemini for intelligent content generation
- 📝 **DITA Format Support** - Generate valid DITA 1.3 XML topics
- 🔄 **Heretto CCMS Integration** - Direct publishing to your documentation platform
- 🔐 **Secure Credential Management** - Encrypted storage for all API credentials
- 🪝 **Webhook Support** - Automated triggers from Jira events
- 📊 **Real-time Monitoring** - Track job progress with WebSocket updates
- 🎨 **Modern Angular UI** - Intuitive interface built with Angular 17 and Material Design

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Angular        │────▶│  FastAPI        │────▶│  PostgreSQL     │
│  Frontend       │     │  Backend        │     │  Database       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ├────▶ Redis (Cache/Queue)
                               ├────▶ Celery (Async Tasks)
                               ├────▶ Jira API
                               ├────▶ Google Gemini AI
                               └────▶ Heretto CCMS
```

## Prerequisites

- Docker and Docker Compose
- Google AI Studio API key (for Gemini)
- Jira instance with API access
- Heretto CCMS account (optional)
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/release-notes-agent.git
   cd release-notes-agent
   ```

2. **Set up environment variables**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your API keys and configuration
   ```

3. **Start the application with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:4200
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

5. **Create your first user**
   - Navigate to http://localhost:4200
   - Click "Create Account"
   - Enter your email and password

## Configuration

### Environment Variables

Key environment variables in `backend/.env`:

```env
# Google AI Studio
GOOGLE_AI_API_KEY=your-gemini-api-key
GOOGLE_AI_MODEL=gemini-1.5-pro

# Security Keys (generate strong random keys for production)
APP_SECRET_KEY=your-app-secret-key
JWT_SECRET_KEY=your-jwt-secret-key
ENCRYPTION_KEY=your-encryption-key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/release_notes_db
REDIS_URL=redis://localhost:6379/0
```

### First-Time Setup

1. **Configure Credentials**
   - Login to the web interface
   - Navigate to Credentials
   - Add your Jira credentials (server URL, email, API token)
   - Add your Heretto credentials (if using)
   - Add your AI provider credentials

2. **Create Instruction Sets**
   - Navigate to Instructions
   - Create custom prompts for different release note styles
   - Set default instruction set for quick job creation

3. **Create Your First Job**
   - Navigate to Jobs
   - Enter a JQL query (e.g., `project = MYPROJ AND fixVersion = '2.0.0'`)
   - Select an instruction set
   - Configure output settings
   - Click "Create Job" to generate release notes

## Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000
```

### Frontend Development

```bash
cd frontend
npm install
ng serve
```

Access the development server at http://localhost:4200

### Running Tests

**Backend Tests:**
```bash
cd backend
pytest tests/
```

**Frontend Tests:**
```bash
cd frontend
ng test
```

## API Documentation

The FastAPI backend provides automatic API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Key endpoints:
- `POST /api/v1/auth/login` - User authentication
- `POST /api/v1/jobs` - Create release notes job
- `GET /api/v1/jobs/{id}` - Get job status
- `POST /api/v1/webhooks/jira` - Jira webhook receiver

## Webhook Configuration

### Setting up Jira Webhooks

1. In Jira, go to System → Webhooks
2. Create a new webhook with URL: `https://your-domain.com/api/v1/webhooks/jira`
3. Select events to trigger (e.g., "Version Released")
4. Copy the webhook secret to your application settings

### Webhook Security

All incoming webhooks are verified using HMAC signatures to ensure authenticity.

## Deployment

### Production Deployment with Docker

1. Copy and configure the production environment file:
   ```bash
   cp .env.production.example .env.production
   # Edit .env.production with your secrets and configuration
   ```

2. Deploy using the provided script:
   ```bash
   ./deployment/deploy.sh
   ```
   This builds Docker images, runs database migrations, and starts all services.

### Deploying to Google Cloud Platform

A full GCP deployment guide is available at [`deployment/GCP_DEPLOYMENT_GUIDE.md`](deployment/GCP_DEPLOYMENT_GUIDE.md).

**Automated setup:**

```bash
./deployment/quick-deploy-gcp.sh
```

This interactively creates a Compute Engine VM, firewall rules, and a static IP.

**Manual setup summary:**

1. Create a Compute Engine VM (e2-standard-2 recommended, ~$50/month)
2. SSH into the VM and clone the repository
3. Configure `.env.production` with your secrets
4. Run `./deployment/deploy.sh`
5. (Optional) Set up SSL with Let's Encrypt:
   ```bash
   ./deployment/setup-ssl.sh your-domain.com
   ```

### Deployment Scripts

The `deployment/` directory includes several operational scripts:

| Script | Purpose |
|--------|---------|
| `deploy.sh` | Build, migrate, and start all production services |
| `quick-deploy-gcp.sh` | Automated GCP VM provisioning |
| `setup-ssl.sh` | SSL/TLS certificate setup with Let's Encrypt |
| `backup.sh` | Database backup (retains 30, optional GCS upload) |
| `health-check.sh` | Container, disk, and memory monitoring with Slack/email alerts |
| `startup-script.sh` | GCP VM bootstrap (Docker, firewall, fail2ban, swap) |

## Troubleshooting

### Common Issues

**Issue: Jobs failing with "No Jira credentials found"**
- Solution: Ensure Jira credentials are configured in the Credentials section

**Issue: DITA validation errors**
- Solution: Check the generated content in job artifacts, ensure templates are valid

**Issue: Cannot connect to database**
- Solution: Verify PostgreSQL is running and DATABASE_URL is correct

**Issue: Celery workers not processing jobs**
- Solution: Check Redis connection and Celery worker logs

### Logs

View logs for debugging:
```bash
# Backend logs
docker-compose logs backend

# Celery worker logs
docker-compose logs celery-worker

# Database logs
docker-compose logs postgres
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Roadmap

- [ ] Support for additional AI providers (OpenAI, Anthropic)
- [ ] Batch processing for multiple versions
- [ ] Custom DITA templates beyond release notes
- [ ] Scheduled job execution
- [ ] Team collaboration features
- [ ] Advanced analytics dashboard
- [ ] Integration with more CCMS platforms

## Acknowledgments

- Built with FastAPI, Angular, and Material Design
- Powered by Google Gemini AI
- DITA validation using lxml
- Async task processing with Celery
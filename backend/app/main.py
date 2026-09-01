from sqlalchemy import desc, func

from hop_core.app_factory import create_hop_app
from hop_core.api.routes.superadmin import register_org_stats_hook

from app.config import get_settings

# Import domain models to register them on Base (must happen before app starts)
import app.models.database  # noqa: F401

from app.api.routes import credentials, instructions, jobs, webhooks, health


# Register domain-specific org stats for superadmin endpoints
def _org_stats(db, org_id):
    from app.models.database import Job
    job_count = db.query(func.count(Job.id)).filter(
        Job.organization_id == org_id,
    ).scalar() or 0

    last_job = db.query(Job.created_at).filter(
        Job.organization_id == org_id,
    ).order_by(desc(Job.created_at)).first()

    return {
        "job_count": job_count,
        "last_activity": last_job[0] if last_job else None,
    }


register_org_stats_hook(_org_stats)


app = create_hop_app(
    settings_factory=get_settings,
    extra_routers=[
        credentials.router,
        instructions.router,
        jobs.router,
        webhooks.router,
    ],
    title="AI Release Notes Agent API",
    description="Automated DITA release notes generation from Jira tickets",
    version="1.0.0",
    include_credentials_router=False,
)

# Health checks are mounted outside api_prefix. create_hop_app puts every extra_router under
# the prefix, and everything under the prefix expects authentication — but a health probe has
# no credentials to offer, so /health and /health/db live at the app root instead.
app.include_router(health.router, tags=["health"])

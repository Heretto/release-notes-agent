"""
Legacy Jira Service - redirects to v3 implementation for backward compatibility.
"""
from app.services.jira_service_v3 import JiraServiceV3

# Use V3 implementation by default
JiraService = JiraServiceV3
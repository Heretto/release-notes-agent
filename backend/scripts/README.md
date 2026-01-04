# Development Utility Scripts

This directory contains utility scripts for managing users, organizations, and passwords in the Release Notes Agent application.

## Available Scripts

### 1. `reset_password.py` (Password & User Management)

Comprehensive utility for managing user passwords and account settings in development.

#### Reset Password

```bash
# Interactive password reset (will prompt for password)
python scripts/reset_password.py user@example.com

# Non-interactive password reset
python scripts/reset_password.py user@example.com --password newpass123

# Reset password for ALL users (batch mode)
python scripts/reset_password.py --reset-all --password defaultpass123
```

#### User Management

```bash
# List all users in the system
python scripts/reset_password.py --list

# Activate/deactivate user accounts
python scripts/reset_password.py user@example.com --activate
python scripts/reset_password.py user@example.com --deactivate

# Grant/remove superuser privileges
python scripts/reset_password.py user@example.com --make-super
python scripts/reset_password.py user@example.com --remove-super
```

#### Features

- **Password Requirements**: Minimum 8 characters
- **Interactive Mode**: Securely prompts for password with confirmation
- **Batch Mode**: Reset multiple users at once
- **User Info**: Shows organization memberships and roles
- **Safety Check**: Warns when running in production environment

### 2. `promote_to_admin.py` (Simple Admin Promotion)

Quick utility to promote users to admin role.

```bash
# Promote user in their only organization
python scripts/promote_to_admin.py user@example.com

# Promote user in specific organization
python scripts/promote_to_admin.py user@example.com --org "Acme Corp"

# List all admins
python scripts/promote_to_admin.py --list-admins

# List admins in specific organization
python scripts/promote_to_admin.py --list-admins --org "Acme Corp"

# List user's organizations
python scripts/promote_to_admin.py --list-user user@example.com
```

### 2. `manage_user_role.py` (Comprehensive Role Management)

Full-featured script for managing user roles and organization membership.

#### Commands

##### Promote User to Admin
```bash
python scripts/manage_user_role.py promote user@example.com --org "Acme Corp"
```

##### Demote Admin to Member
```bash
python scripts/manage_user_role.py demote user@example.com --org "Acme Corp"
```
Note: Cannot demote the last admin in an organization.

##### Add User to Organization
```bash
# Add as member (default)
python scripts/manage_user_role.py add user@example.com --org "Acme Corp"

# Add as admin
python scripts/manage_user_role.py add user@example.com --org "Acme Corp" --role admin
```
Note: User must be registered in the system first.

##### Remove User from Organization
```bash
python scripts/manage_user_role.py remove user@example.com --org "Acme Corp"
```
Note: Cannot remove the last admin. Warns before removing the last member.

##### List Organization Members
```bash
# List members of specific organization
python scripts/manage_user_role.py list --org "Acme Corp"

# List all organizations and their members
python scripts/manage_user_role.py list
```

##### List User's Organizations
```bash
python scripts/manage_user_role.py list --user user@example.com
```

## Prerequisites

Before running these scripts:

1. Ensure the backend environment is set up:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Ensure the database is running:
   ```bash
   docker-compose up -d postgres
   ```

3. Ensure database migrations are applied:
   ```bash
   cd backend
   alembic upgrade head
   ```

## Security Notes

- These scripts require direct database access
- Should only be run by system administrators
- Always verify the user and organization before making changes
- The scripts prevent removing the last admin from an organization
- Changes are immediately committed to the database

## Common Use Cases

### Initial Setup
After deploying the application, promote the first user to admin:
```bash
python scripts/promote_to_admin.py founder@company.com
```

### Adding Team Members
When a new team member joins:
```bash
# They first register through the web UI, then:
python scripts/manage_user_role.py add newmember@company.com --org "Your Company"
```

### Changing Roles
Promote a trusted team member to admin:
```bash
python scripts/manage_user_role.py promote teammember@company.com --org "Your Company"
```

### Auditing
Check who has admin access:
```bash
python scripts/manage_user_role.py list --org "Your Company"
```

## When to Use Each Script

### Use `reset_password.py` when:
- You need to reset a forgotten password in development
- You want to activate/deactivate user accounts
- You need to grant/revoke superuser privileges
- You want to see all registered users quickly
- You need to batch reset passwords for testing

### Use `promote_to_admin.py` when:
- You specifically need to manage organization admin roles
- You want a quick way to promote users without other options
- You need to list organization admins specifically

### Use `manage_user_role.py` when:
- You need comprehensive organization membership management
- You want to add/remove users from organizations
- You need to change roles within organizations
- You want to manage multiple organizations

## Troubleshooting

### "User not found" Error
- Ensure the user has registered through the web application first
- Check the email address is correct (case-sensitive)
- Use `python scripts/reset_password.py --list` to see all users

### "Organization not found" Error
- Verify the exact organization name (case-sensitive)
- List all organizations: `python scripts/manage_user_role.py list`

### Database Connection Errors
- Check PostgreSQL is running: `docker-compose ps`
- Verify DATABASE_URL in backend/.env file
- Ensure you're running from the backend directory

### Permission Errors
- Cannot remove/demote the last admin (by design)
- Cannot add users who haven't registered yet

## Security Notes

⚠️ **IMPORTANT**: These scripts are for DEVELOPMENT ONLY
- They require direct database access
- They bypass normal authentication
- Never use in production environments
- Always use the application's UI for production user management
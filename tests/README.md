# Release Notes Agent - Test Suite

This directory contains all tests for the Release Notes Agent application.

## Directory Structure

```
tests/
├── api/                    # API endpoint tests
│   ├── test_credentials.py # Credentials CRUD operations
│   └── test_delete_artifacts.py # Artifact deletion functionality
├── integration/            # Integration tests
│   ├── test_jira_v3.py    # JIRA API v3 integration
│   └── test_jira_final.py # Comprehensive JIRA tests
├── ui/                     # UI test guides (manual)
│   ├── test_ui_delete.md  # Artifact deletion UI testing
│   └── test_max_tickets.md # Max tickets feature testing
├── utilities/              # Test utilities
│   └── reset_admin_password.py # Reset admin password
├── config.py              # Central test configuration
└── run_tests.py           # Main test runner

```

## Prerequisites

1. Ensure Docker services are running:
   ```bash
   docker-compose up -d
   ```

2. Install Python dependencies (if running tests locally):
   ```bash
   pip install requests sqlalchemy psycopg2-binary
   ```

## Running Tests

### Run All Tests
```bash
# From project root
python tests/run_tests.py

# Or make executable and run directly
chmod +x tests/run_tests.py
./tests/run_tests.py
```

### Run Specific Test
```bash
# Run a specific test file
python tests/run_tests.py --test api/test_credentials.py

# Or run directly
python tests/api/test_credentials.py
```

### List Available Tests
```bash
python tests/run_tests.py --list
```

## Test Categories

### API Tests
- **test_credentials.py**: Tests CRUD operations for credentials
- **test_delete_artifacts.py**: Tests artifact deletion endpoints

### Integration Tests
- **test_jira_v3.py**: Verifies JIRA API v3 integration
- **test_jira_final.py**: Comprehensive JIRA workflow tests

### UI Tests (Manual)
- **test_ui_delete.md**: Guide for testing artifact deletion in UI
- **test_max_tickets.md**: Guide for testing max tickets feature

## Configuration

All tests use centralized configuration from `config.py`:

```python
API_BASE_URL = "http://localhost:8000/api/v1"
TEST_EMAIL = "admin@example.com"
TEST_PASSWORD = "admin"
```

## Utilities

### Reset Admin Password
If you need to reset the admin password for testing:

```bash
python tests/utilities/reset_admin_password.py
```

This will reset the admin account password to `admin`.

## Writing New Tests

1. Create test file in appropriate directory (api/, integration/, etc.)
2. Import config for shared settings:
   ```python
   import sys
   import os
   sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
   from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD
   ```
3. Follow naming convention: `test_<feature>.py`
4. Add to test runner if needed

## Troubleshooting

### Services Not Running
If tests fail with connection errors:
```bash
docker-compose ps  # Check service status
docker-compose up -d  # Start services
```

### Authentication Failures
Reset admin password:
```bash
python tests/utilities/reset_admin_password.py
```

### Database Issues
Check database logs:
```bash
docker logs release-notes-db
```

## CI/CD Integration

To run tests in CI/CD pipeline:

```yaml
# Example GitHub Actions
- name: Start services
  run: docker-compose up -d
  
- name: Wait for services
  run: sleep 10
  
- name: Run tests
  run: python tests/run_tests.py
```
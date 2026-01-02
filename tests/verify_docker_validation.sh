#!/bin/bash

echo "============================================================"
echo "DOCKER VALIDATION VERIFICATION SCRIPT"
echo "============================================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Check if container is running
if docker ps | grep -q release-notes-backend; then
    echo "✅ Backend container is running"
else
    echo "❌ Backend container is not running"
    echo "   Run: docker-compose up -d"
    exit 1
fi

echo ""
echo "Checking Python packages in container..."
echo "----------------------------------------"

# Check if lxml is installed
docker exec release-notes-backend pip list | grep -E "lxml|xml" || echo "❌ lxml not found"

echo ""
echo "Checking imported modules in orchestrator..."
echo "----------------------------------------"

# Check the actual imports in the running container
docker exec release-notes-backend python3 -c "
import sys
sys.path.append('/app')

try:
    from app.services.dita_validator_v2 import DITAValidatorV2
    print('✅ DITAValidatorV2 imported successfully')
except ImportError as e:
    print(f'❌ Failed to import DITAValidatorV2: {e}')

try:
    from app.services.dita_correction_service import DITACorrectionService
    print('✅ DITACorrectionService imported successfully')
except ImportError as e:
    print(f'❌ Failed to import DITACorrectionService: {e}')

try:
    from lxml import etree
    print('✅ lxml imported successfully')
except ImportError as e:
    print(f'❌ Failed to import lxml: {e}')

# Try to instantiate validator
try:
    validator = DITAValidatorV2()
    print('✅ DITAValidatorV2 instantiated successfully')
except Exception as e:
    print(f'❌ Failed to instantiate DITAValidatorV2: {e}')

# Test validation
test_content = '''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE topic PUBLIC \"-//OASIS//DTD DITA Topic//EN\" \"topic.dtd\">
<topic id=\"test\">
  <title>Test</title>
  <body>
    <section>
      <title>Section</title>
      <p>Content</p>
    </section>
  </body>
</topic>'''

try:
    valid, errors = validator.validate_structure(test_content)
    if valid:
        print('✅ Validation test passed')
    else:
        print(f'❌ Validation test failed: {errors}')
except Exception as e:
    print(f'❌ Validation test error: {e}')
"

echo ""
echo "Checking job_orchestrator.py in container..."
echo "----------------------------------------"

docker exec release-notes-backend bash -c "
if grep -q 'from app.services.dita_validator_v2 import DITAValidatorV2' /app/app/services/job_orchestrator.py; then
    echo '✅ job_orchestrator.py imports DITAValidatorV2'
else
    echo '❌ job_orchestrator.py does not import DITAValidatorV2'
fi

if grep -q 'from app.services.dita_correction_service import DITACorrectionService' /app/app/services/job_orchestrator.py; then
    echo '✅ job_orchestrator.py imports DITACorrectionService'
else
    echo '❌ job_orchestrator.py does not import DITACorrectionService'
fi

if grep -q 'validate_and_correct_with_ai' /app/app/services/job_orchestrator.py; then
    echo '✅ job_orchestrator.py uses validate_and_correct_with_ai'
else
    echo '❌ job_orchestrator.py does not use validate_and_correct_with_ai'
fi
"

echo ""
echo "============================================================"
echo "VALIDATION SYSTEM STATUS"
echo "============================================================"

# Run a quick validation test in the container
docker exec release-notes-backend python3 -c "
import sys
sys.path.append('/app')
from app.services.dita_validator_v2 import DITAValidatorV2

validator = DITAValidatorV2()

# Test with invalid content (Markdown)
markdown_content = '''# Release Notes

## Features
- Feature 1'''

valid, errors = validator.validate_structure(markdown_content)

if not valid:
    print('✅ VALIDATION WORKING: Correctly detected invalid Markdown content')
    if errors:
        print(f'   Found {len(errors)} error(s)')
else:
    print('❌ VALIDATION NOT WORKING: Failed to detect invalid Markdown')

# Test with valid DITA
valid_dita = '''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE topic PUBLIC \"-//OASIS//DTD DITA Topic//EN\" \"topic.dtd\">
<topic id=\"test\">
  <title>Test</title>
  <body><p>Content</p></body>
</topic>'''

valid, errors = validator.validate_structure(valid_dita)

if valid:
    print('✅ VALIDATION WORKING: Correctly validated valid DITA')
else:
    print(f'❌ VALIDATION NOT WORKING: Incorrectly rejected valid DITA: {errors}')
" 2>/dev/null || echo "❌ Validation test failed to run"

echo ""
echo "============================================================"
echo "SUMMARY"
echo "============================================================"
echo ""
echo "The enhanced DITA validation system has been integrated into"
echo "the production job orchestrator. The system will now:"
echo ""
echo "1. Validate all generated DITA content"
echo "2. Automatically fix common XML/DITA issues"
echo "3. Use AI to correct structural errors while preserving text"
echo "4. Save validation logs and error reports as job artifacts"
echo ""
echo "To test with a real job:"
echo "1. Create a new job through the UI"
echo "2. Check the job artifacts for validation logs"
echo "3. Any DITA errors will be caught and correction attempted"
echo ""
echo "The validation errors in job 54773e19-5bc9-45ad-bd6a-ac5287c9031a"
echo "should now be prevented in new jobs."
echo "============================================================"
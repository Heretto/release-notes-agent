#!/bin/bash

echo "============================================================"
echo "DOCKER DTD VALIDATION VERIFICATION"
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
echo "Checking DTD files in container..."
echo "----------------------------------------"

# Check if DTD directory exists in container
docker exec release-notes-backend bash -c "
if [ -d '/app/app/dtds/org.oasis-open.dita.v1_3' ]; then
    echo '✅ DTD directory exists in container'
    echo '   Location: /app/app/dtds/org.oasis-open.dita.v1_3'
    
    # Check for key DTD files
    echo ''
    echo 'Checking key DTD files:'
    
    dtd_files=(
        '/app/app/dtds/org.oasis-open.dita.v1_3/dtd/technicalContent/dtd/topic.dtd'
        '/app/app/dtds/org.oasis-open.dita.v1_3/dtd/technicalContent/dtd/concept.dtd'
        '/app/app/dtds/org.oasis-open.dita.v1_3/dtd/technicalContent/dtd/task.dtd'
        '/app/app/dtds/org.oasis-open.dita.v1_3/dtd/technicalContent/dtd/reference.dtd'
    )
    
    for dtd_file in \"\${dtd_files[@]}\"; do
        if [ -f \"\$dtd_file\" ]; then
            echo \"  ✓ \$(basename \$dtd_file)\"
        else
            echo \"  ✗ \$(basename \$dtd_file) - NOT FOUND\"
        fi
    done
else
    echo '❌ DTD directory not found in container'
    echo '   Expected at: /app/app/dtds/org.oasis-open.dita.v1_3'
fi
"

echo ""
echo "Testing DITA validation in container..."
echo "----------------------------------------"

# Test validation with DTDs in container
docker exec release-notes-backend python3 -c "
import sys
import os
sys.path.append('/app')

from app.services.dita_validator_v2 import DITAValidatorV2

# Initialize validator
validator = DITAValidatorV2()

print(f'DTD Directory configured: {validator.dtd_dir}')
print(f'Directory exists: {os.path.exists(validator.dtd_dir)}')

# Test with valid DITA
test_content = '''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE topic PUBLIC \"-//OASIS//DTD DITA Topic//EN\" \"topic.dtd\">
<topic id=\"test\">
  <title>Test Topic</title>
  <body>
    <section>
      <title>Test Section</title>
      <p>This is a test.</p>
    </section>
  </body>
</topic>'''

valid, errors = validator.validate_structure(test_content)

if valid:
    print('✅ DITA validation working in container')
else:
    print(f'❌ Validation failed: {errors}')

# Test with invalid DITA
invalid_content = '''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<topic id=\"test\">
  <body><p>Missing title</p></body>
</topic>'''

valid, errors = validator.validate_structure(invalid_content)

if not valid and errors:
    print('✅ Invalid DITA correctly detected')
    print(f'   Error: {errors[0]}')
else:
    print('❌ Failed to detect invalid DITA')

# Check if DTDs are available
if validator._dtd_available('topic'):
    print('✅ DTD files are accessible')
else:
    print('⚠️  DTD files not accessible, using structural validation')
"

echo ""
echo "============================================================"
echo "SUMMARY"
echo "============================================================"
echo ""
echo "The DITA validator is configured to:"
echo "1. Check for DITA 1.3 DTD files in /app/app/dtds/org.oasis-open.dita.v1_3"
echo "2. Use comprehensive structural validation based on DITA 1.3 rules"
echo "3. Support multiple topic types (topic, concept, task, reference, etc.)"
echo "4. Auto-detect topic type from root element"
echo "5. Validate element nesting and required attributes"
echo ""
echo "Note: Due to the complexity of DITA 1.3 DTDs with extensive entity"
echo "references, the validator uses enhanced structural validation that"
echo "enforces DITA 1.3 requirements without full DTD parsing overhead."
echo "============================================================"
# DITA Validation and AI Correction

## Overview

The Release Notes Agent now includes comprehensive DITA 1.3 validation with AI-driven error correction. This ensures that all generated DITA content is valid and well-formed.

## Features

### 1. DITA Structure Validation
- Validates against DITA 1.3 standards
- Checks for required elements (topic, title, body)
- Validates ID format and uniqueness
- Ensures proper element nesting
- Detects common authoring issues

### 2. AI-Driven Error Correction
- Automatically corrects validation errors
- Preserves original text content exactly
- Makes minimal structural changes
- Multiple correction attempts with fallback strategies

### 3. Validation Process

The validation process follows these steps:

1. **Initial Generation**: AI generates DITA content based on JIRA tickets
2. **Automatic Fixes**: Common issues are automatically corrected
   - XML declaration and DOCTYPE addition
   - Special character escaping
   - ID format fixing
3. **Structure Validation**: Content is validated against DITA rules
4. **AI Correction**: If validation fails, AI corrects structural issues
   - Preserves all text content
   - Only fixes XML/DITA structure
   - Makes minimal changes
5. **Final Validation**: Corrected content is re-validated
6. **Logging**: All validation attempts are logged for debugging

## Implementation

### Key Components

#### DITAValidatorV2 (`dita_validator_v2.py`)
- Uses lxml for XML parsing and validation
- Performs structural validation
- Extracts detailed error information
- Provides automatic fixes for common issues

#### DITACorrectionService (`dita_correction_service.py`)
- Manages AI-driven correction process
- Generates targeted prompts for error correction
- Ensures text preservation during corrections
- Handles multiple correction attempts

#### Enhanced Job Orchestrator
- Integrates validation into the generation pipeline
- Creates validation artifacts for debugging
- Handles validation failures gracefully

### Validation Rules

The validator checks for:

1. **Required Elements**
   - Root element must be `topic`, `concept`, `task`, or `reference`
   - Must have `id` attribute on root element
   - Must contain `<title>` element
   - Must contain `<body>` element (or `<taskbody>` for tasks)

2. **ID Format**
   - Must start with a letter
   - Can only contain letters, numbers, underscores, and hyphens
   - Must be unique within the document

3. **Element Structure**
   - Sections must have titles
   - Lists must contain at least one list item
   - Structural elements cannot contain direct text
   - Text must be in appropriate containers (p, li, note, etc.)

4. **Special Characters**
   - Ampersands must be escaped as `&amp;`
   - Less-than signs must be escaped as `&lt;`
   - Greater-than signs must be escaped as `&gt;`

## AI Correction Prompts

The AI correction system uses specialized prompts that:

1. **Preserve Content**: Explicitly instructs AI not to change any text
2. **Focus on Structure**: Only fixes XML/DITA structural issues
3. **Provide Context**: Includes specific error messages and line numbers
4. **Give Examples**: Shows common fixes needed

Example correction prompt structure:
```
You are a DITA XML validation expert. Fix validation errors while STRICTLY preserving all text content.

CRITICAL RULES:
1. DO NOT change any text content
2. ONLY fix XML/DITA structural issues
3. Make minimal changes needed

Current validation errors:
- Missing required <title> element
- Section contains direct text (use <p> tags)
- Invalid ID format

[DITA content to fix]
```

## Testing

### Unit Tests (`tests/unit/test_dita_validation.py`)

Comprehensive test suite covering:
- Valid DITA validation
- Missing element detection
- ID format validation
- Text placement rules
- Special character handling
- Auto-fix functionality
- Real-world release notes examples

### Running Tests
```bash
# Run DITA validation tests
python3 tests/unit/test_dita_validation.py

# Run all tests including DITA validation
./run_tests.sh
```

## Artifacts and Debugging

The system creates several artifacts for debugging:

1. **validation-log-{job_id}.log**: Complete validation process log
2. **validation-error-{job_id}.log**: Detailed error report if validation fails
3. **correction-note-{job_id}.log**: Summary of corrections made
4. **ai-response-{job_id}.log**: Raw AI response for debugging

## Configuration

### Environment Variables
```bash
# No specific configuration needed for validation
# Uses existing AI service configuration
```

### Dependencies
- lxml (Python XML library)
- System packages: libxml2-dev, libxslt-dev

## Best Practices

1. **Instruction Sets**: Ensure system prompts specify DITA XML output
2. **AI Models**: Lower temperature (0.1-0.3) for consistent corrections
3. **Validation Cycles**: Default 2 cycles, can be adjusted if needed
4. **Error Handling**: Validation failures don't stop job completion

## Future Enhancements

Potential improvements:
1. Download and cache DITA 1.3 DTDs for full DTD validation
2. Support for specialized DITA types (concept, task, reference)
3. Schematron rules for business-specific validation
4. Content reuse and conref validation
5. Link and cross-reference validation

## Troubleshooting

### Common Issues

1. **AI Returns Markdown Instead of DITA**
   - Solution: System detects and converts to basic DITA structure
   - Check instruction set prompts

2. **Validation Loops**
   - Solution: Limited to 2 correction cycles with fallback
   - Review AI model temperature settings

3. **Text Content Changed**
   - Solution: Correction prompts strictly preserve text
   - Check correction logs for details

### Debug Mode

To enable detailed validation logging:
```python
# In job_orchestrator.py
logger.setLevel(logging.DEBUG)
```

## API Usage

The validation system is automatically integrated into the job processing pipeline. No additional API calls are needed.

For manual validation:
```python
from app.services.dita_validator_v2 import DITAValidatorV2

validator = DITAValidatorV2()
valid, errors = validator.validate_structure(dita_content)

if not valid:
    # Apply automatic fixes
    fixed_content = validator.auto_fix_common_issues(dita_content)
```
#!/usr/bin/env python3
"""
End-to-end test for DITA validation in production environment.
Tests that the enhanced DITA validation catches and corrects errors.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append('/Users/patrickbosek/dev/release-notes-agent/backend')

import asyncio
import json
from datetime import datetime
from uuid import uuid4

# Import the production components
from app.services.dita_validator_v2 import DITAValidatorV2
from app.services.dita_correction_service import DITACorrectionService
from app.services.ai_service import AIServiceFactory, GenerationRequest

def test_validation_catches_errors():
    """Test that the validator catches common DITA errors."""
    
    print("="*60)
    print("TEST 1: DITA Validation Error Detection")
    print("="*60)
    
    validator = DITAValidatorV2()
    
    # Test cases with known errors
    test_cases = [
        {
            "name": "Missing XML declaration",
            "content": """<topic id="test">
  <title>Test</title>
  <body><p>Content</p></body>
</topic>""",
            "expected_errors": ["XML declaration"]
        },
        {
            "name": "Invalid ID format",
            "content": """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="123-invalid">
  <title>Test</title>
  <body><p>Content</p></body>
</topic>""",
            "expected_errors": ["Invalid ID format"]
        },
        {
            "name": "Missing title in section",
            "content": """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="test">
  <title>Test</title>
  <body>
    <section>
      <p>Content without title</p>
    </section>
  </body>
</topic>""",
            "expected_errors": ["<section> missing required <title>"]
        },
        {
            "name": "Direct text in structural element",
            "content": """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="test">
  <title>Test</title>
  <body>
    <section>
      <title>Section</title>
      This text should be in a p tag
    </section>
  </body>
</topic>""",
            "expected_errors": ["should not contain direct text"]
        },
        {
            "name": "Markdown instead of DITA",
            "content": """# Release Notes

## Features
- Feature 1
- Feature 2

## Bug Fixes
- Bug 1
- Bug 2""",
            "expected_errors": ["XML Syntax Error"]
        }
    ]
    
    results = []
    for test_case in test_cases:
        print(f"\nTesting: {test_case['name']}")
        print("-" * 40)
        
        valid, errors = validator.validate_structure(test_case["content"])
        
        if not valid and errors:
            print(f"✓ Correctly detected {len(errors)} error(s):")
            for error in errors:
                print(f"  - {error}")
            
            # Check if expected errors were found
            found_expected = False
            for expected in test_case["expected_errors"]:
                if any(expected in error for error in errors):
                    found_expected = True
                    break
            
            if found_expected:
                print(f"✓ Found expected error type")
                results.append(True)
            else:
                print(f"✗ Did not find expected error: {test_case['expected_errors']}")
                results.append(False)
        elif valid:
            print(f"✗ Failed to detect errors in invalid content")
            results.append(False)
        else:
            print(f"✗ Validation failed but no errors returned")
            results.append(False)
    
    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    return all(results)

def test_auto_fix_functionality():
    """Test automatic fixing of common issues."""
    
    print("\n" + "="*60)
    print("TEST 2: Automatic Fix Functionality")
    print("="*60)
    
    validator = DITAValidatorV2()
    
    test_cases = [
        {
            "name": "Add missing XML declaration and DOCTYPE",
            "input": """<topic id="test">
  <title>Test</title>
  <body><p>Content</p></body>
</topic>""",
            "should_fix": True
        },
        {
            "name": "Fix invalid ID starting with number",
            "input": """<?xml version="1.0" encoding="UTF-8"?>
<topic id="123test">
  <title>Test</title>
  <body><p>Content</p></body>
</topic>""",
            "should_fix": True
        },
        {
            "name": "Escape unescaped ampersands",
            "input": """<?xml version="1.0" encoding="UTF-8"?>
<topic id="test">
  <title>Test & Title</title>
  <body><p>Content & more</p></body>
</topic>""",
            "should_fix": True
        }
    ]
    
    results = []
    for test_case in test_cases:
        print(f"\nTesting: {test_case['name']}")
        print("-" * 40)
        
        # Check initial validity
        valid_before, errors_before = validator.validate_structure(test_case["input"])
        print(f"Before: Valid={valid_before}, Errors={len(errors_before) if errors_before else 0}")
        
        # Apply auto-fix
        fixed = validator.auto_fix_common_issues(test_case["input"])
        
        # Check validity after fix
        valid_after, errors_after = validator.validate_structure(fixed)
        print(f"After: Valid={valid_after}, Errors={len(errors_after) if errors_after else 0}")
        
        if test_case["should_fix"]:
            if valid_after or (errors_after and errors_before and len(errors_after) < len(errors_before)):
                print("✓ Auto-fix improved validation")
                results.append(True)
            else:
                print("✗ Auto-fix did not improve validation")
                results.append(False)
        else:
            results.append(True)  # Not expected to fix
    
    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    return all(results)

async def test_ai_correction_mock():
    """Test AI correction service with a mock AI response."""
    
    print("\n" + "="*60)
    print("TEST 3: AI Correction Service (Mock)")
    print("="*60)
    
    validator = DITAValidatorV2()
    
    # Create a mock AI service
    class MockAIService:
        async def generate(self, request):
            # Return a corrected version
            class MockResponse:
                content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="release_notes">
  <title>Release Notes</title>
  <body>
    <section>
      <title>Features</title>
      <ul>
        <li>Feature 1</li>
        <li>Feature 2</li>
      </ul>
    </section>
    <section>
      <title>Bug Fixes</title>
      <ul>
        <li>Bug 1</li>
        <li>Bug 2</li>
      </ul>
    </section>
  </body>
</topic>"""
            return MockResponse()
    
    mock_ai = MockAIService()
    correction_service = DITACorrectionService(mock_ai, validator)
    
    # Test with invalid content
    invalid_content = """# Release Notes

## Features
- Feature 1
- Feature 2

## Bug Fixes
- Bug 1
- Bug 2"""
    
    print("Testing AI correction with invalid Markdown content...")
    print("-" * 40)
    
    corrected, is_valid, log = await correction_service.validate_and_correct_with_ai(
        content=invalid_content,
        max_cycles=1
    )
    
    print("Correction Log:")
    for entry in log:
        print(f"  {entry}")
    
    print(f"\nFinal Status: {'✓ Valid' if is_valid else '✗ Invalid'}")
    
    if is_valid:
        print("✓ AI correction successfully fixed content")
        return True
    else:
        print("✗ AI correction failed to produce valid content")
        return False

def test_orchestrator_integration():
    """Test that the orchestrator properly uses the new validation."""
    
    print("\n" + "="*60)
    print("TEST 4: Orchestrator Integration Check")
    print("="*60)
    
    # Check that job_orchestrator.py imports the correct modules
    orchestrator_path = "/Users/patrickbosek/dev/release-notes-agent/backend/app/services/job_orchestrator.py"
    
    if os.path.exists(orchestrator_path):
        with open(orchestrator_path, 'r') as f:
            content = f.read()
        
        checks = {
            "DITAValidatorV2 imported": "from app.services.dita_validator_v2 import DITAValidatorV2" in content,
            "DITACorrectionService imported": "from app.services.dita_correction_service import DITACorrectionService" in content,
            "DITAValidatorV2 instantiated": "DITAValidatorV2()" in content,
            "DITACorrectionService used": "DITACorrectionService(" in content,
            "validate_and_correct_with_ai called": "validate_and_correct_with_ai(" in content
        }
        
        all_passed = True
        for check_name, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"{status} {check_name}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print("\n✓ Orchestrator properly integrated with enhanced validation")
            return True
        else:
            print("\n✗ Orchestrator integration incomplete")
            return False
    else:
        print("✗ Orchestrator file not found")
        return False

async def main():
    """Run all integration tests."""
    
    print("="*60)
    print("DITA VALIDATION END-TO-END TEST SUITE")
    print("="*60)
    print(f"Started: {datetime.now().isoformat()}")
    
    results = []
    
    # Test 1: Error detection
    results.append(("Error Detection", test_validation_catches_errors()))
    
    # Test 2: Auto-fix
    results.append(("Auto-Fix", test_auto_fix_functionality()))
    
    # Test 3: AI Correction
    ai_result = await test_ai_correction_mock()
    results.append(("AI Correction", ai_result))
    
    # Test 4: Orchestrator Integration
    results.append(("Orchestrator Integration", test_orchestrator_integration()))
    
    # Summary
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED - DITA VALIDATION IS WORKING")
        print("\nThe enhanced DITA validation system is properly integrated:")
        print("• DITAValidatorV2 catches structural errors")
        print("• Auto-fix corrects common issues")
        print("• DITACorrectionService provides AI-driven fixes")
        print("• Job orchestrator uses the enhanced validation")
        print("\nValidation errors reported in job 54773e19-5bc9-45ad-bd6a-ac5287c9031a")
        print("should now be caught and corrected automatically.")
    else:
        print("⚠️ SOME TESTS FAILED - REVIEW REQUIRED")
        print("\nTroubleshooting:")
        print("1. Check Docker logs: docker logs release-notes-backend")
        print("2. Verify lxml is installed in container")
        print("3. Run a new job to test validation")
    
    print("="*60)
    print(f"Completed: {datetime.now().isoformat()}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
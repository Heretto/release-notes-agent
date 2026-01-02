#!/usr/bin/env python3
"""
Manual test script to validate DITA content for a specific job.
Can be used to check and fix DITA validation issues.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append('/Users/patrickbosek/dev/release-notes-agent/backend')

from app.services.dita_validator_v2 import DITAValidatorV2
import argparse

def validate_job_dita(job_id=None, content=None, fix=False):
    """Validate DITA content for a job."""
    
    print("="*60)
    print("DITA CONTENT VALIDATOR")
    print("="*60)
    
    validator = DITAValidatorV2()
    
    if content:
        print(f"\nValidating provided DITA content...")
    elif job_id:
        print(f"\nJob ID: {job_id}")
        print("Note: To validate job artifacts, retrieve them through the API")
        # In production, would fetch from database
        return
    else:
        # Test with sample content
        print("\nUsing sample DITA content for testing...")
        content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="release-notes-test">
  <title>Test Release Notes</title>
  <body>
    <section>
      <title>Features</title>
      <ul>
        <li>Feature 1</li>
        <li>Feature 2</li>
      </ul>
    </section>
    <section>
      Missing title here causes error
      <p>Content</p>
    </section>
  </body>
</topic>"""
    
    print("\nContent preview (first 500 chars):")
    print("-" * 40)
    print(content[:500])
    print("-" * 40)
    
    # Validate structure
    print("\n1. Validating DITA structure...")
    valid, errors = validator.validate_structure(content)
    
    if valid:
        print("   ✓ DITA content is valid!")
        return True
    else:
        print(f"   ✗ Validation failed with {len(errors) if errors else 0} error(s):")
        if errors:
            for i, error in enumerate(errors, 1):
                print(f"      {i}. {error}")
    
    if fix and not valid:
        print("\n2. Attempting automatic fixes...")
        fixed_content = validator.auto_fix_common_issues(content)
        
        # Re-validate
        valid_after, errors_after = validator.validate_structure(fixed_content)
        
        if valid_after:
            print("   ✓ Content fixed successfully!")
            print("\nFixed content preview (first 500 chars):")
            print("-" * 40)
            print(fixed_content[:500])
            print("-" * 40)
            return True
        else:
            print(f"   ⚠ Still has {len(errors_after) if errors_after else 0} error(s) after fixes:")
            if errors_after:
                for i, error in enumerate(errors_after, 1):
                    print(f"      {i}. {error}")
    
    # Extract detailed errors
    print("\n3. Detailed error analysis:")
    error_details = validator.extract_validation_errors(content)
    
    if error_details.get("line_errors"):
        print("   Line-specific errors:")
        for line_no, line_errors in sorted(error_details["line_errors"].items()):
            print(f"   Line {line_no}:")
            for error in line_errors:
                print(f"      - {error}")
    
    if error_details.get("errors"):
        print("   General errors:")
        for error in error_details["errors"]:
            print(f"      - {error}")
    
    print("\n" + "="*60)
    print("Recommendations:")
    print("- Ensure all sections have <title> elements")
    print("- Check ID format (letters, numbers, underscore, hyphen only)")
    print("- Wrap text in <p> tags, not directly in structural elements")
    print("- Validate special characters are escaped (&, <, >)")
    
    return False

def main():
    parser = argparse.ArgumentParser(description='Validate DITA content')
    parser.add_argument('--job-id', help='Job ID to validate')
    parser.add_argument('--file', help='DITA file to validate')
    parser.add_argument('--fix', action='store_true', help='Attempt automatic fixes')
    parser.add_argument('--content', help='Direct DITA content to validate')
    
    args = parser.parse_args()
    
    content = None
    if args.file:
        with open(args.file, 'r') as f:
            content = f.read()
    elif args.content:
        content = args.content
    
    success = validate_job_dita(
        job_id=args.job_id,
        content=content,
        fix=args.fix
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
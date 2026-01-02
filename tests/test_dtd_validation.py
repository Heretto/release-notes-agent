#!/usr/bin/env python3
"""
Test DITA validation with local DTD files.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append('/Users/patrickbosek/dev/release-notes-agent/backend')

from app.services.dita_validator_v2 import DITAValidatorV2

def test_dtd_validation():
    """Test that DTD validation works with local DITA 1.3 DTDs."""
    
    print("="*60)
    print("DITA 1.3 DTD VALIDATION TEST")
    print("="*60)
    
    # Initialize validator (should use local DTDs)
    validator = DITAValidatorV2()
    
    # Check if DTD directory exists
    print(f"\nDTD Directory: {validator.dtd_dir}")
    print(f"Directory exists: {os.path.exists(validator.dtd_dir)}")
    
    if os.path.exists(validator.dtd_dir):
        # Check for specific DTD files
        dtd_files = [
            "dtd/technicalContent/dtd/topic.dtd",
            "dtd/technicalContent/dtd/concept.dtd",
            "dtd/technicalContent/dtd/task.dtd",
            "dtd/technicalContent/dtd/reference.dtd"
        ]
        
        print("\nChecking DTD files:")
        for dtd_file in dtd_files:
            full_path = os.path.join(validator.dtd_dir, dtd_file)
            exists = os.path.exists(full_path)
            status = "✓" if exists else "✗"
            print(f"  {status} {dtd_file}")
    
    print("\n" + "-"*60)
    print("Test 1: Valid DITA Topic (DTD Validation)")
    print("-"*60)
    
    valid_topic = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="release_notes">
  <title>Release Notes v1.0</title>
  <body>
    <section>
      <title>New Features</title>
      <ul>
        <li>Feature 1: Enhanced validation</li>
        <li>Feature 2: Better performance</li>
      </ul>
    </section>
    <section>
      <title>Bug Fixes</title>
      <ul>
        <li>Fixed issue with validation</li>
        <li>Resolved memory leak</li>
      </ul>
    </section>
  </body>
</topic>"""
    
    # Test with DTD validation
    valid, errors = validator.validate_with_dtd(valid_topic)
    
    if valid:
        print("✓ Valid DITA topic passed DTD validation")
    else:
        print(f"✗ Valid DITA topic failed DTD validation")
        if errors:
            for error in errors:
                print(f"  - {error}")
    
    print("\n" + "-"*60)
    print("Test 2: Invalid DITA Topic (Missing Required Elements)")
    print("-"*60)
    
    invalid_topic = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="test">
  <body>
    <p>Missing title element</p>
  </body>
</topic>"""
    
    valid, errors = validator.validate_with_dtd(invalid_topic)
    
    if not valid:
        print("✓ Invalid DITA topic correctly failed DTD validation")
        if errors:
            print(f"  Found {len(errors)} error(s):")
            for error in errors[:3]:  # Show first 3 errors
                print(f"  - {error}")
    else:
        print("✗ Invalid DITA topic incorrectly passed validation")
    
    print("\n" + "-"*60)
    print("Test 3: Valid DITA Concept")
    print("-"*60)
    
    valid_concept = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">
<concept id="intro">
  <title>Introduction to DITA</title>
  <conbody>
    <p>DITA is an XML standard for technical documentation.</p>
    <section>
      <title>Key Features</title>
      <p>DITA provides structured authoring capabilities.</p>
    </section>
  </conbody>
</concept>"""
    
    valid, errors = validator.validate_with_dtd(valid_concept, topic_type="concept")
    
    if valid:
        print("✓ Valid DITA concept passed DTD validation")
    else:
        print(f"✗ Valid DITA concept failed DTD validation")
        if errors:
            for error in errors:
                print(f"  - {error}")
    
    print("\n" + "-"*60)
    print("Test 4: Valid DITA Task")
    print("-"*60)
    
    valid_task = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN" "task.dtd">
<task id="install">
  <title>Installing the Software</title>
  <taskbody>
    <prereq>
      <p>Ensure you have admin privileges.</p>
    </prereq>
    <steps>
      <step>
        <cmd>Download the installer.</cmd>
      </step>
      <step>
        <cmd>Run the installer.</cmd>
      </step>
      <step>
        <cmd>Follow the setup wizard.</cmd>
      </step>
    </steps>
  </taskbody>
</task>"""
    
    valid, errors = validator.validate_with_dtd(valid_task, topic_type="task")
    
    if valid:
        print("✓ Valid DITA task passed DTD validation")
    else:
        print(f"✗ Valid DITA task failed DTD validation")
        if errors:
            for error in errors:
                print(f"  - {error}")
    
    print("\n" + "-"*60)
    print("Test 5: Auto-detection of Topic Type")
    print("-"*60)
    
    # Test auto-detection with a concept (without specifying topic_type)
    valid, errors = validator.validate_with_dtd(valid_concept)
    
    if valid:
        print("✓ Auto-detected concept type and validated successfully")
    else:
        print(f"✗ Auto-detection failed for concept")
        if errors:
            for error in errors[:2]:
                print(f"  - {error}")
    
    print("\n" + "-"*60)
    print("Test 6: Structural Validation Fallback")
    print("-"*60)
    
    # Test with a simple valid structure (should work even without DTD)
    simple_topic = """<?xml version="1.0" encoding="UTF-8"?>
<topic id="simple">
  <title>Simple Topic</title>
  <body>
    <p>This is a simple topic.</p>
  </body>
</topic>"""
    
    valid, errors = validator.validate_structure(simple_topic)
    
    if valid:
        print("✓ Structural validation works as fallback")
    else:
        print(f"✗ Structural validation failed")
        if errors:
            for error in errors:
                print(f"  - {error}")
    
    # Summary
    print("\n" + "="*60)
    print("VALIDATION SYSTEM STATUS")
    print("="*60)
    
    # Try to load a DTD to check if it works
    dtd = validator._get_dtd("topic")
    
    if dtd is not None:
        print("✅ DTD VALIDATION ENABLED")
        print(f"   Using local DITA 1.3 DTDs from:")
        print(f"   {validator.dtd_dir}")
        print("\n   The validator will now:")
        print("   1. Use DITA 1.3 DTDs for strict validation")
        print("   2. Auto-detect topic types (topic, concept, task, etc.)")
        print("   3. Fall back to structural validation if DTD unavailable")
        print("   4. Provide detailed DTD validation errors")
    else:
        print("⚠️ DTD VALIDATION NOT AVAILABLE")
        print("   Using structural validation only")
        print("\n   To enable DTD validation:")
        print("   1. Ensure DTD files exist at:")
        print(f"      {validator.dtd_dir}")
        print("   2. Check file permissions")
        print("   3. Verify lxml is installed")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    test_dtd_validation()
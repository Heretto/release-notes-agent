#!/usr/bin/env python3
"""
Unit tests for DITA validation functionality.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'backend'))

import unittest
from app.services.dita_validator_v2 import DITAValidatorV2


class TestDITAValidation(unittest.TestCase):
    """Test DITA validation functionality."""
    
    def setUp(self):
        """Set up test validator."""
        self.validator = DITAValidatorV2()
    
    def test_valid_dita_topic(self):
        """Test validation of a valid DITA topic."""
        valid_dita = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="release_notes_v1">
  <title>Release Notes v1.0</title>
  <body>
    <section>
      <title>New Features</title>
      <p>This release includes exciting new features.</p>
      <ul>
        <li>Feature 1</li>
        <li>Feature 2</li>
      </ul>
    </section>
  </body>
</topic>"""
        
        valid, errors = self.validator.validate_structure(valid_dita)
        self.assertTrue(valid, f"Valid DITA should pass validation. Errors: {errors}")
    
    def test_missing_title(self):
        """Test detection of missing title element."""
        invalid_dita = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="test">
  <body>
    <p>Content without title</p>
  </body>
</topic>"""
        
        valid, errors = self.validator.validate_structure(invalid_dita)
        self.assertFalse(valid, "Should fail without title")
        self.assertTrue(any("title" in str(e).lower() for e in errors))
    
    def test_missing_body(self):
        """Test detection of missing body element."""
        invalid_dita = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="test">
  <title>Title without body</title>
</topic>"""
        
        valid, errors = self.validator.validate_structure(invalid_dita)
        self.assertFalse(valid, "Should fail without body")
        self.assertTrue(any("body" in str(e).lower() for e in errors))
    
    def test_missing_id_attribute(self):
        """Test detection of missing ID attribute."""
        invalid_dita = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic>
  <title>Topic without ID</title>
  <body>
    <p>Content</p>
  </body>
</topic>"""
        
        valid, errors = self.validator.validate_structure(invalid_dita)
        self.assertFalse(valid, "Should fail without ID attribute")
        self.assertTrue(any("id" in str(e).lower() for e in errors))
    
    def test_invalid_id_format(self):
        """Test detection of invalid ID format."""
        test_cases = [
            ("123invalid", False, "IDs cannot start with number"),
            ("valid-id_123", True, "Valid ID with letters, numbers, hyphen, underscore"),
            ("invalid id", False, "IDs cannot contain spaces"),
            ("invalid.id", False, "IDs cannot contain dots"),
            ("_invalid", False, "IDs must start with letter"),
        ]
        
        for id_value, should_be_valid, description in test_cases:
            dita = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="{id_value}">
  <title>Test</title>
  <body><p>Content</p></body>
</topic>"""
            
            valid, errors = self.validator.validate_structure(dita)
            self.assertEqual(valid, should_be_valid, 
                           f"{description}: ID '{id_value}' validation incorrect. Errors: {errors}")
    
    def test_direct_text_in_structural_elements(self):
        """Test detection of direct text in structural elements."""
        invalid_dita = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="test">
  <title>Test</title>
  <body>
    <section>
      <title>Section Title</title>
      Direct text not in paragraph
    </section>
  </body>
</topic>"""
        
        valid, errors = self.validator.validate_structure(invalid_dita)
        self.assertFalse(valid, "Should fail with direct text in section")
        self.assertTrue(any("text outside" in str(e).lower() or "direct text" in str(e).lower() for e in errors))
    
    def test_section_without_title(self):
        """Test detection of section without title."""
        invalid_dita = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="test">
  <title>Test</title>
  <body>
    <section>
      <p>Section content without title</p>
    </section>
  </body>
</topic>"""
        
        valid, errors = self.validator.validate_structure(invalid_dita)
        self.assertFalse(valid, "Should fail with section missing title")
        self.assertTrue(any("section" in str(e).lower() and "title" in str(e).lower() for e in errors))
    
    def test_empty_list(self):
        """Test detection of empty list."""
        invalid_dita = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="test">
  <title>Test</title>
  <body>
    <ul></ul>
  </body>
</topic>"""
        
        valid, errors = self.validator.validate_structure(invalid_dita)
        self.assertFalse(valid, "Should fail with empty list")
        self.assertTrue(any("<ul>" in str(e) and "<li>" in str(e) for e in errors))
    
    def test_xml_syntax_error(self):
        """Test detection of XML syntax errors."""
        invalid_xml = """<?xml version="1.0" encoding="UTF-8"?>
<topic id="test">
  <title>Unclosed tag
  <body>
    <p>Content</p>
  </body>
</topic>"""
        
        valid, errors = self.validator.validate_structure(invalid_xml)
        self.assertFalse(valid, "Should fail with XML syntax error")
        self.assertTrue(any("syntax" in str(e).lower() for e in errors))
    
    def test_auto_fix_common_issues(self):
        """Test automatic fixing of common issues."""
        # Test adding XML declaration
        content = '<topic id="test"><title>Test</title><body><p>Content</p></body></topic>'
        fixed = self.validator.auto_fix_common_issues(content)
        self.assertTrue(fixed.startswith('<?xml'), "Should add XML declaration")
        
        # Test fixing unescaped ampersand
        content = '<?xml version="1.0"?><topic id="test"><title>Test & Demo</title><body><p>Content</p></body></topic>'
        fixed = self.validator.auto_fix_common_issues(content)
        self.assertIn('&amp;', fixed, "Should escape ampersand")
        
        # Test fixing invalid ID
        content = '<?xml version="1.0"?><topic id="123 invalid id"><title>Test</title><body><p>Content</p></body></topic>'
        fixed = self.validator.auto_fix_common_issues(content)
        self.assertNotIn(' ', fixed[fixed.find('id="'):fixed.find('"', fixed.find('id="')+4)], 
                        "Should remove spaces from ID")
    
    def test_extract_validation_errors(self):
        """Test extraction of detailed validation errors."""
        invalid_dita = """<?xml version="1.0" encoding="UTF-8"?>
<topic>
  <body>
    <p>Missing title and ID</p>
  </body>
</topic>"""
        
        errors = self.validator.extract_validation_errors(invalid_dita)
        
        self.assertTrue(errors["has_errors"], "Should have errors")
        # DTD validation via xmllint emits line-numbered errors into line_errors;
        # structural validation puts them in errors.  Either is acceptable.
        all_errors = errors["errors"] + [
            e for errs in errors["line_errors"].values() for e in errs
        ]
        self.assertTrue(len(all_errors) > 0, "Should have at least one error (in errors or line_errors)")
    
    def test_nested_sections(self):
        """Test validation of nested sections."""
        valid_dita = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="test">
  <title>Test Topic</title>
  <body>
    <section>
      <title>Main Section</title>
      <p>Some content</p>
      <section>
        <title>Nested Section</title>
        <p>Nested content</p>
      </section>
    </section>
  </body>
</topic>"""
        
        valid, errors = self.validator.validate_structure(valid_dita)
        self.assertTrue(valid, f"Nested sections should be valid. Errors: {errors}")
    
    def test_special_characters(self):
        """Test handling of special characters."""
        test_cases = [
            ("&amp;", True, "Escaped ampersand"),
            ("&lt;", True, "Escaped less-than"),
            ("&gt;", True, "Escaped greater-than"),
            ("&quot;", True, "Escaped quote"),
            ("&apos;", True, "Escaped apostrophe"),
        ]
        
        for char, should_be_valid, description in test_cases:
            dita = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="test">
  <title>Test {char} Character</title>
  <body>
    <p>Content with {char} character</p>
  </body>
</topic>"""
            
            valid, errors = self.validator.validate_structure(dita)
            self.assertEqual(valid, should_be_valid, 
                           f"{description} should be {'valid' if should_be_valid else 'invalid'}. Errors: {errors}")


class TestDITAValidationIntegration(unittest.TestCase):
    """Integration tests for DITA validation with real-world examples."""
    
    def setUp(self):
        """Set up test validator."""
        self.validator = DITAValidatorV2()
    
    def test_release_notes_example(self):
        """Test validation of a typical release notes DITA document."""
        release_notes = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="release-notes-2024-01">
  <title>Release Notes - Version 2024.01</title>
  <shortdesc>Major release with new features and improvements</shortdesc>
  
  <prolog>
    <metadata>
      <keywords>
        <keyword>release notes</keyword>
        <keyword>version 2024.01</keyword>
      </keywords>
    </metadata>
  </prolog>
  
  <body>
    <section>
      <title>New Features</title>
      <ul>
        <li><b>[FEAT-001]</b> Added user authentication system</li>
        <li><b>[FEAT-002]</b> Implemented data export functionality</li>
      </ul>
    </section>
    
    <section>
      <title>Bug Fixes</title>
      <ul>
        <li><b>[BUG-101]</b> Fixed memory leak in data processing</li>
        <li><b>[BUG-102]</b> Resolved UI rendering issues on mobile devices</li>
      </ul>
    </section>
    
    <section>
      <title>Known Issues</title>
      <note type="warning">
        <p>Large file uploads may timeout on slower connections.</p>
      </note>
    </section>
  </body>
</topic>"""
        
        valid, errors = self.validator.validate_structure(release_notes)
        self.assertTrue(valid, f"Release notes example should be valid. Errors: {errors}")
    
    def test_ai_generated_markdown_detection(self):
        """Test detection of markdown content instead of DITA."""
        markdown_content = """# Release Notes

## New Features
- Feature 1
- Feature 2

## Bug Fixes
- Bug 1
- Bug 2"""
        
        valid, errors = self.validator.validate_structure(markdown_content)
        self.assertFalse(valid, "Markdown content should fail DITA validation")
        self.assertTrue(any("syntax" in str(e).lower() for e in errors))


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
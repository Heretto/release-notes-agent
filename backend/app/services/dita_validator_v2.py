"""
Enhanced DITA Validator with DTD validation and AI-driven error correction.
"""

import os
import re
import logging
import subprocess
import tempfile
from typing import Tuple, Optional, List, Dict, Any
from lxml import etree
from pathlib import Path

logger = logging.getLogger(__name__)


class DITAValidatorV2:
    """Enhanced DITA validator with DTD support and error correction."""
    
    # Map topic types to DTD file paths relative to dtd_dir
    DTD_FILES = {
        "topic": "dtd/technicalContent/dtd/topic.dtd",
        "concept": "dtd/technicalContent/dtd/concept.dtd",
        "task": "dtd/technicalContent/dtd/task.dtd",
        "reference": "dtd/technicalContent/dtd/reference.dtd",
        "troubleshooting": "dtd/technicalContent/dtd/troubleshooting.dtd",
        "glossentry": "dtd/technicalContent/dtd/glossentry.dtd",
        "glossgroup": "dtd/technicalContent/dtd/glossgroup.dtd"
    }
    
    def __init__(self, dtd_dir: Optional[str] = None):
        """Initialize validator with optional DTD directory."""
        # Default to the local DITA 1.3 DTDs in the app directory
        if dtd_dir is None:
            # Try to find the DTD directory relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            app_dir = os.path.dirname(current_dir)  # Go up to app directory
            dtd_dir = os.path.join(app_dir, "dtds", "org.oasis-open.dita.v1_3")
            
            # If not found, try from /app in Docker container
            if not os.path.exists(dtd_dir):
                dtd_dir = "/app/app/dtds/org.oasis-open.dita.v1_3"
        
        self.dtd_dir = dtd_dir
        self.dtd_cache = {}
        
        # Log DTD directory location
        if os.path.exists(self.dtd_dir):
            logger.info(f"Using DITA 1.3 DTDs from: {self.dtd_dir}")
        else:
            logger.warning(f"DTD directory not found at: {self.dtd_dir}")
    
    def _dtd_available(self, topic_type: str = "topic") -> bool:
        """Check if DTD file is available for the topic type."""
        dtd_relative_path = self.DTD_FILES.get(topic_type, self.DTD_FILES["topic"])
        dtd_path = os.path.join(self.dtd_dir, dtd_relative_path)
        return os.path.exists(dtd_path)
    
    def _get_dtd(self, topic_type: str = "topic") -> Optional[etree.DTD]:
        """Return None — DITA 1.3 DTDs exceed lxml's entity amplification limit.
        DTD validation is performed via xmllint instead (see _validate_with_xmllint).
        """
        return None

    # ------------------------------------------------------------------
    # xmllint-based DTD validation
    # ------------------------------------------------------------------

    _XMLLINT_AVAILABLE: Optional[bool] = None  # class-level cache

    @classmethod
    def _xmllint_available(cls) -> bool:
        """Return True if xmllint is present on PATH."""
        if cls._XMLLINT_AVAILABLE is None:
            try:
                subprocess.run(
                    ["xmllint", "--version"],
                    capture_output=True,
                    timeout=5,
                )
                cls._XMLLINT_AVAILABLE = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                cls._XMLLINT_AVAILABLE = False
        return cls._XMLLINT_AVAILABLE

    def _base_dtd_path(self) -> Optional[str]:
        """Return the absolute path to basetopic.dtd, or None if not found."""
        path = os.path.join(self.dtd_dir, "dtd", "base", "dtd", "basetopic.dtd")
        return path if os.path.exists(path) else None

    def _inject_system_doctype(self, content: str, topic_type: str, dtd_path: str) -> str:
        """Replace the DOCTYPE declaration with a local SYSTEM identifier."""
        # Strip any existing DOCTYPE
        stripped = re.sub(
            r'<!DOCTYPE\s[^>]*(?:"[^"]*"[^>]*)?>',
            '',
            content,
            flags=re.DOTALL,
        ).strip()
        doctype = f'<!DOCTYPE {topic_type} SYSTEM "{dtd_path}">'
        # Insert after the XML declaration if present
        xml_decl = re.match(r'<\?xml[^?]*\?>', stripped)
        if xml_decl:
            pos = xml_decl.end()
            return stripped[:pos] + '\n' + doctype + stripped[pos:]
        return doctype + '\n' + stripped

    def _validate_with_xmllint(self, content: str, topic_type: str = "topic") -> Tuple[Optional[bool], Optional[List[str]]]:
        """Validate against the DITA 1.3 base DTD using xmllint.

        Returns (True, None) on success, (False, errors) on failure,
        or (None, None) when xmllint / DTD files are unavailable.
        """
        if not self._xmllint_available():
            logger.debug("xmllint not found; skipping DTD validation")
            return None, None

        dtd_path = self._base_dtd_path()
        if dtd_path is None:
            logger.debug("DITA base DTD not found; skipping xmllint validation")
            return None, None

        validated_xml = self._inject_system_doctype(content, topic_type, dtd_path)

        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.xml', delete=False, encoding='utf-8'
        )
        try:
            tmp.write(validated_xml)
            tmp.close()

            result = subprocess.run(
                ["xmllint", "--valid", "--noout", tmp.name],
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            os.unlink(tmp.name)

        if result.returncode == 0:
            logger.debug("xmllint DTD validation passed")
            return True, None

        # Parse errors from stderr
        errors: List[str] = []
        for line in result.stderr.splitlines():
            line = line.strip()
            if line and ("validity error" in line or "parser error" in line or "error" in line.lower()):
                errors.append(line)
        if not errors and result.stderr.strip():
            errors = [result.stderr.strip()]

        logger.debug(f"xmllint DTD validation failed with {len(errors)} error(s)")
        return False, errors
    
    def validate_with_dtd(self, content: str, topic_type: Optional[str] = None) -> Tuple[bool, Optional[List[str]]]:
        """Validate DITA content against the DITA 1.3 DTD.

        Uses xmllint when available (most accurate — full DTD content model).
        Falls back to structural validation when xmllint or the DTD files are absent.
        """
        # Auto-detect topic type from root element tag
        if topic_type is None:
            try:
                parser = etree.XMLParser(recover=True, no_network=True, resolve_entities=False)
                doc = etree.fromstring(content.encode('utf-8'), parser)
                root_tag = doc.tag
                topic_type = root_tag if root_tag in self.DTD_FILES else "topic"
            except Exception:
                topic_type = "topic"

        # --- xmllint DTD validation (preferred) ---
        xmllint_valid, xmllint_errors = self._validate_with_xmllint(content, topic_type)
        if xmllint_valid is not None:
            return xmllint_valid, xmllint_errors

        # --- Fallback: structural validation ---
        logger.info("xmllint unavailable; using structural validation")
        return self.validate_structure(content)
    
    def validate(self, content: str) -> Tuple[bool, Optional[str]]:
        """Main validation method for backward compatibility."""
        # Try DTD validation first (will fall back to structural if DTD not available)
        valid, errors = self.validate_with_dtd(content)
        if not valid and errors:
            # Return errors as a single string for backward compatibility
            return False, "; ".join(errors)
        return valid, None
    
    def validate_structure(self, content: str) -> Tuple[bool, Optional[List[str]]]:
        """Validate DITA structure according to DITA 1.3 requirements."""
        errors = []
        
        try:
            parser = etree.XMLParser(recover=False, no_network=True, resolve_entities=False)
            doc = etree.fromstring(content.encode('utf-8'), parser)

            # Determine topic type and validate accordingly
            topic_type = doc.tag
            
            # Check root element - expanded list based on DITA 1.3
            valid_root_elements = [
                'topic', 'concept', 'task', 'reference', 'troubleshooting',
                'glossentry', 'glossgroup', 'generalTask'
            ]
            
            if topic_type not in valid_root_elements:
                errors.append(f"Invalid root element '{topic_type}'. Must be one of: {', '.join(valid_root_elements)}")
            
            # Check if we have DTDs available for enhanced validation context
            if self._dtd_available(topic_type):
                logger.debug(f"Validating against DITA 1.3 rules for '{topic_type}'")
            
            # Check required attributes
            if 'id' not in doc.attrib:
                errors.append("Root element missing required 'id' attribute")
            elif not re.match(r'^[a-zA-Z][a-zA-Z0-9_\-]*$', doc.attrib['id']):
                errors.append(f"Invalid ID format: '{doc.attrib['id']}'. IDs must start with a letter and contain only letters, numbers, underscores, and hyphens.")
            
            # Check for required elements based on topic type
            title = doc.find('title')
            if title is None:
                errors.append("Missing required <title> element")
            elif not title.text or not title.text.strip():
                errors.append("Title element is empty")
            
            # Check for body element based on topic type
            body_elements = {
                'task': 'taskbody',
                'concept': 'conbody',
                'reference': 'refbody',
                'troubleshooting': 'troublebody',
                'glossentry': 'glossdef',
                'topic': 'body',
                'generalTask': 'taskbody'
            }
            
            expected_body = body_elements.get(topic_type, 'body')
            body = doc.find(expected_body)
            
            # Also check for generic 'body' as fallback
            if body is None and expected_body != 'body':
                body = doc.find('body')
                if body is not None:
                    # Using generic body is acceptable but note it
                    logger.debug(f"Using generic <body> element for {topic_type}")
            
            if body is None:
                errors.append(f"Missing required <{expected_body}> element")
            
            # Validate element nesting
            if body is not None:
                self._validate_body_content(body, errors)
            
            # Check for common issues
            self._check_common_issues(doc, errors)
            
            return len(errors) == 0, errors if errors else None
            
        except etree.XMLSyntaxError as e:
            line_error = f"XML Syntax Error"
            if hasattr(e, 'lineno'):
                line_error += f" at line {e.lineno}"
            line_error += f": {e.msg}"
            errors.append(line_error)
            return False, errors
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            return False, errors
    
    def _validate_body_content(self, body: etree.Element, errors: List[str]):
        """Validate content within body element."""
        # Elements that can contain text directly
        text_containers = {'p', 'li', 'note', 'title', 'ph', 'b', 'i', 'u', 'codeph'}
        
        # Elements that should not contain direct text
        structural_elements = {'section', 'ul', 'ol', 'table', 'fig', 'body'}
        
        for element in body.iter():
            # Check for invalid direct text in structural elements
            if element.tag in structural_elements:
                # Check for direct text (after children elements too)
                if element.text and element.text.strip():
                    errors.append(f"<{element.tag}> should not contain direct text. Use <p> or other text elements.")
                
                # Also check for text between child elements (tail text of children)
                for child in element:
                    if child.tail and child.tail.strip() and element.tag != 'body':
                        # Allow tail text in body as it might be between sections
                        if element.tag == 'section':
                            errors.append(f"<{element.tag}> contains text outside of proper elements. Use <p> tags.")
            
            # Check for required child elements
            if element.tag == 'section':
                title = element.find('title')
                if title is None:
                    errors.append(f"<section> missing required <title> element")
            
            if element.tag in ['ul', 'ol']:
                if not element.findall('li'):
                    errors.append(f"<{element.tag}> must contain at least one <li> element")
    
    def _check_common_issues(self, doc: etree.Element, errors: List[str]):
        """Check for common DITA authoring issues."""
        # Check for empty elements that shouldn't be empty
        non_empty_elements = {'title', 'p', 'li', 'note'}
        for elem_name in non_empty_elements:
            for elem in doc.iter(elem_name):
                if not elem.text or not elem.text.strip():
                    if not list(elem):  # No child elements either
                        errors.append(f"Empty <{elem_name}> element found")
        
        # Check for deprecated or invalid attributes
        for elem in doc.iter():
            for attr in elem.attrib:
                # Check for common invalid attributes
                if attr.startswith('xmlns:') and 'ditaarch' not in attr:
                    errors.append(f"Unexpected namespace attribute '{attr}' on <{elem.tag}>")
    
    def extract_validation_errors(self, content: str) -> Dict[str, Any]:
        """Extract detailed validation errors for AI correction."""
        errors_dict = {
            "has_errors": False,
            "errors": [],
            "warnings": [],
            "line_errors": {}
        }
        
        try:
            # Try parsing to get line numbers
            parser = etree.XMLParser(recover=False, no_network=True, resolve_entities=False)
            doc = etree.fromstring(content.encode('utf-8'), parser)
            
            # Run validation
            valid, errors = self.validate_structure(content)
            
            if not valid and errors:
                errors_dict["has_errors"] = True
                for error in errors:
                    # Parse error message for line numbers
                    line_match = re.search(r'line (\d+)', error, re.IGNORECASE)
                    if line_match:
                        line_no = int(line_match.group(1))
                        if line_no not in errors_dict["line_errors"]:
                            errors_dict["line_errors"][line_no] = []
                        errors_dict["line_errors"][line_no].append(error)
                    else:
                        errors_dict["errors"].append(error)
                        
        except etree.XMLSyntaxError as e:
            errors_dict["has_errors"] = True
            if hasattr(e, 'lineno'):
                errors_dict["line_errors"][e.lineno] = [f"XML Syntax Error: {e.msg}"]
            else:
                errors_dict["errors"].append(f"XML Syntax Error: {e.msg}")
        
        return errors_dict
    
    def generate_correction_prompt(self, content: str, errors: Dict[str, Any]) -> str:
        """Generate a prompt for AI to correct validation errors."""
        prompt = """You are a DITA XML validation expert. Your task is to fix DITA validation errors while preserving the exact text content.

CRITICAL RULES:
1. DO NOT change any text content - only fix XML/DITA structural issues
2. Preserve all text exactly as it appears (including typos, formatting, etc.)
3. Only make minimal changes needed to fix validation errors
4. Maintain all existing IDs and references

Current validation errors to fix:
"""
        
        # Add general errors
        if errors.get("errors"):
            prompt += "\nGeneral Errors:\n"
            for error in errors["errors"]:
                prompt += f"  - {error}\n"
        
        # Add line-specific errors
        if errors.get("line_errors"):
            prompt += "\nLine-specific Errors:\n"
            for line_no, line_errors in sorted(errors["line_errors"].items()):
                prompt += f"  Line {line_no}:\n"
                for error in line_errors:
                    prompt += f"    - {error}\n"
        
        prompt += f"""
                    
Common fixes needed:
- Add missing required elements (title, body)
- Fix ID format (must start with letter, only letters/numbers/underscore/hyphen)
- Remove direct text from structural elements (use <p> tags)
- Ensure sections have titles
- Fix empty elements that shouldn't be empty
- Escape special characters (&, <, >)

Here is the DITA content to fix:

{content}

Return ONLY the corrected DITA XML with no explanation or commentary."""
        
        return prompt
    
    def validate_and_fix(self, content: str, max_attempts: int = 3) -> Tuple[str, bool, List[str]]:
        """Validate and attempt to fix DITA content."""
        attempt = 0
        validation_log = []
        current_content = content
        
        while attempt < max_attempts:
            attempt += 1
            
            # Validate current content (uses DTD if available, falls back to structural)
            valid, errors = self.validate_with_dtd(current_content)
            
            if valid:
                validation_log.append(f"Attempt {attempt}: Validation successful")
                return current_content, True, validation_log
            
            validation_log.append(f"Attempt {attempt}: Found {len(errors) if errors else 0} errors")
            
            # Try automatic fixes first
            if attempt == 1:
                current_content = self.auto_fix_common_issues(current_content)
                validation_log.append("Applied automatic fixes")
                continue
            
            # If automatic fixes didn't work, we need AI correction
            # (This would be called by the orchestrator with AI service)
            if errors:
                validation_log.extend([f"  - {e}" for e in errors])
            break
        
        return current_content, False, validation_log
    
    def auto_fix_common_issues(self, content: str) -> str:
        """Automatically fix common DITA issues."""
        # Ensure XML declaration
        if not content.strip().startswith('<?xml'):
            content = '<?xml version="1.0" encoding="UTF-8"?>\n' + content.strip()
        
        # Ensure DOCTYPE
        if '<!DOCTYPE' not in content and '<topic' in content:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if '<topic' in line:
                    lines.insert(i, '<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">')
                    break
            content = '\n'.join(lines)
        
        # Fix unescaped ampersands
        content = re.sub(r'&(?![a-zA-Z]+;|#[0-9]+;|#x[0-9a-fA-F]+;)', '&amp;', content)
        
        # Fix invalid ID characters (basic fix - replace spaces and special chars)
        content = re.sub(
            r'(<(?:topic|concept|task|reference)[^>]*\sid=")([^"]+)(")',
            lambda m: m.group(1) + re.sub(r'[^a-zA-Z0-9_\-]', '_', m.group(2)) + m.group(3),
            content
        )
        
        # Ensure IDs start with a letter
        content = re.sub(
            r'(<(?:topic|concept|task|reference)[^>]*\sid=")(\d)',
            r'\1topic_\2',
            content
        )
        
        return content
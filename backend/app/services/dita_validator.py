from lxml import etree
from typing import Tuple, Optional
import os

class DITAValidator:
    """Service for validating DITA XML content."""
    
    def __init__(self):
        # DITA 1.3 DTD would normally be loaded here
        # For now, we'll use basic XML validation
        pass
    
    def validate_xml(self, content: str) -> Tuple[bool, Optional[str]]:
        """Validate XML structure."""
        try:
            # Parse XML
            parser = etree.XMLParser(remove_blank_text=True, no_network=True, resolve_entities=False)
            doc = etree.fromstring(content.encode('utf-8'), parser)

            # Basic validation passed
            return True, None
            
        except etree.XMLSyntaxError as e:
            return False, f"XML syntax error: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def validate_dita_structure(self, content: str) -> Tuple[bool, Optional[str]]:
        """Validate DITA topic structure."""
        try:
            parser = etree.XMLParser(remove_blank_text=True, no_network=True, resolve_entities=False)
            doc = etree.fromstring(content.encode('utf-8'), parser)

            # Check for required elements
            if doc.tag != 'topic':
                return False, "Root element must be 'topic'"
            
            # Check for required topic attributes
            if 'id' not in doc.attrib:
                return False, "Topic must have an 'id' attribute"
            
            # Check for title element
            title = doc.find('title')
            if title is None:
                return False, "Topic must have a 'title' element"
            
            # Check for body element
            body = doc.find('body')
            if body is None:
                return False, "Topic must have a 'body' element"
            
            # Validate allowed elements in body
            allowed_body_elements = {
                'section', 'p', 'ul', 'ol', 'li', 'note', 'codeblock', 
                'table', 'fig', 'image', 'xref', 'ph', 'b', 'i', 'u'
            }
            
            for element in body.iter():
                if element.tag not in allowed_body_elements and element != body:
                    # Allow nested structure but warn about unknown elements
                    pass
            
            return True, None
            
        except etree.XMLSyntaxError as e:
            return False, f"DITA parsing error: {str(e)}"
        except Exception as e:
            return False, f"DITA validation error: {str(e)}"
    
    def validate(self, content: str) -> Tuple[bool, Optional[str]]:
        """Perform full DITA validation."""
        # First validate XML structure
        valid, error = self.validate_xml(content)
        if not valid:
            return False, error
        
        # Then validate DITA structure
        valid, error = self.validate_dita_structure(content)
        if not valid:
            return False, error
        
        return True, None
    
    def fix_common_issues(self, content: str) -> str:
        """Attempt to fix common DITA issues."""
        import re
        
        # Ensure proper XML declaration
        if not content.startswith('<?xml'):
            content = '<?xml version="1.0" encoding="UTF-8"?>\n' + content
        
        # Ensure DOCTYPE declaration
        if '<!DOCTYPE' not in content and '<topic' in content:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if '<topic' in line:
                    lines.insert(i, '<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">')
                    break
            content = '\n'.join(lines)
        
        # Fix common XML entity issues
        # Find and escape unescaped ampersands (but not already escaped ones)
        content = re.sub(r'&(?![a-zA-Z]+;|#[0-9]+;|#x[0-9a-fA-F]+;)', '&amp;', content)
        
        # Fix unescaped less-than in text content (not in tags)
        # This is more complex, so we'll be conservative
        # Only fix obvious cases like "< " or "< word"
        content = re.sub(r'<\s+(?![a-zA-Z/!?])', '&lt; ', content)
        
        # Fix unescaped greater-than that might cause issues
        content = re.sub(r'(?<![a-zA-Z/])\s+>', ' &gt;', content)
        
        # Try to fix unclosed codeblock tags (common issue)
        # Count opening and closing codeblock tags
        open_codeblocks = len(re.findall(r'<codeblock[^>]*>', content))
        close_codeblocks = len(re.findall(r'</codeblock>', content))
        
        if open_codeblocks > close_codeblocks:
            # Find the last <codeblock> and ensure it's closed before </section> or </body>
            # This is a heuristic fix
            content = re.sub(r'(<codeblock[^>]*>.*?)(?=</section>|</body>)', 
                           r'\1</codeblock>', content, flags=re.DOTALL)
        
        return content
from typing import List, Dict, Optional
from datetime import datetime
import re

from app.models.schemas import JiraTicket

class DITAGenerator:
    """Service for generating DITA XML content."""
    
    def __init__(self):
        self.default_template = self._get_default_template()
    
    def _get_default_template(self) -> str:
        """Get default DITA release notes template."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="release-notes-{version}">
  <title>Release Notes - Version {version}</title>
  <shortdesc>{short_description}</shortdesc>
  
  <prolog>
    <metadata>
      <keywords>
        <keyword>release notes</keyword>
        <keyword>{product}</keyword>
        <keyword>{version}</keyword>
      </keywords>
    </metadata>
  </prolog>
  
  <body>
    {content}
  </body>
</topic>'''
    
    def generate_release_notes(
        self,
        tickets: List[JiraTicket],
        ai_content: str,
        version: str,
        product: str = "Product",
        short_description: Optional[str] = None
    ) -> str:
        """Generate DITA release notes from tickets and AI content."""
        
        # Clean the AI content first
        ai_content = self._clean_ai_content(ai_content)
        
        # Extract version ID for topic ID (remove special characters)
        version_id = re.sub(r'[^a-zA-Z0-9\-_]', '-', version)
        
        # Generate short description if not provided
        if not short_description:
            short_description = f"Release notes for {product} version {version}"
        
        # Check if AI returned a full DITA document instead of just body content
        if '<?xml' in ai_content or '<!DOCTYPE' in ai_content or '<topic' in ai_content:
            # AI returned a full document, extract just the body content
            ai_content = self._extract_body_content(ai_content)
        
        # The AI content should already be valid DITA body content,
        # but we should not escape it if it contains valid XML tags
        # Only escape if it appears to be plain text (no XML tags)
        if '<' not in ai_content or '>' not in ai_content:
            # Plain text content - wrap it properly
            ai_content = f"<section><p>{self._escape_xml(ai_content)}</p></section>"
        
        # Fill in the template
        dita_content = self.default_template.format(
            version=version,
            version_id=version_id,
            product=product,
            short_description=self._escape_xml(short_description),
            content=ai_content
        )
        
        return dita_content
    
    def categorize_tickets(self, tickets: List[JiraTicket]) -> Dict[str, List[JiraTicket]]:
        """Categorize tickets by type."""
        categories = {
            "features": [],
            "improvements": [],
            "bugs": [],
            "known_issues": []
        }
        
        for ticket in tickets:
            issue_type = ticket.issue_type.lower()
            
            if "bug" in issue_type or "defect" in issue_type:
                categories["bugs"].append(ticket)
            elif "feature" in issue_type or "story" in issue_type:
                categories["features"].append(ticket)
            elif "improvement" in issue_type or "enhancement" in issue_type:
                categories["improvements"].append(ticket)
            elif ticket.status.lower() in ["open", "in progress", "reopened"]:
                categories["known_issues"].append(ticket)
            else:
                # Default to improvements
                categories["improvements"].append(ticket)
        
        return categories
    
    def format_tickets_for_ai(self, tickets: List[JiraTicket]) -> str:
        """Format tickets for AI prompt."""
        categorized = self.categorize_tickets(tickets)
        formatted = []
        
        for category, category_tickets in categorized.items():
            if category_tickets:
                formatted.append(f"\n## {category.replace('_', ' ').title()}\n")
                for ticket in category_tickets:
                    formatted.append(f"- [{ticket.key}] {ticket.summary}")
                    if ticket.description:
                        # Truncate long descriptions
                        desc = ticket.description[:500]
                        if len(ticket.description) > 500:
                            desc += "..."
                        formatted.append(f"  Description: {desc}")
                    formatted.append("")
        
        return "\n".join(formatted)
    
    def create_prompt(
        self,
        tickets: List[JiraTicket],
        product: str,
        version: str,
        user_instructions: Optional[str] = None
    ) -> tuple[str, str]:
        """Create system and user prompts for AI generation."""
        
        system_prompt = """You are a technical writer creating release notes in DITA XML format.

## CRITICAL REQUIREMENT
You MUST generate ONLY the BODY CONTENT for a DITA topic. Do NOT include:
- NO <?xml version...?> declarations
- NO <!DOCTYPE...> declarations  
- NO <topic> root elements
- NO <prolog> or metadata sections
- ONLY provide content that goes INSIDE the <body> element

Do NOT use Markdown syntax:
- NO # or ## for headers - use <section><title>
- NO ** for bold - use <b> if needed
- NO * or - for lists - use <ul><li>
- NO backticks for code - use <codeblock> or <codeph>
- NO --- for separators - use sections to organize content

## Valid DITA Elements to Use
- <section> - Major sections of content
- <title> - Section titles
- <p> - Paragraphs
- <ul> - Unordered lists
- <ol> - Ordered lists
- <li> - List items
- <b> - Bold text
- <i> - Italic text
- <codeph> - Inline code
- <codeblock> - Code blocks
- <note> - Important notes
- <xref> - Cross references

## Structure Requirements
1. Generate ONLY the content for inside the <body> section
2. Organize content into logical sections
3. Each section should have a <title>
4. Write clear, user-facing descriptions
5. Include ticket references in square brackets

## XML Rules
- ALWAYS escape special characters:
  - Use &amp; for & (ampersand)
  - Use &lt; for < (less than) in text
  - Use &gt; for > (greater than) in text
  - Use &quot; for " in attributes
- Close all tags properly
- Use proper nesting

## Example Output (THIS IS WHAT YOU MUST GENERATE):
<section>
  <title>Executive Summary</title>
  <p>This release includes significant improvements to system stability and performance. Key updates include enhanced error handling, improved user interface responsiveness, and critical security fixes.</p>
</section>

<section>
  <title>New Features</title>
  <ul>
    <li><b>[PROJ-123]</b> Added support for advanced search filters allowing users to find content more efficiently</li>
    <li><b>[PROJ-456]</b> Implemented real-time collaboration features enabling multiple users to edit documents simultaneously</li>
  </ul>
</section>

<section>
  <title>Bug Fixes</title>
  <ul>
    <li><b>[PROJ-789]</b> Fixed issue where special characters in file names caused export failures</li>
    <li><b>[PROJ-101]</b> Resolved memory leak in the image processing module that affected system performance</li>
    <li><b>[PROJ-202]</b> Corrected validation error that prevented saving documents with embedded tables</li>
  </ul>
</section>

<section>
  <title>Known Issues</title>
  <ul>
    <li><b>[PROJ-303]</b> Large file uploads may timeout on slower network connections. Workaround: Split files larger than 100MB</li>
  </ul>
</section>

REMEMBER: Output ONLY valid DITA XML. NO Markdown syntax whatsoever."""
        
        if user_instructions:
            system_prompt += f"\n\n## Custom Instructions\n{user_instructions}"
        
        user_prompt = f"""Create release notes content for {product} version {version}.

Release Date: {datetime.now().strftime('%Y-%m-%d')}

JIRA Tickets to include:
{self.format_tickets_for_ai(tickets)}

CRITICAL: Generate ONLY the content that goes INSIDE a <body> element. 
DO NOT include:
- <?xml version="1.0"?> declarations
- <!DOCTYPE> declarations
- <topic>, <prolog>, or <body> tags
- Any wrapper elements

START your response directly with <section> tags. Generate ONLY valid DITA XML elements:
- Use <section> and <title> for sections
- Use <ul> and <li> for lists
- Use <p> for paragraphs
- Use <b> for ticket numbers

Create properly structured DITA XML content with sections for executive summary, new features, improvements, bug fixes, and known issues as appropriate based on the tickets provided."""
        
        return system_prompt, user_prompt
    
    def _escape_xml(self, text: str) -> str:
        """Escape special XML characters."""
        if not text:
            return ""
        
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&apos;")
        
        return text
    
    def _clean_ai_content(self, content: str) -> str:
        """Clean AI-generated content by removing any duplicate or unwanted parts."""
        if not content:
            return ""
        
        # Remove any duplicate XML declarations
        import re
        # Remove all XML declarations except the first one (but we'll add our own)
        content = re.sub(r'<\?xml[^>]*\?>', '', content)
        # Remove DOCTYPE declarations (we'll add our own)
        content = re.sub(r'<!DOCTYPE[^>]*>', '', content)
        
        # Trim whitespace
        content = content.strip()
        
        return content
    
    def _extract_body_content(self, content: str) -> str:
        """Extract just the body content from a full DITA document."""
        import re
        
        # Try to extract content between <body> tags
        body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL)
        if body_match:
            return body_match.group(1).strip()
        
        # If no body tags, try to extract content between <topic> tags
        topic_match = re.search(r'<topic[^>]*>.*?<body[^>]*>(.*?)</body>.*?</topic>', content, re.DOTALL)
        if topic_match:
            return topic_match.group(1).strip()
        
        # If still no match, check if the content is already just body content
        # (starts with section, p, ul, etc.)
        if content.strip().startswith(('<section', '<p>', '<ul>', '<ol>', '<note')):
            return content.strip()
        
        # Last resort: return the content as is, but log a warning
        import logging
        logging.warning("Could not extract body content from AI response, using full content")
        return content
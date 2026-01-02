"""
Service for AI-driven DITA validation error correction.
"""

import logging
from typing import Tuple, Optional, List, Dict, Any
from app.services.ai_service import AIServiceFactory, GenerationRequest
from app.services.dita_validator_v2 import DITAValidatorV2

logger = logging.getLogger(__name__)


class DITACorrectionService:
    """Service to correct DITA validation errors using AI."""
    
    def __init__(self, ai_service, validator: Optional[DITAValidatorV2] = None):
        """Initialize with AI service and validator."""
        self.ai_service = ai_service
        self.validator = validator or DITAValidatorV2()
        
    async def correct_validation_errors(
        self, 
        content: str, 
        max_attempts: int = 3,
        preserve_text: bool = True
    ) -> Tuple[str, bool, List[str]]:
        """
        Attempt to correct DITA validation errors using AI.
        
        Args:
            content: DITA content with validation errors
            max_attempts: Maximum correction attempts
            preserve_text: Whether to preserve original text content
            
        Returns:
            Tuple of (corrected_content, success, correction_log)
        """
        correction_log = []
        current_content = content
        
        for attempt in range(1, max_attempts + 1):
            # Validate current content
            valid, errors = self.validator.validate_structure(current_content)
            
            if valid:
                correction_log.append(f"Attempt {attempt}: Validation successful")
                return current_content, True, correction_log
            
            correction_log.append(f"Attempt {attempt}: Found {len(errors) if errors else 0} validation errors")
            
            # Extract detailed error information
            error_details = self.validator.extract_validation_errors(current_content)
            
            # Generate correction prompt
            correction_prompt = self._generate_correction_prompt(
                current_content, 
                error_details, 
                preserve_text
            )
            
            # Get AI correction
            try:
                corrected_content = await self._get_ai_correction(correction_prompt)
                
                # Validate the correction
                valid_after, errors_after = self.validator.validate_structure(corrected_content)
                
                if valid_after:
                    correction_log.append(f"Attempt {attempt}: AI correction successful")
                    return corrected_content, True, correction_log
                
                # Check if we made progress
                if errors_after and errors and len(errors_after) < len(errors):
                    correction_log.append(f"Attempt {attempt}: Reduced errors from {len(errors)} to {len(errors_after)}")
                    current_content = corrected_content
                else:
                    correction_log.append(f"Attempt {attempt}: No improvement, keeping previous version")
                    
            except Exception as e:
                correction_log.append(f"Attempt {attempt}: AI correction failed - {str(e)}")
                
        # Final validation attempt with auto-fixes
        correction_log.append("Applying automatic fixes as final attempt")
        final_content = self.validator.auto_fix_common_issues(current_content)
        valid_final, _ = self.validator.validate_structure(final_content)
        
        return final_content, valid_final, correction_log
    
    def _generate_correction_prompt(
        self, 
        content: str, 
        errors: Dict[str, Any],
        preserve_text: bool = True
    ) -> str:
        """Generate prompt for AI to correct validation errors."""
        
        if preserve_text:
            prompt = """You are a DITA XML validation expert. Fix the validation errors below while STRICTLY preserving all text content.

CRITICAL RULES:
1. DO NOT change any text content - preserve it exactly (including typos, case, punctuation)
2. DO NOT add or remove any text
3. DO NOT reorder sections or content
4. ONLY fix XML/DITA structural issues
5. Make minimal changes needed to fix validation errors

"""
        else:
            prompt = """You are a DITA XML validation expert. Fix the validation errors below.

RULES:
1. Fix all XML/DITA structural issues
2. Ensure valid DITA 1.3 structure
3. Make content well-formed and valid

"""
        
        prompt += "VALIDATION ERRORS TO FIX:\n"
        
        # Add general errors
        if errors.get("errors"):
            prompt += "\nGeneral Errors:\n"
            for error in errors["errors"]:
                prompt += f"• {error}\n"
        
        # Add line-specific errors
        if errors.get("line_errors"):
            prompt += "\nLine-Specific Errors:\n"
            for line_no, line_errors in sorted(errors["line_errors"].items()):
                prompt += f"Line {line_no}:\n"
                for error in line_errors:
                    prompt += f"  • {error}\n"
        
        prompt += """
COMMON FIXES NEEDED:
• Add missing <title> element after <topic>
• Add missing <body> element after <title>
• Fix invalid ID format (must start with letter, use only letters/numbers/underscore/hyphen)
• Move text content into <p> tags (structural elements like <section> can't have direct text)
• Add <title> to any <section> elements
• Ensure lists (<ul>/<ol>) contain <li> elements
• Escape special characters (&→&amp; <→&lt; >→&gt;)
• Close all opened tags properly

CURRENT DITA CONTENT:
```xml
{}
```

Return ONLY the corrected DITA XML. Do not include any explanation, commentary, or markdown formatting.
""".format(content)
        
        return prompt
    
    async def _get_ai_correction(self, prompt: str) -> str:
        """Get AI correction for DITA content."""
        
        system_prompt = """You are a DITA XML validation expert. Your role is to fix DITA structural errors while preserving content.
You must return valid DITA XML that conforms to DITA 1.3 standards.
Never add markdown formatting or explanations - return only pure XML."""
        
        request = GenerationRequest(
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=4096,
            temperature=0.1  # Low temperature for consistent corrections
        )
        
        response = await self.ai_service.generate(request)
        
        # Clean response (remove any markdown formatting if present)
        corrected = response.content.strip()
        
        # Remove markdown code blocks if present
        if corrected.startswith("```"):
            lines = corrected.split('\n')
            if lines[0].startswith("```"):
                lines = lines[1:]  # Remove first line
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # Remove last line
            corrected = '\n'.join(lines)
        
        return corrected
    
    async def validate_and_correct_with_ai(
        self,
        content: str,
        original_prompt: Optional[str] = None,
        max_cycles: int = 2
    ) -> Tuple[str, bool, List[str]]:
        """
        Validate DITA content and use AI to correct if needed.
        
        This is the main entry point for the orchestrator.
        """
        validation_log = []
        
        # First, try automatic fixes
        validation_log.append("Applying automatic fixes...")
        content = self.validator.auto_fix_common_issues(content)
        
        # Validate
        valid, errors = self.validator.validate_structure(content)
        
        if valid:
            validation_log.append("Content valid after automatic fixes")
            return content, True, validation_log
        
        validation_log.append(f"Validation failed with {len(errors) if errors else 0} errors")
        
        # Try AI correction
        for cycle in range(1, max_cycles + 1):
            validation_log.append(f"Starting AI correction cycle {cycle}")
            
            corrected, success, cycle_log = await self.correct_validation_errors(
                content,
                max_attempts=2,
                preserve_text=True
            )
            
            validation_log.extend(cycle_log)
            
            if success:
                return corrected, True, validation_log
            
            content = corrected
        
        # Final attempt: regenerate with stricter prompt if we have the original
        if original_prompt and max_cycles > 0:
            validation_log.append("Final attempt: Regenerating with stricter DITA requirements")
            
            enhanced_prompt = original_prompt + """

CRITICAL REQUIREMENT: Generate ONLY valid DITA 1.3 XML with this exact structure:
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="valid_id_here">
  <title>Title Here</title>
  <body>
    <!-- Your content sections here -->
  </body>
</topic>

Ensure all content is in valid DITA elements. No markdown, no plain text outside of elements."""
            
            try:
                request = GenerationRequest(
                    system_prompt="Generate valid DITA 1.3 XML only. No markdown.",
                    user_prompt=enhanced_prompt,
                    max_tokens=4096,
                    temperature=0.3
                )
                
                response = await self.ai_service.generate(request)
                content = response.content.strip()
                
                # Apply fixes and validate
                content = self.validator.auto_fix_common_issues(content)
                valid, _ = self.validator.validate_structure(content)
                
                if valid:
                    validation_log.append("Successfully regenerated valid DITA content")
                    return content, True, validation_log
                    
            except Exception as e:
                validation_log.append(f"Regeneration failed: {str(e)}")
        
        validation_log.append("Unable to produce valid DITA after all attempts")
        return content, False, validation_log
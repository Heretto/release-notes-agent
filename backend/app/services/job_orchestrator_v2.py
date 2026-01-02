"""
Enhanced Job Orchestrator with DITA validation and AI correction.
This is a partial update focusing on the DITA validation section.
"""

from app.services.dita_validator_v2 import DITAValidatorV2
from app.services.dita_correction_service import DITACorrectionService

# This would be integrated into the main job_orchestrator.py
# Showing the key validation section that would replace the current validation

async def process_dita_validation(self, job, dita_content, ai_response, ai_service):
    """
    Process DITA validation with AI-driven error correction.
    
    This method would replace the current validation section in job_orchestrator.py
    """
    logger = self.logger
    
    # Initialize enhanced validator and correction service
    validator = DITAValidatorV2()
    correction_service = DITACorrectionService(ai_service, validator)
    
    # Store original for comparison
    original_dita = dita_content
    
    logger.info(f"Starting DITA validation for job {job.id}")
    
    # Validate and correct with AI if needed
    corrected_content, is_valid, validation_log = await correction_service.validate_and_correct_with_ai(
        content=dita_content,
        original_prompt=None,  # Could pass original prompt for regeneration
        max_cycles=2
    )
    
    # Save validation log as artifact
    if validation_log:
        validation_artifact = JobArtifact(
            job_id=job.id,
            artifact_type="validation_log",
            filename=f"validation-log-{job.id}.log",
            content=self._format_validation_log(validation_log, is_valid)
        )
        self.db.add(validation_artifact)
        self.db.commit()
    
    if not is_valid:
        # Save error artifact with details
        error_details = validator.extract_validation_errors(corrected_content)
        
        error_artifact = JobArtifact(
            job_id=job.id,
            artifact_type="validation_error",
            filename=f"validation-error-{job.id}.log",
            content=self._format_validation_error(
                job.id,
                error_details,
                ai_response.content[:2000],
                corrected_content[:2000],
                validation_log
            )
        )
        self.db.add(error_artifact)
        self.db.commit()
        
        # Log warning but continue with best effort
        logger.warning(f"DITA validation failed for job {job.id} after correction attempts")
        
        # Use the best version we have
        dita_content = corrected_content
    else:
        # Validation successful
        logger.info(f"DITA validation successful for job {job.id}")
        dita_content = corrected_content
        
        # If content was corrected, save a note about it
        if corrected_content != original_dita:
            logger.info(f"DITA content was corrected during validation for job {job.id}")
            
            correction_note = JobArtifact(
                job_id=job.id,
                artifact_type="correction_note",
                filename=f"correction-note-{job.id}.log",
                content=f"""DITA Content Correction Summary
=====================================
Job ID: {job.id}
Timestamp: {datetime.utcnow().isoformat()}

The AI-generated DITA content required structural corrections to be valid.
The text content was preserved, but XML structure was fixed.

Validation Log:
{chr(10).join(validation_log)}

Content is now valid DITA 1.3.
"""
            )
            self.db.add(correction_note)
            self.db.commit()
    
    return dita_content, is_valid

def _format_validation_log(self, log_entries, is_valid):
    """Format validation log for artifact storage."""
    status = "SUCCESS" if is_valid else "FAILED"
    
    content = f"""DITA Validation Log
====================
Final Status: {status}
Timestamp: {datetime.utcnow().isoformat()}

Validation Steps:
"""
    
    for i, entry in enumerate(log_entries, 1):
        content += f"{i}. {entry}\n"
    
    return content

def _format_validation_error(self, job_id, error_details, ai_preview, dita_preview, validation_log):
    """Format validation error details for debugging."""
    content = f"""DITA Validation Error Report
============================
Job ID: {job_id}
Timestamp: {datetime.utcnow().isoformat()}

Error Summary:
--------------
"""
    
    if error_details.get("errors"):
        content += "\nGeneral Errors:\n"
        for error in error_details["errors"]:
            content += f"  • {error}\n"
    
    if error_details.get("line_errors"):
        content += "\nLine-Specific Errors:\n"
        for line_no, errors in error_details["line_errors"].items():
            content += f"  Line {line_no}:\n"
            for error in errors:
                content += f"    • {error}\n"
    
    content += f"""

Validation Attempts:
-------------------
{chr(10).join(validation_log)}

Original AI Response (first 2000 chars):
----------------------------------------
{ai_preview}

Final DITA Content (first 2000 chars):
--------------------------------------
{dita_preview}

Recommendation:
--------------
The content has structural DITA validation errors that could not be automatically corrected.
Consider:
1. Reviewing the AI model's DITA generation prompt
2. Checking if the instruction set properly specifies DITA output format
3. Manually correcting the DITA file if needed
"""
    
    return content
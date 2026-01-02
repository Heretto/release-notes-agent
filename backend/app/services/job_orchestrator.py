from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
import logging
from typing import Optional, Dict, Any

from app.models.database import Job, JobArtifact, JobRequest, InstructionSet, Credential, WebhookConfig
from app.services.jira_service import JiraService
from app.services.heretto_service import HerettoService
from app.services.ai_service import AIServiceFactory, GenerationRequest
from app.services.dita_generator import DITAGenerator
from app.services.dita_validator_v2 import DITAValidatorV2
from app.services.dita_correction_service import DITACorrectionService
from app.core.security import decrypt_credentials
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class JobOrchestrator:
    """Orchestrate the complete job processing workflow."""
    
    def __init__(self, db: Session):
        self.db = db
        self.dita_generator = DITAGenerator()
        self.dita_validator = DITAValidatorV2()
        self.logger = logger
    
    async def process_job(self, job_id: UUID) -> None:
        """Process a release notes generation job."""
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        try:
            # Update job status
            job.status = "running"
            job.started_at = datetime.utcnow()
            self.db.commit()
            
            # Step 1: Get Jira credentials
            jira_cred = self._get_credential(job.user_id, "jira")
            if not jira_cred:
                raise Exception("No Jira credentials found")
            
            jira_config = decrypt_credentials(jira_cred.encrypted_data)
            jira_service = JiraService(
                server=jira_config["server_url"],
                email=jira_config["email"],
                api_token=jira_config["api_token"]
            )
            
            # Step 2: Execute JQL query
            logger.info(f"Executing JQL query for job {job_id}")
            
            # Log the JIRA request
            import json
            import time
            jira_request = JobRequest(
                job_id=job.id,
                request_type="jira_query",
                request_data=json.dumps({
                    "jql": job.jql_query,
                    "server": jira_config["server_url"],
                    "max_tickets": job.max_tickets if job.max_tickets else 100
                }),
                status="pending"
            )
            self.db.add(jira_request)
            self.db.commit()
            
            start_time = time.time()
            try:
                # Use max_tickets if specified, otherwise default to 100
                max_results = job.max_tickets if job.max_tickets else 100
                tickets = await jira_service.execute_query(job.jql_query, max_results=max_results)
                job.tickets_processed = len(tickets)
                
                # Update request status
                jira_request.status = "success"
                jira_request.response_data = json.dumps({
                    "ticket_count": len(tickets),
                    "tickets": [t.key for t in tickets[:10]]  # First 10 ticket keys
                })
                jira_request.duration_ms = int((time.time() - start_time) * 1000)
                self.db.commit()
            except Exception as e:
                jira_request.status = "failed"
                jira_request.error_message = str(e)
                jira_request.duration_ms = int((time.time() - start_time) * 1000)
                self.db.commit()
                raise
            
            if not tickets:
                raise Exception("No tickets found matching JQL query")
            
            # Step 3: Get AI credentials
            # Use the AI credential specified in the job, or fall back to any available
            if job.ai_credential_id:
                ai_cred = self.db.query(Credential).filter(
                    Credential.id == job.ai_credential_id,
                    Credential.user_id == job.user_id
                ).first()
                if not ai_cred:
                    raise Exception(f"Specified AI credential {job.ai_credential_id} not found")
            else:
                # Fall back to any available AI credential (gemini, anthropic, or openai)
                ai_cred = self.db.query(Credential).filter(
                    Credential.user_id == job.user_id,
                    Credential.type.in_(["GEMINI", "ANTHROPIC", "OPENAI"])
                ).first()
                if not ai_cred:
                    raise Exception("No AI credentials found")
            
            # Determine the provider from credential type
            provider_map = {
                "gemini": "gemini",
                "anthropic": "anthropic", 
                "openai": "openai"
            }
            provider = provider_map.get(ai_cred.type.value, "gemini")
            
            ai_config = decrypt_credentials(ai_cred.encrypted_data)
            ai_service = AIServiceFactory.create(
                provider=provider,
                api_key=ai_config["api_key"],
                model=ai_config.get("model")
            )
            
            # Step 4: Generate prompts
            instruction_set = self.db.query(InstructionSet).filter(
                InstructionSet.id == job.instruction_set_id
            ).first()
            
            system_prompt, user_prompt = self.dita_generator.create_prompt(
                tickets=tickets,
                product="Product",  # TODO: Make this configurable
                version=self._extract_version(job.jql_query),
                user_instructions=instruction_set.user_instructions if instruction_set else None
            )
            
            if instruction_set and instruction_set.system_prompt:
                system_prompt = instruction_set.system_prompt
            
            if job.additional_instructions:
                user_prompt += f"\n\nAdditional Instructions:\n{job.additional_instructions}"
            
            # Step 5: Generate content with AI
            logger.info(f"Generating content with AI for job {job_id}")
            logger.debug(f"System prompt: {system_prompt[:200]}...")
            logger.debug(f"User prompt: {user_prompt[:500]}...")
            
            # Log the AI request
            ai_request = JobRequest(
                job_id=job.id,
                request_type="ai_generation",
                request_data=json.dumps({
                    "provider": provider,
                    "model": ai_config.get("model", "default"),
                    "system_prompt_preview": system_prompt[:500],
                    "user_prompt_preview": user_prompt[:500],
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "ticket_count": len(tickets)
                }),
                status="pending"
            )
            self.db.add(ai_request)
            self.db.commit()
            
            generation_request = GenerationRequest(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=4096,
                temperature=0.7
            )
            
            start_time = time.time()
            try:
                ai_response = await ai_service.generate(generation_request)
                logger.info(f"AI response received, content length: {len(ai_response.content)} chars")
                logger.debug(f"AI content preview: {ai_response.content[:500]}...")
                
                # Update request status
                ai_request.status = "success"
                ai_request.response_data = json.dumps({
                    "content_length": len(ai_response.content),
                    "content_preview": ai_response.content[:500],
                    "usage": getattr(ai_response, 'usage', None)
                })
                ai_request.duration_ms = int((time.time() - start_time) * 1000)
                self.db.commit()
            except Exception as e:
                ai_request.status = "failed"
                ai_request.error_message = str(e)
                ai_request.duration_ms = int((time.time() - start_time) * 1000)
                self.db.commit()
                raise
            
            # Save AI raw response as a separate log artifact for debugging
            ai_log_artifact = JobArtifact(
                job_id=job.id,
                artifact_type="ai_log",
                filename=f"ai-response-{job.id}.log",
                content=f"""AI Response Log
================
Job ID: {job.id}
Provider: {provider}
Model: {ai_config.get('model', 'unknown')}
Timestamp: {datetime.utcnow().isoformat()}
Tickets Processed: {len(tickets)}
Response Length: {len(ai_response.content)} characters

--- SYSTEM PROMPT ---
{system_prompt}

--- USER PROMPT ---
{user_prompt}

--- AI RESPONSE ---
{ai_response.content}
"""
            )
            self.db.add(ai_log_artifact)
            self.db.commit()
            logger.info(f"Saved AI response log for job {job.id}")
            
            # Step 6: Generate complete DITA document
            dita_content = self.dita_generator.generate_release_notes(
                tickets=tickets,
                ai_content=ai_response.content,
                version=self._extract_version(job.jql_query),
                product="Product"
            )
            
            # Step 7: Enhanced DITA Validation with AI Correction
            logger.info(f"Starting DITA validation for job {job_id}")
            
            # Initialize correction service with the AI service
            correction_service = DITACorrectionService(ai_service, self.dita_validator)
            
            # Store original for comparison
            original_dita = dita_content
            
            # Validate and correct with AI if needed
            corrected_content, is_valid, validation_log = await correction_service.validate_and_correct_with_ai(
                content=dita_content,
                original_prompt=user_prompt,  # Pass original prompt for potential regeneration
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
                error_details = self.dita_validator.extract_validation_errors(corrected_content)
                
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
            
            # Step 8: Save artifact - ensure it's clean DITA only
            # The dita_content should already be clean and valid, just ensure proper formatting
            final_dita_content = dita_content.strip()
            
            # Ensure the filename has .dita extension
            output_filename = job.output_filename or f"release-notes-{job.id}.dita"
            if not output_filename.endswith('.dita'):
                output_filename = output_filename.rsplit('.', 1)[0] + '.dita'
            
            artifact = JobArtifact(
                job_id=job.id,
                artifact_type="dita",
                filename=output_filename,
                content=final_dita_content
            )
            self.db.add(artifact)
            self.db.commit()
            
            logger.info(f"Saved clean DITA artifact: {output_filename}")
            
            # Step 9: Publish to Heretto if requested
            if job.auto_publish:
                heretto_cred = self._get_credential(job.user_id, "heretto")
                if heretto_cred:
                    heretto_config = decrypt_credentials(heretto_cred.encrypted_data)
                    heretto_service = HerettoService(
                        base_url=heretto_config.get("base_url", settings.heretto_base_url),
                        api_key=heretto_config["api_key"],
                        organization_id=heretto_config["organization_id"]
                    )
                    
                    logger.info(f"Publishing to Heretto for job {job_id}")
                    
                    # Log the Heretto request
                    heretto_request = JobRequest(
                        job_id=job.id,
                        request_type="heretto_publish",
                        request_data=json.dumps({
                            "filename": artifact.filename,
                            "folder_id": job.heretto_folder_id,
                            "content_length": len(dita_content)
                        }),
                        status="pending"
                    )
                    self.db.add(heretto_request)
                    self.db.commit()
                    
                    start_time = time.time()
                    try:
                        upload_result = await heretto_service.upload_dita_topic(
                            content=dita_content,
                            filename=artifact.filename,
                            folder_id=job.heretto_folder_id
                        )
                        
                        if upload_result.success:
                            artifact.heretto_doc_id = upload_result.document_id
                            heretto_request.status = "success"
                            heretto_request.response_data = json.dumps({
                                "document_id": upload_result.document_id,
                                "message": upload_result.message
                            })
                            heretto_request.duration_ms = int((time.time() - start_time) * 1000)
                            self.db.commit()
                        else:
                            logger.error(f"Heretto upload failed: {upload_result.message}")
                            heretto_request.status = "failed"
                            heretto_request.error_message = upload_result.message
                            heretto_request.duration_ms = int((time.time() - start_time) * 1000)
                            self.db.commit()
                    except Exception as e:
                        heretto_request.status = "failed"
                        heretto_request.error_message = str(e)
                        heretto_request.duration_ms = int((time.time() - start_time) * 1000)
                        self.db.commit()
                        raise
            
            # Step 10: Mark job as completed
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            self.db.commit()
    
    async def process_webhook_event(
        self,
        config_id: UUID,
        event_type: str,
        issue_key: str,
        payload: Dict[str, Any]
    ) -> None:
        """Process webhook event and create job if needed."""
        try:
            config = self.db.query(WebhookConfig).filter(
                WebhookConfig.id == config_id
            ).first()
            
            if not config or not config.is_active:
                return
            
            # Check if we should process this event
            if config.jql_filter:
                # TODO: Validate issue against JQL filter
                pass
            
            # Create job for this webhook event
            job = Job(
                user_id=config.user_id,
                instruction_set_id=config.instruction_set_id,
                jql_query=f"key = {issue_key}",  # Or use config.jql_filter
                triggered_by="webhook",
                status="pending",
                auto_publish=config.auto_publish,
                output_filename=f"release-notes-{issue_key}.dita"
            )
            
            self.db.add(job)
            self.db.commit()
            
            # Process the job
            await self.process_job(job.id)
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
    
    def _get_credential(self, user_id: UUID, cred_type: str) -> Optional[Credential]:
        """Get first credential of given type for user."""
        return self.db.query(Credential).filter(
            Credential.user_id == user_id,
            Credential.type == cred_type
        ).first()
    
    def _extract_version(self, jql: str) -> str:
        """Extract version from JQL query if possible."""
        import re
        
        # Look for fixVersion in JQL
        match = re.search(r"fixVersion\s*=\s*['\"]([^'\"]+)['\"]", jql)
        if match:
            return match.group(1)
        
        # Look for version in JQL
        match = re.search(r"version\s*=\s*['\"]([^'\"]+)['\"]", jql)
        if match:
            return match.group(1)
        
        # Default version
        return datetime.now().strftime("%Y.%m")
    
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
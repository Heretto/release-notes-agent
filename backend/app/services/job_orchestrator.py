from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
import logging
from typing import Optional, Dict, Any

from sqlalchemy import or_
from app.models.database import Job, JobArtifact, JobRequest, InstructionSet, InstructionSetAgent, Credential, CredentialType, WebhookConfig
from app.services.jira_service import JiraService
from app.services.heretto_service import HerettoService
from app.services.ai_service import AIServiceFactory
from app.services.dita_generator import DITAGenerator
from hop_core.dita import DitaValidator, DitaCorrectionService
from hop_core.agents import AgentDefinition, AgentRequest, AgentRunner
from hop_core.agents.providers import CredentialAiService
from app.core.security import decrypt_credentials
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class JobOrchestrator:
    """Orchestrate the complete job processing workflow."""
    
    def __init__(self, db: Session):
        self.db = db
        self.dita_generator = DITAGenerator()
        self.dita_validator = DitaValidator()
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
            
            # Step 1: Get Jira credentials (instruction set's choice, else user's own or org-shared)
            instruction_set = self.db.query(InstructionSet).filter(
                InstructionSet.id == job.instruction_set_id
            ).first()

            if instruction_set and instruction_set.jira_credential_id:
                jira_cred = self.db.query(Credential).filter(
                    Credential.id == instruction_set.jira_credential_id,
                    or_(
                        Credential.user_id == job.user_id,
                        Credential.organization_id == job.organization_id
                    )
                ).first()
                if not jira_cred:
                    raise Exception(
                        f"The instruction set's selected Jira credential "
                        f"{instruction_set.jira_credential_id} was not found"
                    )
                try:
                    jira_config = decrypt_credentials(jira_cred.encrypted_data)
                except Exception:
                    raise Exception(
                        f"Failed to decrypt Jira credential '{jira_cred.name}'. "
                        "It may need to be re-created."
                    )
            else:
                jira_cred, jira_config = self._get_decryptable_credential(
                    job.user_id, job.organization_id, CredentialType.JIRA
                )
                if not jira_cred:
                    raise Exception("No Jira credentials found. Please add Jira credentials in the Credentials page.")

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
                # Use max_tickets if specified, clamped to the configured upper limit
                from app.config import get_settings
                settings = get_settings()
                max_results = min(job.max_tickets or 100, settings.max_tickets_per_job)
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
            
            # Step 3: Get AI credentials (check user's own or organization-shared)
            if job.ai_credential_id:
                ai_cred = self.db.query(Credential).filter(
                    Credential.id == job.ai_credential_id,
                    or_(
                        Credential.user_id == job.user_id,
                        Credential.organization_id == job.organization_id
                    )
                ).first()
                if not ai_cred:
                    raise Exception(f"Specified AI credential {job.ai_credential_id} not found")
                try:
                    ai_config = decrypt_credentials(ai_cred.encrypted_data)
                except Exception:
                    raise Exception(
                        f"Failed to decrypt AI credential '{ai_cred.name}'. "
                        "It may need to be re-created."
                    )
            else:
                # Fall back to any available AI credential
                ai_cred, ai_config = self._get_decryptable_credential(
                    job.user_id, job.organization_id,
                    [CredentialType.GEMINI, CredentialType.ANTHROPIC, CredentialType.OPENAI]
                )
                if not ai_cred:
                    raise Exception("No AI credentials found. Please add AI credentials in the Credentials page.")

            provider = ai_cred.type if isinstance(ai_cred.type, str) else ai_cred.type.value
            ai_service = AIServiceFactory.create(
                provider=provider,
                api_key=ai_config["api_key"],
                model=ai_config.get("model")
            )
            
            # Step 4: Load the instruction set's ordered agent chain
            agent_links = []
            if instruction_set:
                agent_links = self.db.query(InstructionSetAgent).filter(
                    InstructionSetAgent.instruction_set_id == instruction_set.id
                ).order_by(InstructionSetAgent.position).all()

            if not agent_links:
                raise Exception(
                    "Instruction set has no agents configured. Add at least one agent "
                    "to its chain before running a job."
                )

            # dita_format_instructions carries the fixed DITA-output structural rules that
            # every agent in the chain must honor, regardless of each agent's own configured
            # system prompt; seed_prompt is the ticket-data payload that seeds the first agent.
            dita_format_instructions, seed_prompt = self.dita_generator.create_prompt(
                tickets=tickets,
                product="Product",  # TODO: Make this configurable
                version=self._extract_version(job.jql_query),
            )

            # Step 5: Run the agent chain in series, piping each agent's output into the next
            logger.info(f"Running {len(agent_links)}-agent chain for job {job_id}")

            current_output = seed_prompt
            last_result = None
            for index, link in enumerate(agent_links):
                agent_row = link.agent
                definition = AgentDefinition.from_model(agent_row)

                credential = agent_row.ai_configuration
                if credential is None:
                    raise Exception(
                        f"Agent '{agent_row.name}' has no AI configuration selected. "
                        "Configure one in the Agents page before running this job."
                    )
                try:
                    agent_ai_config = decrypt_credentials(credential.encrypted_data)
                except Exception:
                    raise Exception(
                        f"Failed to decrypt the AI configuration for agent '{agent_row.name}'. "
                        "It may need to be re-created."
                    )
                agent_ai_service = CredentialAiService.from_credential(
                    credential,
                    api_key=agent_ai_config["api_key"],
                    model=agent_ai_config.get("model") or "",
                )

                task = (
                    "Generate the release notes body content from the Jira ticket data below."
                    if index == 0 else
                    "Refine the previous step's output according to your configured role, "
                    "preserving valid DITA structure."
                )
                agent_request = AgentRequest(
                    instructions=f"{dita_format_instructions}\n\n## Task\n{task}",
                    input=current_output,
                    max_tokens=4096,
                )

                agent_job_request = JobRequest(
                    job_id=job.id,
                    request_type="agent_run",
                    request_data=json.dumps({
                        "agent_id": str(agent_row.id),
                        "agent_name": agent_row.name,
                        "position": index,
                        "input_preview": current_output[:500],
                    }),
                    status="pending"
                )
                self.db.add(agent_job_request)
                self.db.commit()

                start_time = time.time()
                try:
                    last_result = await AgentRunner(agent_ai_service).run(definition, agent_request)
                    logger.info(
                        f"Agent '{agent_row.name}' produced {len(last_result.output)} chars"
                    )
                    agent_job_request.status = "success"
                    agent_job_request.response_data = json.dumps({
                        "content_length": len(last_result.output),
                        "content_preview": last_result.output[:500],
                        "provider": last_result.provider,
                        "model": last_result.model,
                    })
                    agent_job_request.duration_ms = int((time.time() - start_time) * 1000)
                    self.db.commit()
                except Exception as e:
                    agent_job_request.status = "failed"
                    agent_job_request.error_message = str(e)
                    agent_job_request.duration_ms = int((time.time() - start_time) * 1000)
                    self.db.commit()
                    raise

                current_output = last_result.output

            generated_content = current_output

            # Save the full chain output as a log artifact for debugging
            ai_log_artifact = JobArtifact(
                job_id=job.id,
                artifact_type="ai_log",
                filename=f"ai-response-{job.id}.log",
                content=f"""AI Response Log
================
Job ID: {job.id}
Agents run (in order): {', '.join(link.agent.name for link in agent_links)}
Final provider/model: {last_result.provider}/{last_result.model}
Timestamp: {datetime.utcnow().isoformat()}
Tickets Processed: {len(tickets)}
Response Length: {len(generated_content)} characters

--- SEED INPUT (ticket data) ---
{seed_prompt}

--- FINAL AGENT OUTPUT ---
{generated_content}
"""
            )
            self.db.add(ai_log_artifact)
            self.db.commit()
            logger.info(f"Saved AI response log for job {job.id}")

            # Step 6: Generate complete DITA document
            dita_content = self.dita_generator.generate_release_notes(
                tickets=tickets,
                ai_content=generated_content,
                version=self._extract_version(job.jql_query),
                product="Product"
            )
            
            # Step 7: Enhanced DITA Validation with AI Correction
            logger.info(f"Starting DITA validation for job {job_id}")
            
            # Initialize correction service with the AI service
            correction_service = DitaCorrectionService(ai_service, self.dita_validator)
            
            # Store original for comparison
            original_dita = dita_content
            
            # Validate and correct with AI if needed. Invalid DITA is recoverable:
            # the content is looped back through the LLM until it validates, up to
            # a configurable safety cap (which in practice is never reached).
            corrected_content, is_valid, validation_log = await correction_service.validate_and_correct_with_ai(
                content=dita_content,
                original_prompt=seed_prompt,  # Pass original prompt for potential regeneration
                max_iterations=settings.dita_max_correction_iterations,
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
                        generated_content[:2000],
                        corrected_content[:2000],
                        validation_log
                    )
                )
                self.db.add(error_artifact)
                self.db.commit()

                # The correction loop exhausted its safety cap without producing
                # valid DITA — an exceptional case that should not happen in
                # practice. Do NOT emit invalid DITA (e.g. a <section> root
                # instead of <topic>): fail the job so no malformed output is
                # ever saved or published. The validation_error artifact above
                # preserves the details for debugging.
                logger.error(
                    f"DITA validation failed for job {job.id}: correction loop reached its "
                    f"safety cap ({settings.dita_max_correction_iterations} iterations) "
                    "without producing valid DITA; no DITA artifact will be produced"
                )
                raise Exception(
                    "DITA validation failed: the generated content could not be made "
                    "valid within the maximum number of correction attempts, so no "
                    "output was produced. See the validation error log for details."
                )
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
            
            # Step 9: Publish to Heretto if requested (job flag or instruction set flag)
            should_publish = job.auto_publish
            if not should_publish and instruction_set and getattr(instruction_set, 'publish_to_heretto', False):
                should_publish = True
            if should_publish:
                heretto_cred, heretto_config = self._get_decryptable_credential(
                    job.user_id, job.organization_id, CredentialType.HERETTO
                )
                if heretto_cred:
                    heretto_service = HerettoService(
                        base_url=heretto_config.get("server_url", settings.heretto_base_url),
                        username=heretto_config["username"],
                        token=heretto_config["token"]
                    )
                    
                    logger.info(f"Publishing to Heretto for job {job_id}")

                    # Use job's folder ID, falling back to instruction set's
                    folder_id = job.heretto_folder_id
                    if not folder_id and instruction_set:
                        folder_id = instruction_set.heretto_folder_id

                    # Log the Heretto request
                    heretto_request = JobRequest(
                        job_id=job.id,
                        request_type="heretto_publish",
                        request_data=json.dumps({
                            "filename": artifact.filename,
                            "folder_id": folder_id,
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
                            folder_id=folder_id
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
            logger.error("Job %s failed: %s", job_id, e, exc_info=True)
            job.status = "failed"
            job.error_message = _sanitize_job_error(str(e))
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
            logger.error("Webhook processing failed: %s", e, exc_info=True)
    
    def _get_decryptable_credential(self, user_id: UUID, organization_id: Optional[UUID], cred_type) -> tuple:
        """Get a credential that can be successfully decrypted.

        Tries all matching credentials (by user or org) and returns the first
        one whose encrypted data can be decrypted. Skips stale/corrupt credentials.

        cred_type can be a single CredentialType or a list of CredentialType values.

        Returns (credential, decrypted_config) or (None, None) if none found.
        """
        query = self.db.query(Credential).filter(
            or_(
                Credential.user_id == user_id,
                Credential.organization_id == organization_id
            )
        )
        if isinstance(cred_type, list):
            query = query.filter(Credential.type.in_(cred_type))
        else:
            query = query.filter(Credential.type == cred_type)

        credentials = query.all()
        for cred in credentials:
            try:
                config = decrypt_credentials(cred.encrypted_data)
                return cred, config
            except Exception:
                logger.warning(f"Credential '{cred.name}' (id={cred.id}) has stale encryption, skipping")
                continue

        return None, None
    
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


# Messages that are safe to show to users (raised intentionally in process_job)
_SAFE_ERROR_PREFIXES = (
    "No Jira credentials found",
    "No tickets found",
    "No AI credentials found",
    "Specified AI credential",
    "Failed to decrypt AI credential",
    "Jira query failed",
    "Failed to get projects",
    "Failed to get versions",
    "Failed to get issue",
    "DITA validation failed",
    "Instruction set has no agents configured",
    "Agent '",
    "Failed to decrypt the AI configuration",
    "The instruction set's selected Jira credential",
    "Failed to decrypt Jira credential",
    "Anthropic returned HTTP",
    "OpenAI returned HTTP",
    "Gemini returned HTTP",
)


def _sanitize_job_error(error_msg: str) -> str:
    """Return a user-safe error message, stripping internal details."""
    if not error_msg:
        return "An unexpected error occurred while processing the job"
    for prefix in _SAFE_ERROR_PREFIXES:
        if error_msg.startswith(prefix):
            return error_msg
    return "An unexpected error occurred while processing the job — check the server logs for details"
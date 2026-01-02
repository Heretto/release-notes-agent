# Job Rerun Feature Implementation

## Overview
Successfully implemented the ability to rerun a job, which creates a new job with the same parameters as an existing completed or failed job.

## Implementation Details

### Backend Changes

#### 1. New API Endpoint (`backend/app/api/routes/jobs.py`)
Added a new POST endpoint at `/api/v1/jobs/{job_id}/rerun`:

```python
@router.post("/{job_id}/rerun", response_model=JobResponse)
async def rerun_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
```

**Features**:
- Creates a new job with the same parameters as the original
- Preserves all configuration settings:
  - JQL query
  - Instruction set
  - AI credential
  - Additional instructions
  - Output filename
  - Heretto folder
  - Auto-publish setting
  - Max tickets limit
- Sets the new job status to `PENDING`
- Sets trigger type to `MANUAL` (rerun is always manual)
- Automatically schedules the job for processing

### Frontend Changes

#### 1. Service Method (`frontend/src/app/core/services/jobs.service.ts`)
Added `rerunJob` method to the JobsService:

```typescript
rerunJob(id: string): Observable<Job> {
  return this.http.post<Job>(`${this.apiUrl}/${id}/rerun`, {});
}
```

#### 2. Job Detail Component (`job-detail.component.ts`)
- **UI**: Added "Rerun Job" button in the header actions
  - Available for completed and failed jobs
  - Uses `replay` icon for clarity
  - Includes tooltip explaining the action
- **Functionality**: 
  - Creates new job and navigates to it
  - Shows snackbar notification with option to view the new job

#### 3. Jobs List Component (`jobs.component.ts`)
- **UI**: Added "Rerun" option to the actions menu
  - Available for completed and failed jobs
  - Uses `replay` icon for consistency
- **Functionality**:
  - Creates new job and adds it to the list
  - Shows snackbar notification with navigation option

## User Experience

### When to Use Rerun vs Retry

**Rerun Job** (New Feature):
- Creates a **new** job with same parameters
- Available for both completed and failed jobs
- Use when you want to:
  - Re-process the same query with updated data
  - Generate fresh release notes for the same criteria
  - Test different AI models with same input

**Retry Job** (Existing Feature):
- Attempts to restart a **failed** job
- Only available for failed jobs
- Use when you want to:
  - Recover from temporary failures
  - Continue where the job left off

### Visual Indicators
- **Rerun Button**: Standard button with replay icon
- **Retry Button**: Accent color button with refresh icon
- **Tooltips**: Explain the difference between actions

## Testing

Created comprehensive test script at `tests/test_rerun_job.py` that verifies:
1. Authentication and authorization
2. Finding a suitable job to rerun
3. Creating a new job via rerun endpoint
4. Parameter preservation
5. New job status and processing

### Test Results
✅ All tests pass successfully:
- New job created with identical parameters
- Job properly queued for processing
- Frontend navigation works correctly

## API Documentation

### Endpoint: POST `/api/v1/jobs/{job_id}/rerun`

**Parameters**:
- `job_id` (UUID): ID of the job to rerun

**Headers**:
- `Authorization: Bearer {token}` - Required

**Response**: 
- `200 OK`: Returns the newly created job
- `404 Not Found`: Original job not found
- `401 Unauthorized`: Not authenticated

**Example Response**:
```json
{
  "id": "3f9b3721-9880-4716-a07b-5d05e9a793bc",
  "user_id": "user-uuid",
  "instruction_set_id": "instruction-uuid",
  "jql_query": "project = TEST",
  "status": "pending",
  "triggered_by": "manual",
  "created_at": "2024-01-02T14:58:00Z"
}
```

## Benefits

1. **Efficiency**: Quickly recreate complex job configurations
2. **Consistency**: Ensures identical parameters for comparison
3. **Convenience**: One-click operation from both list and detail views
4. **Flexibility**: Works for both successful and failed jobs
5. **Traceability**: Each rerun creates a new job with its own history

## Security Considerations

- Only job owners can rerun their jobs
- Authentication required via JWT token
- New job inherits user context from current session
- No exposure of sensitive data between users

## Future Enhancements

Potential improvements for future iterations:
1. Add "Rerun with modifications" option to adjust parameters
2. Track parent-child relationships between original and rerun jobs
3. Bulk rerun for multiple jobs
4. Schedule periodic reruns
5. Compare outputs between original and rerun jobs

## Conclusion

The job rerun feature provides users with a convenient way to recreate jobs with identical parameters, improving workflow efficiency and enabling easy re-processing of release notes generation tasks. The implementation is clean, secure, and integrates seamlessly with the existing UI/UX patterns.
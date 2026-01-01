# Testing Max Tickets Feature

## Setup
1. Ensure the application is running at http://localhost:4200
2. Login with your credentials

## Test Scenarios

### Test 1: Create Job with Max Tickets Limit
1. Navigate to Instructions page
2. Click the play button on any instruction set
3. In the job creation dialog:
   - Enter a filename (e.g., "test-max-tickets.xml")
   - **Enter "5" in the "Maximum Tickets to Process" field**
   - Leave other fields as default
4. Click "Generate Release Notes"
5. Navigate to the Jobs page
6. Click on the newly created job
7. Verify:
   - The job processes only 5 tickets (check "Tickets Processed" field)
   - The summary shows "5 / 5" for tickets processed
   - In the Requests tab, the JIRA query request should show `max_tickets: 5`

### Test 2: Create Job without Max Tickets (Default)
1. Create another job without specifying max_tickets
2. Verify:
   - The job processes up to 100 tickets (default limit)
   - No max_tickets limit is shown in the job details

### Test 3: Validation
1. Try to enter invalid values:
   - Enter 0 → Should show validation error
   - Enter -5 → Should show validation error
   - Enter 1001 → Should show validation error (max is 1000)
   - Enter 500 → Should be accepted

## Backend API Test

You can also test via API:

```bash
# Get auth token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your_email","password":"your_password"}' \
  | jq -r '.access_token')

# Create job with max_tickets
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jql_query": "project = TEST",
    "instruction_set_id": "your-instruction-set-id",
    "output_filename": "test-max-5.xml",
    "max_tickets": 5,
    "publish_to_heretto": false
  }'
```

## Expected Results
- Jobs with max_tickets specified should only process that many tickets
- The limit should be visible in the job details
- The JIRA API call should respect the limit
- Frontend validation should prevent invalid values
- Jobs without max_tickets should use the default (100)
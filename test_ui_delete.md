# Manual Test Instructions for Artifact Deletion Feature

## Setup
1. Access the application at http://localhost:4200
2. Login with your credentials (or create a new account if admin password is unknown)

## Test Steps

### Test 1: Delete Single Artifact
1. Navigate to the Jobs page
2. Find a completed job (or create one if needed)
3. Click on the job to view details
4. Go to the "Generated Content" tab
5. You should see:
   - A "Clear All Content" button at the top
   - Delete icons (trash can) next to each artifact
6. Click the delete icon for a single artifact
7. Confirm the deletion in the popup
8. Verify:
   - The artifact is removed from the list
   - A success message appears
   - The content preview clears if that artifact was being viewed

### Test 2: Delete All Artifacts
1. In the same job detail view
2. Click the "Clear All Content" button
3. Confirm deletion in the first popup
4. Type "DELETE" in the second confirmation prompt
5. Verify:
   - All artifacts are removed
   - Success message shows the count of deleted items
   - The "Generated Content" tab disappears (since no artifacts remain)

### Test 3: Cancel Deletion
1. Find another job with artifacts
2. Try to delete an artifact but cancel the confirmation
3. Verify nothing is deleted
4. Try "Clear All Content" but type something other than "DELETE"
5. Verify cancellation message appears and nothing is deleted

## Expected Results
- Individual artifacts can be deleted with single confirmation
- Clear all content requires double confirmation  
- Deleted artifacts are permanently removed from storage
- UI updates immediately to reflect deletions
- Appropriate success/error messages are displayed

## Visual Indicators
- Delete buttons are styled in red (warn color)
- Confirmation dialogs clearly explain the action
- Success messages appear in green snackbar
- Error messages appear in red snackbar
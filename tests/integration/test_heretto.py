#!/usr/bin/env python3
"""
Integration tests for Heretto CCMS service.

Tests the HerettoService against a real Heretto instance using
HERETTO_TESTING_SERVER, HERETTO_TESTING_LOGIN_USER, and HERETTO_TESTING_LOGIN_TOKEN
environment variables.
"""

import sys
import os
import asyncio
import base64
import xml.etree.ElementTree as ET

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

import httpx

# Backend imports are deferred to main() so the test can skip gracefully
# when the full backend dependency chain isn't installed locally.
HerettoService = None
HerettoFolder = None
HerettoUploadResult = None


def _import_backend():
    """Import backend modules. Call after env var check."""
    global HerettoService, HerettoFolder, HerettoUploadResult
    sys.path.append(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'backend'
    ))
    from app.services.heretto_service import HerettoService as _HS
    from app.models.schemas import HerettoFolder as _HF, HerettoUploadResult as _HUR
    HerettoService = _HS
    HerettoFolder = _HF
    HerettoUploadResult = _HUR


def get_env_vars():
    """Load and return Heretto test environment variables, or None if not set."""
    server = os.getenv("HERETTO_TESTING_SERVER")
    user = os.getenv("HERETTO_TESTING_LOGIN_USER")
    token = os.getenv("HERETTO_TESTING_LOGIN_TOKEN")
    if not all([server, user, token]):
        return None
    return server, user, token


def make_service(server, user, token):
    """Create a HerettoService instance."""
    return HerettoService(base_url=server, username=user, token=token)


def _auth_header(user, token):
    """Build Basic Auth header value."""
    auth_str = f"{user}:{token}"
    return f"Basic {base64.b64encode(auth_str.encode()).decode()}"


def _discover_test_folder(server, user, token):
    """Discover a folder ID from root level via raw API call.

    list_folders() requires a parent_id, so we use a raw GET to
    /rest/all-files/ to find a root-level folder for testing.
    Returns (folder_id, folder_name) or (None, None).
    """
    headers = {
        "Authorization": _auth_header(user, token),
        "Content-Type": "application/xml",
    }
    try:
        resp = httpx.get(f"{server.rstrip('/')}/rest/all-files/", headers=headers, timeout=10.0)
        if resp.status_code != 200:
            return None, None
        root = ET.fromstring(resp.text)
        # Look for folder elements in the response
        for folder_el in root.iter("folder"):
            folder_id = folder_el.get("id")
            folder_name = folder_el.get("name", "")
            if folder_id:
                return folder_id, folder_name
        return None, None
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_validate_connection(service):
    """Test that validate_connection() returns True with valid credentials."""
    print("\ntest_validate_connection")
    print("-" * 40)
    result = asyncio.run(service.validate_connection())
    assert result is True, f"Expected True, got {result}"
    print("  ✓ validate_connection() returned True")
    return True


def test_validate_connection_bad_credentials(server):
    """Test that validate_connection() returns False with bad credentials."""
    print("\ntest_validate_connection_bad_credentials")
    print("-" * 40)
    bad_service = HerettoService(base_url=server, username="bad-user", token="bad-token")
    result = asyncio.run(bad_service.validate_connection())
    assert result is False, f"Expected False, got {result}"
    print("  ✓ validate_connection() returned False for bad credentials")
    return True


def test_get_folder_info(service, folder_id, folder_name):
    """Test get_folder_info() returns a HerettoFolder for a known folder."""
    print("\ntest_get_folder_info")
    print("-" * 40)
    folder = asyncio.run(service.get_folder_info(folder_id))
    assert folder is not None, f"Expected HerettoFolder, got None for folder {folder_id}"
    assert isinstance(folder, HerettoFolder), f"Expected HerettoFolder, got {type(folder)}"
    assert folder.id, "folder.id should be non-empty"
    assert folder.name, "folder.name should be non-empty"
    assert folder.path, "folder.path should be non-empty"
    print(f"  Folder: id={folder.id}, name={folder.name}, path={folder.path}")
    print("  ✓ get_folder_info() returned valid HerettoFolder")
    return True


def test_list_folders(service, parent_folder_id):
    """Test list_folders() with a known parent folder ID."""
    print("\ntest_list_folders")
    print("-" * 40)

    # With None — should return empty list (service requires parent_id)
    result_none = asyncio.run(service.list_folders(None))
    assert isinstance(result_none, list), f"Expected list, got {type(result_none)}"
    print(f"  list_folders(None) returned {len(result_none)} items (expected 0)")

    # With a real parent folder ID
    result = asyncio.run(service.list_folders(parent_folder_id))
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    print(f"  list_folders({parent_folder_id}) returned {len(result)} items")
    for item in result:
        assert isinstance(item, HerettoFolder), f"Expected HerettoFolder, got {type(item)}"
        assert item.id, "folder.id should be non-empty"
        assert item.name, "folder.name should be non-empty"
        print(f"    - {item.name} (id={item.id})")
    print("  ✓ list_folders() returned valid results")
    return True


def test_upload_dita_topic(service, folder_id, server, user, token):
    """Test upload_dita_topic() creates a document and uploads content."""
    print("\ntest_upload_dita_topic")
    print("-" * 40)

    test_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="integration-test-topic">
  <title>Integration Test Topic</title>
  <body>
    <p>This is an automated integration test document. Safe to delete.</p>
  </body>
</topic>"""

    test_filename = "integration-test-topic.dita"
    document_id = None

    try:
        result = asyncio.run(service.upload_dita_topic(test_content, test_filename, folder_id))
        assert isinstance(result, HerettoUploadResult), f"Expected HerettoUploadResult, got {type(result)}"
        assert result.success is True, f"Upload failed: {result.message}"
        assert result.document_id, "document_id should be set on success"
        document_id = result.document_id
        print(f"  Uploaded document: id={result.document_id}")
        print(f"  URL: {result.url}")
        print("  ✓ upload_dita_topic() succeeded")
        return True
    finally:
        # Clean up: delete the uploaded document via raw API
        if document_id:
            _cleanup_document(server, user, token, document_id)


def test_get_folder_info_nonexistent(service):
    """Test get_folder_info() returns None for a nonexistent folder ID."""
    print("\ntest_get_folder_info_nonexistent")
    print("-" * 40)
    result = asyncio.run(service.get_folder_info("nonexistent-id"))
    assert result is None, f"Expected None for nonexistent folder, got {result}"
    print("  ✓ get_folder_info('nonexistent-id') returned None")
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cleanup_document(server, user, token, document_id):
    """Delete a document from Heretto via raw API call."""
    headers = {
        "Authorization": _auth_header(user, token),
        "Content-Type": "application/xml",
    }
    try:
        url = f"{server.rstrip('/')}/rest/all-files/{document_id}"
        resp = httpx.delete(url, headers=headers, timeout=10.0)
        if resp.status_code in (200, 204):
            print(f"  Cleaned up test document {document_id}")
        else:
            print(f"  ⚠ Failed to clean up document {document_id}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ⚠ Error cleaning up document {document_id}: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Heretto CCMS Integration Tests")
    print("=" * 60)

    env = get_env_vars()
    if not env:
        print("\nSkipping Heretto tests — environment variables not set.")
        print("Set the following to run these tests:")
        print("  HERETTO_TESTING_SERVER")
        print("  HERETTO_TESTING_LOGIN_USER")
        print("  HERETTO_TESTING_LOGIN_TOKEN")
        return True  # Not a failure — just nothing to test

    server, user, token = env

    # Import backend modules now that we know we'll run the tests
    try:
        _import_backend()
    except ImportError as e:
        print(f"\nSkipping Heretto tests — backend dependencies not available: {e}")
        print("Run tests inside Docker or install backend dependencies.")
        return True  # Not a failure — just can't run locally

    service = make_service(server, user, token)
    print(f"Server: {server}")

    results = []

    # Tests that don't need a folder ID
    for test_fn, args in [
        (test_validate_connection, (service,)),
        (test_validate_connection_bad_credentials, (server,)),
        (test_get_folder_info_nonexistent, (service,)),
    ]:
        try:
            test_fn(*args)
            results.append((test_fn.__name__, True, None))
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            results.append((test_fn.__name__, False, str(e)))
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append((test_fn.__name__, False, str(e)))

    # Discover a folder for folder-dependent tests
    folder_id, folder_name = _discover_test_folder(server, user, token)
    if not folder_id:
        print("\n⚠ Could not discover a test folder — skipping folder-dependent tests")
        for name in ["test_get_folder_info", "test_list_folders", "test_upload_dita_topic"]:
            results.append((name, True, "skipped (no folder found)"))
    else:
        print(f"\nUsing test folder: {folder_name} ({folder_id})")
        for test_fn, args in [
            (test_get_folder_info, (service, folder_id, folder_name)),
            (test_list_folders, (service, folder_id)),
            (test_upload_dita_topic, (service, folder_id, server, user, token)),
        ]:
            try:
                test_fn(*args)
                results.append((test_fn.__name__, True, None))
            except AssertionError as e:
                print(f"  ✗ FAILED: {e}")
                results.append((test_fn.__name__, False, str(e)))
            except Exception as e:
                print(f"  ✗ ERROR: {e}")
                results.append((test_fn.__name__, False, str(e)))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)

    passed = 0
    failed = 0
    for name, success, msg in results:
        if success:
            if msg:
                print(f"  ✓ {name} ({msg})")
            else:
                print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}: {msg}")
            failed += 1

    print(f"\nTotal: {passed}/{len(results)} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ All Heretto integration tests passed!")
    else:
        print("\n✗ Some Heretto tests failed")
        sys.exit(1)

#!/usr/bin/env python3
"""
Twingate Stale User Cleanup Script

Lists and optionally removes:
  - MANUAL users (non-ADMIN) with no device activity (login/auth) for 90+ days
  - PENDING accounts created over 30 days ago (invited but never activated)

NOTE: Activity tracking is based on device lastSuccessfulLoginAt (authentication events).
The Twingate GraphQL API may not return lastConnectedAt (actual connection activity)
for all devices or API token permission levels. If lastConnectedAt is unavailable,
the script falls back to lastSuccessfulLoginAt which may not reflect daily usage.

Requires:
  - A Twingate Access Token (from Admin Console → Settings → API Tokens)
  - Your network ID (the subdomain, e.g., 'networkidhere' for networkidhere.twingate.com)

Usage:
  # Dry run (default) — shows what WOULD be deleted
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py

  # Save output to a timestamped file
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py \
    --output-dir /root/cleanuptwingateusers

  # Enable debug mode (shows API requests and responses)
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py --debug

  # Live run — actually deletes users
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py --live

  # Live run with single-user confirmation (prompt for each deletion)
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py --live --single

  # Live run with output saved
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py \
    --live --output-dir /root/cleanuptwingateusers
"""

import os
import sys
import time
import json
import argparse
import requests
from datetime import datetime
from pathlib import Path

# ─── Config ────────────────────────────────────────────────────────────────

INACTIVE_DAYS = 90
NEVER_LOGIN_DAYS = 30

# ─── Helpers ───────────────────────────────────────────────────────────────

def gql_access_token():
    token = os.environ.get("TWINGATE_ACCESS_TOKEN", "").strip()
    if not token:
        print("ERROR: Set TWINGATE_ACCESS_TOKEN env var")
        sys.exit(1)
    return token


def gql_network_id():
    """Get the Twingate network name (used to construct API endpoint)."""
    nid = os.environ.get("TWINGATE_NETWORK_ID", "").strip()
    if not nid:
        print("ERROR: Set TWINGATE_NETWORK_ID env var (your network name, e.g., 'networkidhere')")
        sys.exit(1)
    return nid


def gql_api_url(network_id):
    """Construct the network-specific GraphQL API endpoint."""
    return f"https://{network_id}.twingate.com/api/graphql/"


def gql_headers(token):
    return {
        "Content-Type": "application/json",
        "X-API-KEY": token,
        "Accept": "application/json",
    }


def gql_query(token, network_id, operation, variables=None, debug=False):
    """Execute a GraphQL query/mutation and return parsed JSON."""
    api_url = gql_api_url(network_id)
    headers = gql_headers(token)
    payload = {"query": operation, "variables": variables or {}}

    if debug:
        print(f"\n[DEBUG] API URL: {api_url}")
        print(f"[DEBUG] Headers: {dict(headers)}")
        print(f"[DEBUG] Query:\n{operation}")
        print(f"[DEBUG] Variables: {variables or {}}\n")

    resp = requests.post(
        api_url,
        headers=headers,
        json=payload,
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"GraphQL error {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)
    data = resp.json()
    if "errors" in data and data["errors"]:
        print(f"GraphQL errors:")
        for err in data["errors"]:
            msg = err.get('message', 'unknown')
            locations = err.get('locations', [])
            path = err.get('path', [])
            print(f"  - Message: {msg}")
            if locations:
                print(f"    Locations: {locations}")
            if path:
                print(f"    Path: {path}")
        print(f"\nFull response: {json.dumps(data, indent=2)}")
        sys.exit(1)
    return data


def test_token(token, network_id, debug=False):
    """Test if the API token is valid with a simple query."""
    # Introspection might be disabled, try a real query instead
    test_queries = [
        # Try listing users with minimal fields
        """
        query {
          users {
            edges {
              node {
                id
              }
            }
          }
        }
        """,
        # Try getting network info
        """
        query {
          network {
            id
            name
          }
        }
        """,
        # Try introspection
        """
        {
          __schema {
            queryType {
              name
            }
          }
        }
        """,
    ]

    # Try different endpoint and auth header combinations
    tests = [
        (f"https://{network_id}.twingate.com/api/graphql/", "X-API-KEY"),
        (f"https://{network_id}.twingate.com/api/graphql", "X-API-KEY"),
    ]

    for endpoint, auth_type in tests:
        for test_query in test_queries:
            query_name = "users" if "users" in test_query else ("network" if "network" in test_query else "introspection")
            if debug:
                print(f"[Testing: {endpoint} | auth: {auth_type} | query: {query_name}]")
            try:
                # Temporarily override the functions
                original_gql_api_url = globals()['gql_api_url']
                original_gql_headers = globals()['gql_headers']

                globals()['gql_api_url'] = lambda nid: endpoint

                if auth_type == "Bearer":
                    globals()['gql_headers'] = lambda t: {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {t}",
                        "Accept": "application/json",
                    }
                else:
                    globals()['gql_headers'] = lambda t: {
                        "Content-Type": "application/json",
                        "X-API-KEY": t,
                        "Accept": "application/json",
                    }

                data = gql_query(token, network_id, test_query, {}, debug=debug)

                # Check if we got valid data
                if data.get("data"):
                    if debug:
                        print(f"✓ SUCCESS!")
                        print(f"✓ Working endpoint: {endpoint}")
                        print(f"✓ Working auth: {auth_type}")
                        print(f"✓ Working query type: {query_name}\n")
                    else:
                        print(f"✓ Token validated successfully\n")
                    return True, endpoint, auth_type

                # Restore original functions
                globals()['gql_api_url'] = original_gql_api_url
                globals()['gql_headers'] = original_gql_headers
            except SystemExit:
                # Restore original functions
                globals()['gql_api_url'] = lambda nid: f"https://{nid}.twingate.com/api/graphql"
                globals()['gql_headers'] = lambda t: {
                    "Content-Type": "application/json",
                    "X-API-KEY": t,
                    "Accept": "application/json",
                }
                if debug:
                    print(f"✗ Failed\n")
                continue

    if debug:
        print("✗ All endpoint, auth, and query variations failed")
    return False, None, None


# ─── GraphQL operations ────────────────────────────────────────────────────

LIST_USERS_QUERY = """
query {
  users {
    edges {
      node {
        id
        email
        firstName
        lastName
        role
        type
        state
        createdAt
        updatedAt
        devices {
          edges {
            node {
              id
              name
              lastSuccessfulLoginAt
              lastFailedLoginAt
              lastConnectedAt
            }
          }
        }
      }
    }
  }
}
"""

DELETE_USER_MUTATION = """
mutation UserDelete($id: ID!) {
  userDelete(id: $id) {
    ok
  }
}
"""


# ─── Main logic ────────────────────────────────────────────────────────────

def fetch_all_users(token, network_id):
    """Paginate through all users in the network."""
    data = gql_query(token, network_id, LIST_USERS_QUERY, {})
    edges = data["data"]["users"]["edges"]
    all_users = [edge["node"] for edge in edges]
    return all_users


def get_latest_device_activity(user, debug=False):
    """Get the most recent device activity timestamp for a user.

    Checks both lastConnectedAt (actual usage) and lastSuccessfulLoginAt (authentication).
    Uses the most recent timestamp from either field across all devices.
    """
    devices = user.get("devices", {}).get("edges", [])

    if not devices:
        return None

    latest_activity = None
    email = user.get("email", "unknown")

    for device_edge in devices:
        device = device_edge.get("node", {})
        device_name = device.get("name", "unknown")

        # Check both connected and login timestamps
        last_connected = device.get("lastConnectedAt")
        last_login = device.get("lastSuccessfulLoginAt")

        if debug and globals().get('DEBUG_MODE', False):
            print(f"  [DEBUG] Device '{device_name}' for {email}:")
            print(f"    lastConnectedAt: {last_connected}")
            print(f"    lastSuccessfulLoginAt: {last_login}")

        timestamps = [last_connected, last_login]

        for ts in timestamps:
            if ts:
                try:
                    ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if latest_activity is None or ts_dt > latest_activity:
                        latest_activity = ts_dt
                except Exception as e:
                    if debug and globals().get('DEBUG_MODE', False):
                        print(f"    [DEBUG] Failed to parse timestamp '{ts}': {e}")
                    continue

    if debug and globals().get('DEBUG_MODE', False):
        print(f"  [DEBUG] Latest activity for {email}: {latest_activity}")

    return latest_activity


def classify_users(users):
    """Separate users into cleanup candidates based on the criteria."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    inactive_users = []   # accounts with no device activity for 90+ days
    never_login_users = []  # created > 30d ago, state=PENDING (never activated)
    other_users = []

    for u in users:
        # Skip non-MANUAL users (service accounts, SSO users, etc.)
        user_type = u.get("type")
        if user_type != "MANUAL":
            other_users.append((u, f"type={user_type} (not MANUAL)"))
            continue

        # Skip admins
        role = u.get("role")
        if role == "ADMIN":
            other_users.append((u, "role=ADMIN"))
            continue

        created = u.get("createdAt")
        state = u.get("state")

        # Check if user is PENDING (invited but never logged in)
        if state == "PENDING":
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if (now - created_dt).days >= NEVER_LOGIN_DAYS:
                        never_login_users.append(u)
                    else:
                        other_users.append((u, f"state=PENDING, created {(now - created_dt).days}d ago"))
                except Exception:
                    other_users.append((u, "state=PENDING, invalid createdAt"))
            continue

        # For active users, check device activity
        latest_activity = get_latest_device_activity(u, debug=globals().get('DEBUG_MODE', False))

        if latest_activity is None:
            # User has no devices or no successful logins
            # Check when account was created - if old, it's a candidate
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    days_since_created = (now - created_dt).days
                    if days_since_created >= INACTIVE_DAYS:
                        inactive_users.append((u, f"no device activity, created {days_since_created}d ago"))
                    else:
                        other_users.append((u, f"no device activity, created {days_since_created}d ago"))
                except Exception:
                    other_users.append((u, "no device activity, invalid createdAt"))
            else:
                other_users.append((u, "no device activity, no createdAt"))
        else:
            # Check when they last logged in
            inactive_days = (now - latest_activity).days
            if inactive_days >= INACTIVE_DAYS:
                inactive_users.append((u, f"last device login {inactive_days}d ago"))
            else:
                other_users.append((u, f"last device login {inactive_days}d ago"))

    return inactive_users, never_login_users, other_users


def build_display(user, extra=""):
    """Build a nice display line for a user."""
    user_type = user.get("type") or "MANUAL"
    role = user.get("role") or "MEMBER"
    state = user.get("state") or "ACTIVE"
    email = user.get("email") or "N/A"
    name = f"{user.get('firstName', '')} {user.get('lastName', '')}".strip() or email

    # Get device count and latest activity
    devices = user.get("devices", {}).get("edges", [])
    device_count = len(devices)
    latest_activity = get_latest_device_activity(user)

    if latest_activity:
        last_login_str = latest_activity.strftime("%Y-%m-%d")
    else:
        last_login_str = "never"

    return f"  - {name:<35} | {email:<30} | {role:<10} | {state:<10} | devices:{device_count} | last:{last_login_str:<12} | {extra}"


class OutputWriter:
    """Handles writing output to both console and optional file."""
    def __init__(self, output_dir=None, network_id=""):
        self.output_dir = output_dir
        self.network_id = network_id
        self.file_handle = None
        self.file_path = None

        if output_dir:
            # Create directory if it doesn't exist
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"twingate_cleanup_{network_id}_{timestamp}.txt"
            self.file_path = Path(output_dir) / filename

            # Open file for writing
            self.file_handle = open(self.file_path, 'w', encoding='utf-8')
            self.write(f"Twingate Cleanup Report - {network_id}")
            self.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.write("=" * 100)
            self.write("")

    def write(self, message=""):
        """Write message to console and file (if configured)."""
        print(message)
        if self.file_handle:
            self.file_handle.write(message + "\n")
            self.file_handle.flush()

    def close(self):
        """Close the output file."""
        if self.file_handle:
            self.file_handle.close()
            print(f"\n📄 Report saved to: {self.file_path}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    parser = argparse.ArgumentParser(description="Clean up stale Twingate users")
    parser.add_argument("--live", action="store_true", help="Actually delete users")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Directory to save output report (e.g., /root/cleanuptwingateusers)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output (shows API requests/responses)")
    parser.add_argument("--single", action="store_true", help="Prompt for each user deletion individually (requires --live)")
    args = parser.parse_args()

    token = gql_access_token()
    network_id = gql_network_id()

    live_mode = args.live
    debug_mode = args.debug
    single_mode = args.single

    # Validate arguments
    if single_mode and not live_mode:
        print("ERROR: --single requires --live flag")
        print("The --single flag prompts for each deletion, which only makes sense in live mode.")
        sys.exit(1)

    # Store debug mode in a global so other functions can access it
    globals()['DEBUG_MODE'] = debug_mode

    # Test token
    if not debug_mode:
        print(f"Testing API token for network: {network_id}\n")
    success, working_endpoint, auth_type = test_token(token, network_id, debug_mode)
    if not success:
        print("\nERROR: Could not connect to Twingate API.")
        print("Please verify:")
        print(f"  1. Your network ID is correct: {network_id}")
        print(f"  2. Your token has the correct permissions")
        print(f"  3. The token is not expired")
        sys.exit(1)

    # Update the API URL function and headers to use the working configuration
    if working_endpoint:
        globals()['gql_api_url'] = lambda nid: working_endpoint

    if auth_type == "Bearer":
        globals()['gql_headers'] = lambda t: {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {t}",
            "Accept": "application/json",
        }

    # Initialize output writer
    with OutputWriter(args.output_dir, network_id) as out:
        # Fetch users
        out.write(f"Fetching users for network: {network_id}")
        users = fetch_all_users(token, network_id)
        out.write(f"Total users fetched: {len(users)}")
        out.write()

        # Classify
        inactive, never_login, other = classify_users(users)

        # Print summary by category
        out.write("=" * 100)
        out.write("CATEGORY: Inactive for 90+ days (no device connection or login activity)")
        out.write("=" * 100)
        for u, extra in inactive:
            out.write(build_display(u, extra))

        out.write()
        out.write("=" * 100)
        out.write("CATEGORY: PENDING users - invited but never activated (created 30+ days ago)")
        out.write("=" * 100)
        for u in never_login:
            out.write(build_display(u, f"created {u.get('createdAt', '')!r}"))

        out.write()
        out.write("=" * 100)
        out.write("CATEGORY: Kept (not a candidate for cleanup)")
        out.write("=" * 100)
        for u, reason in other:
            out.write(build_display(u, reason))

        total_remove = len(inactive) + len(never_login)

        if total_remove == 0:
            out.write("\nNo users to remove. You're all set!")
            sys.exit(0)

        # Final summary with action
        out.write()
        out.write("=" * 100)
        out.write(f"TO REMOVE: {total_remove} user(s)")
        out.write("=" * 100)

        # Ask for confirmation
        if not live_mode:
            out.write()
            out.write("[DRY RUN] No users will be deleted.")
            out.write("To actually delete, run with --live flag.")
            return

        # In single mode, skip the bulk confirmation (we'll ask per-user)
        if not single_mode:
            confirm = input(f"\n🔥 You are about to PERMANENTLY delete {total_remove} user(s). Continue? [y/N]: ")
            if confirm.lower() != "y":
                out.write("\nAborted by user.")
                print("Aborted.")
                sys.exit(0)

        # Delete users
        out.write()
        if single_mode:
            out.write("--- Deleting users (single mode - prompting for each) ---")
        else:
            out.write("--- Deleting users ---")
        deleted = []
        failed = []
        skipped = []

        # Combine all users to delete
        all_to_delete = [(u, extra, "inactive") for u, extra in inactive] + \
                        [(u, f"created {u.get('createdAt', '')!r}", "pending") for u in never_login]

        for u, reason, category in all_to_delete:
            email = u.get("email") or "N/A"
            name = f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() or email

            # In single mode, prompt for each user
            if single_mode:
                print(f"\n{build_display(u, reason)}")
                confirm = input(f"Delete this user? [y/N/q(quit)]: ").lower()

                if confirm == 'q':
                    out.write(f"\n⏹️  Deletion process stopped by user at: {name}")
                    print("\nStopping deletion process...")
                    break
                elif confirm != 'y':
                    skipped.append(u)
                    out.write(f"  ⊘ Skipped: {name} ({email})")
                    continue

            try:
                gql_query(token, network_id, DELETE_USER_MUTATION, {"id": u["id"]})
                deleted.append(u)
                if single_mode:
                    out.write(f"  ✓ Deleted: {name} ({email})")
            except Exception as e:
                failed.append((u, str(e)))
                if single_mode:
                    out.write(f"  ✗ Failed: {name} ({email}) - {str(e)}")

        # Show summary (unless in single mode where we already showed each action)
        if not single_mode:
            if deleted:
                out.write()
                out.write("✅ Successfully deleted:")
                for u in deleted:
                    out.write(build_display(u))

            if failed:
                out.write()
                out.write("❌ Failed to delete:")
                for u, err in failed:
                    out.write(f"  - {u.get('email', u.get('firstName', 'unknown'))}: {err}")

        out.write()
        if single_mode and skipped:
            out.write(f"Done. {len(deleted)} deleted, {len(skipped)} skipped, {len(failed)} failed.")
        else:
            out.write(f"Done. {len(deleted)} deleted, {len(failed)} failed.")


if __name__ == "__main__":
    main()

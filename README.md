# twingate-cleanup
clean up twingate accounts

Twingate Stale User Cleanup Script

Lists and optionally removes:
  - MANUAL users (non-ADMIN) with no device activity (login/auth) for 90+ days
  - PENDING accounts created over 30 days ago (invited but never activated)

## Important Note on Activity Tracking

Activity tracking is based on device `lastSuccessfulLoginAt` (authentication events).

**Limitation**: The Twingate GraphQL API may not return `lastConnectedAt` (actual connection
activity) for all devices or API token permission levels. This means:
- A user who authenticated once but connects daily may appear inactive
- The script tracks authentication, not daily usage
- This differs from the Twingate Admin Console "All Activity" view

**Recommendation**: Review the "Kept" category before assuming users are inactive. Cross-reference
with the Twingate Admin Console's activity logs for users near the 90-day threshold.

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

  # Live run with force mode (no confirmation prompts - use with caution!)
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py --live --force

  # Live run with output saved
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py \
    --live --output-dir /root/cleanuptwingateusers

Options:
  --live              Actually delete users (default is dry-run)
  --output-dir DIR    Save report to timestamped file in specified directory
  --debug             Show detailed API requests and responses
  --single            Prompt for confirmation on each user deletion individually (requires --live)
  --force             Skip all confirmation prompts - deletes immediately (requires --live, mutually exclusive with --single)

Output files are named: twingate_cleanup_{network}_{timestamp}.txt
Example: twingate_cleanup_networkidhere_20260623_143052.txt

# twingate-cleanup
clean up twingate accounts

Twingate Stale User Cleanup Script

Lists and optionally removes:
  - MANUAL users (non-ADMIN) with no device activity (login/auth) for 90+ days
  - PENDING accounts created over 30 days ago (invited but never activated)
  - OLD devices with no activity for 45+ days (archives, not deletes - can be reactivated) (opt-in)

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

  # Override thresholds (e.g., 120 days for inactive, 60 days for never logged in)
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py \
    --inactive-days 120 --never-login-days 60

  # Cleanup old devices (45+ days inactive) in addition to users
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py \
    --cleanup-devices --device-age-days 45

  # Only remove users who have NO connected devices (extra safety)
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py \
    --require-no-devices

  # Live run with output saved
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py \
    --live --output-dir /root/cleanuptwingateusers

  # Stdout-only mode for automation/scripting (no file output, no extra messages)
  TWINGATE_ACCESS_TOKEN=twt_v0... TWINGATE_NETWORK_ID=networkidhere python3 twingate-cleanup.py --stdout-only

Options:
  --live                   Actually delete users (default is dry-run)
  --output-dir DIR         Save report to timestamped file in specified directory
  --stdout-only            Output only to stdout (no file output, for automation/scripting)
  --debug                  Show detailed API requests and responses
  --single                 Prompt for confirmation on each user deletion individually (requires --live)
  --force                  Skip all confirmation prompts - deletes immediately (requires --live, mutually exclusive with --single)
  --inactive-days N        Days threshold for inactive users (default: 90)
  --never-login-days N     Days threshold for users who never logged in (default: 30)
  --cleanup-devices        Also cleanup old devices in addition to users
  --device-age-days N      Days threshold for old devices (default: 45)
  --require-no-devices     Only remove users who have NO connected devices (additional safety check)

Output files are named: twingate_cleanup_{network}_{timestamp}.txt
Example: twingate_cleanup_networkidhere_20260623_143052.txt

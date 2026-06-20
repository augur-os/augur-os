"""
Data Expiration Checker

Scans data files for expired items and routes them to the reviews system
for user attention ("Needs Your Attention" on dashboard).

Expiry metadata schema:
  - expires_at: ISO date string (e.g., '2026-02-15')
  - expiry_policy: Shorthand duration (1d, 2d, 1w, 2w, 1m, 2m, 3m, never)
  - expiry_action: What to suggest (review, archive, delete)

Default policy: 1 month from 'added' or 'created_at' timestamp
"""

import json
import re
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import yaml

from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_project_root, get_runtime_dir  # noqa: E402
from src.lib.skill_paths import get_own_data_dir, get_peer_data_dir  # noqa: E402
from runtime_paths import get_notification_pending_path  # noqa: E402


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Duration parsing patterns
DURATION_PATTERN = re.compile(r'^(\d+)([dwm])$')
DURATION_MULTIPLIERS = {
    'd': 1,  # days
    'w': 7,  # weeks
    'm': 30,  # months (approximate)
}

# Default expiry policy (1 month)
DEFAULT_EXPIRY_POLICY = '1m'

# Files to scan for expiration (ADR-270: user data in external vault/state layers).
TRACKED_FILES = [
    # Jobs
    str(get_peer_data_dir(__file__, "career") / "job-analyzer" / "jobs" / "jobs-active.yaml"),
    str(get_peer_data_dir(__file__, "career") / "job-analyzer" / "jobs" / "jobs-inbox.yaml"),
    # Competition tracking
    str(get_peer_data_dir(__file__, "venture") / "competition" / "competitors.yaml"),
    # Recipes inbox
    str(get_peer_data_dir(__file__, "lifestyle") / "recipes" / "inbox.yaml"),
    # Learning queue
    str(get_own_data_dir(__file__) / "inbox" / "learning_queue.yaml"),
    # Notifications (runtime state path)
    str(get_notification_pending_path()),
    # Voice memos
    str(get_peer_data_dir(__file__, "apple") / "voice-memos" / "inbox.yaml"),
]


def parse_duration(policy: str) -> Optional[timedelta]:
    """Parse expiry policy string into timedelta.

    Args:
        policy: Duration string like '1d', '2w', '1m', or 'never'

    Returns:
        timedelta or None if 'never'
    """
    if policy == 'never':
        return None

    match = DURATION_PATTERN.match(policy)
    if not match:
        # Fall back to default
        return timedelta(days=30)

    amount = int(match.group(1))
    unit = match.group(2)
    days = amount * DURATION_MULTIPLIERS[unit]
    return timedelta(days=days)


def get_item_added_date(item: dict) -> Optional[datetime]:
    """Extract the creation/added date from an item.

    Checks common timestamp fields in order of preference.
    """
    for field in ['added', 'added_at', 'created_at', 'timestamp', 'date', 'last_updated']:
        if field in item and item[field]:
            try:
                value = item[field]
                if isinstance(value, datetime):
                    return value
                if isinstance(value, str):
                    # Handle ISO format with or without timezone
                    value = value.replace('Z', '+00:00')
                    if 'T' in value:
                        return datetime.fromisoformat(value.split('+')[0])
                    else:
                        return datetime.strptime(value, '%Y-%m-%d')
            except (ValueError, TypeError):
                continue
    return None


def calculate_expiry_date(item: dict) -> Optional[datetime]:
    """Calculate when an item expires.

    Uses explicit expires_at, or calculates from expiry_policy + added date.
    Falls back to default policy (1 month) if no policy specified.
    """
    # Check explicit expiry date
    if 'expires_at' in item and item['expires_at']:
        try:
            value = item['expires_at']
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value).replace('Z', ''))
        except (ValueError, TypeError):
            pass

    # Calculate from policy + added date
    added = get_item_added_date(item)
    if not added:
        return None

    policy = item.get('expiry_policy', DEFAULT_EXPIRY_POLICY)
    duration = parse_duration(policy)

    if duration is None:  # 'never'
        return None

    return added + duration


def is_expired(item: dict, now: Optional[datetime] = None) -> bool:
    """Check if an item has expired."""
    if now is None:
        now = datetime.now()

    # Skip items marked as 'never' expire
    if item.get('expiry_policy') == 'never':
        return False

    expiry_date = calculate_expiry_date(item)
    if expiry_date is None:
        return False

    return now > expiry_date


def get_item_identifier(item: dict, index: int) -> str:
    """Get a human-readable identifier for an item."""
    # Try common identifier fields
    for field in ['id', 'title', 'name', 'company', 'url']:
        if field in item and item[field]:
            value = str(item[field])
            if len(value) > 50:
                value = value[:47] + '...'
            return value
    return f"Item #{index + 1}"


def extract_items_from_file(file_path: Path) -> list[tuple[dict, str]]:
    """Extract items from a YAML file.

    Returns list of (item, list_key) tuples.
    Handles various file structures:
    - Root list
    - Dict with 'jobs', 'competitors', 'items', etc.
    """
    if not file_path.exists():
        return []

    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
    except Exception:
        return []

    if data is None:
        return []

    # Handle root list
    if isinstance(data, list):
        return [(item, '') for item in data if isinstance(item, dict)]

    # Handle dict with common list keys
    if isinstance(data, dict):
        results = []
        for key in ['jobs', 'competitors', 'items', 'tasks', 'entries', 'recipes', 'pending', 'ideas', 'memos']:
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict):
                        results.append((item, key))
        return results

    return []


def check_file_expirations(file_path: Path, now: Optional[datetime] = None) -> list[dict]:
    """Check a single file for expired items.

    Returns list of expired item reports.
    """
    if now is None:
        now = datetime.now()

    items = extract_items_from_file(file_path)
    expired = []

    for index, (item, list_key) in enumerate(items):
        if is_expired(item, now):
            expiry_date = calculate_expiry_date(item)
            days_expired = (now - expiry_date).days if expiry_date else 0

            expired.append(
                {
                    'file': str(file_path),
                    'list_key': list_key,
                    'index': index,
                    'identifier': get_item_identifier(item, index),
                    'added': get_item_added_date(item).isoformat() if get_item_added_date(item) else None,
                    'expired_at': expiry_date.isoformat() if expiry_date else None,
                    'days_expired': days_expired,
                    'policy': item.get('expiry_policy', DEFAULT_EXPIRY_POLICY),
                    'suggested_action': item.get('expiry_action', 'review'),
                    'item_preview': {
                        k: v
                        for k, v in item.items()
                        if k in ['title', 'name', 'company', 'status', 'url', 'description']
                    },
                }
            )

    return expired


def check_all_expirations(custom_files: Optional[list[str]] = None) -> dict[str, Any]:
    """Check all tracked files for expired items.

    Args:
        custom_files: Optional list of file paths to check instead of defaults

    Returns:
        Dict with expired items grouped by file
    """
    project_root = get_project_root()
    now = datetime.now()

    files_to_check = custom_files if custom_files else TRACKED_FILES

    all_expired = []
    files_checked = []

    for file_rel in files_to_check:
        file_path = project_root / file_rel
        if file_path.exists():
            files_checked.append(str(file_rel))
            expired = check_file_expirations(file_path, now)
            all_expired.extend(expired)

    # Sort by days expired (most urgent first)
    all_expired.sort(key=lambda x: x.get('days_expired', 0), reverse=True)

    return {
        'checked_at': now.isoformat(),
        'files_checked': files_checked,
        'total_expired': len(all_expired),
        'expired_items': all_expired,
    }


def create_review_items(expired_items: list[dict]) -> list[dict]:
    """Convert expired items into review items for the reviews system.

    These will appear in "Needs Your Attention" on the dashboard.
    """
    reviews = []

    for item in expired_items:
        identifier = item['identifier']
        days = item['days_expired']
        file_name = Path(item['file']).name

        # Determine priority based on how long expired
        if days > 30:
            priority = 'high'
        elif days > 14:
            priority = 'medium'
        else:
            priority = 'low'

        # Create review item
        review = {
            'id': f"expiry-{uuid.uuid4().hex[:8]}",
            'skill': 'data-expiration',
            'type': 'data_review',
            'priority': priority,
            'title': f"Expired: {identifier}",
            'summary': f"Item in {file_name} expired {days} days ago. Action: {item['suggested_action']}",
            'created_at': datetime.now().isoformat(),
            'status': 'pending',
            'metadata': {
                'file': item['file'],
                'list_key': item['list_key'],
                'index': item['index'],
                'suggested_action': item['suggested_action'],
                'item_preview': item.get('item_preview', {}),
            },
        }
        reviews.append(review)

    return reviews


def add_to_pending_reviews(reviews: list[dict]) -> int:
    """Add expired items to the pending reviews file.

    Returns count of items added.
    """
    reviews_dir = get_runtime_dir() / "attention" / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)

    pending_file = reviews_dir / "pending_reviews.yaml"

    # Load existing reviews
    existing = []
    if pending_file.exists():
        try:
            with open(pending_file, 'r') as f:
                data = yaml.safe_load(f)
                existing = data.get('reviews', []) if data else []
        except Exception:
            existing = []

    # Filter out duplicates (same file + identifier)
    existing_keys = set()
    for r in existing:
        if r.get('skill') == 'data-expiration':
            meta = r.get('metadata', {})
            key = f"{meta.get('file')}:{meta.get('index')}"
            existing_keys.add(key)

    new_reviews = []
    for review in reviews:
        meta = review.get('metadata', {})
        key = f"{meta.get('file')}:{meta.get('index')}"
        if key not in existing_keys:
            new_reviews.append(review)

    # Add new reviews
    all_reviews = existing + new_reviews

    # Save
    with open(pending_file, 'w') as f:
        yaml.dump({'reviews': all_reviews}, f, default_flow_style=False)

    return len(new_reviews)


def run_expiration_check(dry_run: bool = False) -> dict[str, Any]:
    """Run the full expiration check workflow.

    Args:
        dry_run: If True, don't add to reviews (just report)

    Returns:
        Summary of findings and actions taken
    """
    # Check for expired items
    result = check_all_expirations()

    if result['total_expired'] == 0:
        return {
            'success': True,
            'message': 'No expired items found',
            'files_checked': result['files_checked'],
            'expired_count': 0,
            'reviews_added': 0,
        }

    # Create review items
    reviews = create_review_items(result['expired_items'])

    if dry_run:
        return {
            'success': True,
            'dry_run': True,
            'files_checked': result['files_checked'],
            'expired_count': result['total_expired'],
            'would_add_reviews': len(reviews),
            'expired_items': result['expired_items'],
        }

    # Add to pending reviews
    added = add_to_pending_reviews(reviews)

    return {
        'success': True,
        'files_checked': result['files_checked'],
        'expired_count': result['total_expired'],
        'reviews_added': added,
        'message': f"Added {added} items to review queue" if added > 0 else "All expired items already in review queue",
    }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Check data files for expired items')
    parser.add_argument('--dry-run', action='store_true', help='Report only, do not add reviews')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    result = run_expiration_check(dry_run=args.dry_run)

    if args.json:
        _out(json.dumps(result, indent=2))
    else:
        _out("\nExpiration Check Results")
        _out("========================")
        _out(f"Files checked: {len(result.get('files_checked', []))}")
        _out(f"Expired items: {result.get('expired_count', 0)}")

        if args.dry_run:
            _out(f"Would add reviews: {result.get('would_add_reviews', 0)}")
            if 'expired_items' in result:
                _out("\nExpired items:")
                for item in result['expired_items'][:10]:
                    _out(f"  - {item['identifier']} ({item['days_expired']} days expired)")
        else:
            _out(f"Reviews added: {result.get('reviews_added', 0)}")

        _out(f"\n{result.get('message', '')}")

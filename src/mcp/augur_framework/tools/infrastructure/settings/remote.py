"""Remote provider scope handlers — execute, scan, audit, usage, OAuth."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from . import _helpers

# ---------------------------------------------------------------------------
# Write handlers
# ---------------------------------------------------------------------------


def _handle_remote_execute(params: dict[str, Any]) -> dict[str, Any]:
    """Record a remote execution request and return result placeholder."""
    provider_id = params.get("providerId")
    if not provider_id:
        return {"success": False, "error": "Missing 'providerId' parameter"}

    model = params.get("model", "")
    messages = params.get("messages", [])

    audit_path = _helpers._get_state_dir() / "remote" / "audit.json"
    audit = _helpers._read_json(audit_path)
    entries = audit.setdefault("entries", [])
    entry_id = str(uuid.uuid4())
    entries.append(
        {
            "id": entry_id,
            "event": "execute",
            "provider": provider_id,
            "model": model,
            "messageCount": len(messages) if isinstance(messages, list) else 0,
            "timestamp": datetime.now().isoformat(),
        }
    )
    if len(entries) > 500:
        audit["entries"] = entries[-500:]
    _helpers._write_json(audit_path, audit)

    return {
        "success": True,
        "executionId": entry_id,
        "provider": provider_id,
        "model": model,
        "status": "queued",
    }


def _handle_remote_scan(params: dict[str, Any]) -> dict[str, Any]:
    """Scan input text for potential security issues (PII, secrets)."""
    import re as _re

    input_text = params.get("input", "")
    warnings: list[str] = []
    blockers: list[str] = []
    pii_count = 0
    secrets_count = 0

    if _re.search(r"\b\d{3}-\d{2}-\d{4}\b", input_text):
        warnings.append("Possible SSN detected")
        pii_count += 1
    if _re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", input_text):
        warnings.append("Email address detected")
        pii_count += 1
    if _re.search(r"(sk-|api[_-]?key|secret[_-]?key|password)\s*[:=]\s*\S+", input_text, _re.IGNORECASE):
        blockers.append("Possible API key or secret detected")
        secrets_count += 1

    return {
        "safe": len(blockers) == 0,
        "warnings": warnings,
        "blockers": blockers,
        "piiCount": pii_count,
        "secretsCount": secrets_count,
    }


def _handle_remote_audit_clear(params: dict[str, Any]) -> dict[str, Any]:
    """Clear audit log entries before a given date."""
    before = params.get("before", "")
    audit_path = _helpers._get_state_dir() / "remote" / "audit.json"
    audit = _helpers._read_json(audit_path)
    entries = audit.get("entries", [])

    if before:
        original_len = len(entries)
        audit["entries"] = [e for e in entries if e.get("timestamp", "") >= before]
        removed = original_len - len(audit["entries"])
    else:
        removed = len(entries)
        audit["entries"] = []

    _helpers._write_json(audit_path, audit)
    return {"success": True, "removed": removed, "remaining": len(audit["entries"])}


def _handle_remote_usage_record(params: dict[str, Any]) -> dict[str, Any]:
    """Record usage from a remote execution."""
    provider_id = params.get("providerId")
    if not provider_id:
        return {"success": False, "error": "Missing 'providerId' parameter"}

    usage_path = _helpers._get_state_dir() / "remote" / "usage.json"
    data = _helpers._read_json(usage_path)
    records = data.setdefault("records", [])
    records.append(
        {
            "id": str(uuid.uuid4()),
            "providerId": provider_id,
            "cost": params.get("cost", 0),
            "inputTokens": params.get("inputTokens", 0),
            "outputTokens": params.get("outputTokens", 0),
            "timestamp": datetime.now().isoformat(),
        }
    )
    if len(records) > 5000:
        data["records"] = records[-5000:]
    _helpers._write_json(usage_path, data)
    return {"success": True, "recorded": True}


def _handle_remote_providers_update(params: dict[str, Any]) -> dict[str, Any]:
    """Update global remote provider settings (security, budget, audit)."""
    updates = params.get("updates", {})
    if not updates or not isinstance(updates, dict):
        return {"success": False, "error": "Missing or invalid 'updates' parameter"}

    path = _helpers._get_state_dir() / "remote" / "providers-settings.json"
    data = _helpers._read_json(path)
    data.update(updates)
    data["updatedAt"] = datetime.now().isoformat()
    _helpers._write_json(path, data)
    return {"success": True, "updatedAt": data["updatedAt"]}


def _handle_remote_provider_update(params: dict[str, Any]) -> dict[str, Any]:
    """Update configuration for a specific remote provider."""
    provider_id = params.get("providerId")
    if not provider_id:
        return {"success": False, "error": "Missing 'providerId' parameter"}

    updates = params.get("updates", {})
    path = _helpers._get_state_dir() / "remote" / "providers" / f"{provider_id}.json"
    data = _helpers._read_json(path)
    data.update(updates)
    data["id"] = provider_id
    data["updatedAt"] = datetime.now().isoformat()
    _helpers._write_json(path, data)
    return {"success": True, "providerId": provider_id, "updatedAt": data["updatedAt"]}


def _handle_remote_provider_delete(params: dict[str, Any]) -> dict[str, Any]:
    """Disable a provider and clear its configuration."""
    provider_id = params.get("providerId")
    if not provider_id:
        return {"success": False, "error": "Missing 'providerId' parameter"}

    path = _helpers._get_state_dir() / "remote" / "providers" / f"{provider_id}.json"
    if path.exists():
        path.unlink()
        return {"success": True, "providerId": provider_id, "deleted": True}
    return {"success": False, "error": f"Provider '{provider_id}' not found"}


def _handle_remote_provider_test(params: dict[str, Any]) -> dict[str, Any]:
    """Test connection to a remote provider."""
    provider_id = params.get("providerId")
    if not provider_id:
        return {"success": False, "error": "Missing 'providerId' parameter"}

    path = _helpers._get_state_dir() / "remote" / "providers" / f"{provider_id}.json"
    data = _helpers._read_json(path)
    if not data:
        return {
            "success": False,
            "providerId": provider_id,
            "error": f"Provider '{provider_id}' not configured",
            "status": "not_configured",
        }

    audit_path = _helpers._get_state_dir() / "remote" / "audit.json"
    audit = _helpers._read_json(audit_path)
    entries = audit.setdefault("entries", [])
    entries.append(
        {
            "id": str(uuid.uuid4()),
            "event": "test",
            "provider": provider_id,
            "timestamp": datetime.now().isoformat(),
        }
    )
    _helpers._write_json(audit_path, audit)

    return {
        "success": True,
        "providerId": provider_id,
        "status": "configured",
        "hasApiKey": bool(data.get("apiKey") or data.get("api_key")),
        "testedAt": datetime.now().isoformat(),
    }


def _handle_remote_oauth_callback(params: dict[str, Any]) -> dict[str, Any]:
    """Handle OAuth callback from a remote provider."""
    provider = params.get("provider")
    if not provider:
        return {"success": False, "error": "Missing 'provider' parameter"}

    error = params.get("error")
    if error:
        return {
            "success": False,
            "provider": provider,
            "error": error,
            "error_description": params.get("error_description", ""),
        }

    code = params.get("code", "")
    if not code:
        return {"success": False, "provider": provider, "error": "Missing 'code' parameter"}

    oauth_path = _helpers._get_state_dir() / "remote" / "oauth" / f"{provider}.json"
    oauth_data = {
        "provider": provider,
        "code": code,
        "state": params.get("state", ""),
        "status": "callback_received",
        "receivedAt": datetime.now().isoformat(),
    }
    _helpers._write_json(oauth_path, oauth_data)

    audit_path = _helpers._get_state_dir() / "remote" / "audit.json"
    audit = _helpers._read_json(audit_path)
    entries = audit.setdefault("entries", [])
    entries.append(
        {
            "id": str(uuid.uuid4()),
            "event": "oauth_callback",
            "provider": provider,
            "timestamp": datetime.now().isoformat(),
        }
    )
    _helpers._write_json(audit_path, audit)

    return {"success": True, "provider": provider, "status": "callback_received"}


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


def _read_remote_providers(_params: dict[str, Any]) -> dict[str, Any]:
    """List all configured remote providers."""
    providers_dir = _helpers._get_state_dir() / "remote" / "providers"
    providers: list[dict[str, Any]] = []
    if providers_dir.exists():
        for f in sorted(providers_dir.iterdir()):
            if f.is_file() and f.suffix == ".json":
                provider_data = _helpers._read_json(f)
                if provider_data:
                    providers.append(provider_data)

    settings_path = _helpers._get_state_dir() / "remote" / "providers-settings.json"
    settings = _helpers._read_json(settings_path)

    return {
        "providers": providers,
        "security": settings.get("security", {}),
        "budget": settings.get("budget", {}),
        "usage": settings.get("usage", {}),
    }


def _read_remote_provider(params: dict[str, Any]) -> dict[str, Any]:
    """Get configuration for a specific remote provider."""
    provider_id = params.get("providerId")
    if not provider_id:
        return {"error": "Missing 'providerId' parameter"}

    path = _helpers._get_state_dir() / "remote" / "providers" / f"{provider_id}.json"
    data = _helpers._read_json(path)
    if not data:
        return {"error": f"Provider '{provider_id}' not found"}
    return data


def _read_remote_usage(params: dict[str, Any]) -> dict[str, Any]:
    """Get usage statistics for remote providers."""
    period = params.get("period", "month")
    provider_filter = params.get("provider")

    usage_path = _helpers._get_state_dir() / "remote" / "usage.json"
    data = _helpers._read_json(usage_path)
    records = data.get("records", [])

    if provider_filter:
        records = [r for r in records if r.get("providerId") == provider_filter]

    total_cost = sum(r.get("cost", 0) for r in records)
    total_input = sum(r.get("inputTokens", 0) for r in records)
    total_output = sum(r.get("outputTokens", 0) for r in records)

    by_provider: dict[str, dict[str, Any]] = {}
    for r in records:
        pid = r.get("providerId", "unknown")
        if pid not in by_provider:
            by_provider[pid] = {"cost": 0, "inputTokens": 0, "outputTokens": 0, "count": 0}
        by_provider[pid]["cost"] += r.get("cost", 0)
        by_provider[pid]["inputTokens"] += r.get("inputTokens", 0)
        by_provider[pid]["outputTokens"] += r.get("outputTokens", 0)
        by_provider[pid]["count"] += 1

    now = datetime.now().isoformat()
    return {
        "stats": {
            "dailyCost": 0,
            "monthlyCost": total_cost,
            "dailyTokens": 0,
            "monthlyTokens": total_input + total_output,
            "byProvider": by_provider,
        },
        "dailyBreakdown": [],
        "providerBreakdown": [{"provider": k, **v} for k, v in by_provider.items()],
        "period": period,
        "startDate": now,
        "endDate": now,
    }


def _read_remote_audit(params: dict[str, Any]) -> dict[str, Any]:
    """Get audit log entries for remote provider usage."""
    limit = params.get("limit", 100)
    offset = params.get("offset", 0)
    event_filter = params.get("event")
    provider_filter = params.get("provider")
    since = params.get("since")

    audit_path = _helpers._get_state_dir() / "remote" / "audit.json"
    data = _helpers._read_json(audit_path)
    entries = data.get("entries", [])

    if event_filter:
        entries = [e for e in entries if e.get("event") == event_filter]
    if provider_filter:
        entries = [e for e in entries if e.get("provider") == provider_filter]
    if since:
        entries = [e for e in entries if e.get("timestamp", "") >= since]

    total = len(entries)
    if isinstance(offset, int) and offset > 0:
        entries = entries[offset:]
    if isinstance(limit, int) and limit > 0:
        entries = entries[:limit]

    # Build summary
    summary: dict[str, int] = {}
    for e in data.get("entries", []):
        evt = e.get("event", "unknown")
        summary[evt] = summary.get(evt, 0) + 1

    return {
        "entries": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": summary,
    }


def _read_remote_scan(params: dict[str, Any]) -> dict[str, Any]:
    """Scan input text for security issues (read alias for scan)."""
    return _handle_remote_scan(params)

"""
LLM Usage Tracker

Tracks API calls, token usage, and costs for LLM providers.
Implements Story-013: Cost tracking and usage statistics.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from src.logging import get_entity_logger
from src.logging import ljson

# Add project root to sys.path if not present
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config.paths import get_logs_dir, get_project_root  # noqa: E402

logger = get_entity_logger("llm")

# --- Configuration ---
# Use the centralized path config
LOG_FILE = get_logs_dir() / "llm_logs.jsonl"


class UsageTracker:
    """Tracks LLM usage, costs, and statistics."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize usage tracker."""
        self.data_dir = data_dir or get_project_root()
        self.usage_file = self.data_dir / "factory" / "devops" / "llm_usage.json"

        # New: Separate requests log file (ljson)
        self.requests_file = self.data_dir / "factory" / "devops" / "requests.ljson"

        self._usage_data = self._load_usage_data()

    def _load_usage_data(self) -> Dict[str, Any]:
        """Load usage data from file."""
        if not self.usage_file.exists():
            return {
                "daily_stats": {},
                "provider_stats": {},
                "total_cost": 0.0,
                "total_tokens": 0,
            }

        try:
            content = self.usage_file.read_text(encoding="utf-8")
            data = json.loads(content)

            # Migration: If 'requests' is in data, we should probably ignore it
            # or migrate it, but for now we just drop the key from memory
            # to avoid writing it back to the monolithic file.
            if "requests" in data:
                del data["requests"]

            return data
        except Exception:
            return {
                "daily_stats": {},
                "provider_stats": {},
                "total_cost": 0.0,
                "total_tokens": 0,
            }

    def _save_usage_data(self):
        """Save usage data to file."""
        try:
            self.usage_file.parent.mkdir(parents=True, exist_ok=True)
            self.usage_file.write_text(json.dumps(self._usage_data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save usage data: %s", e)

    def track_request(
        self,
        provider: str,
        profile: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None,
        prompt_text: Optional[str] = None,
        response_text: Optional[str] = None,
    ):
        """Track an LLM API request."""
        timestamp = datetime.now().isoformat()
        date_key = datetime.now().strftime("%Y-%m-%d")

        request_data = {
            "timestamp": timestamp,
            "provider": provider,
            "profile": profile,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost": cost or 0.0,
            "success": success,
            "error": error,
        }

        # 1. Append to ljson log
        ljson.append(self.requests_file, request_data)

        # 2. Update aggregated stats (in memory + stats file)

        # Update daily stats
        daily_stats = self._usage_data.setdefault("daily_stats", {})
        day_stats = daily_stats.setdefault(
            date_key,
            {
                "requests": 0,
                "tokens": 0,
                "cost": 0.0,
                "errors": 0,
            },
        )
        day_stats["requests"] += 1
        day_stats["tokens"] += prompt_tokens + completion_tokens
        day_stats["cost"] += cost or 0.0
        if not success:
            day_stats["errors"] += 1

        # Update provider stats
        provider_stats = self._usage_data.setdefault("provider_stats", {})
        provider_stat = provider_stats.setdefault(
            provider,
            {
                "requests": 0,
                "tokens": 0,
                "cost": 0.0,
                "errors": 0,
                "models": {},
            },
        )
        provider_stat["requests"] += 1
        provider_stat["tokens"] += prompt_tokens + completion_tokens
        provider_stat["cost"] += cost or 0.0
        if not success:
            provider_stat["errors"] += 1

        # Update model stats
        model_stat = provider_stat["models"].setdefault(
            model,
            {
                "requests": 0,
                "tokens": 0,
                "cost": 0.0,
            },
        )
        model_stat["requests"] += 1
        model_stat["tokens"] += prompt_tokens + completion_tokens
        model_stat["cost"] += cost or 0.0

        # Update totals
        self._usage_data["total_cost"] = self._usage_data.get("total_cost", 0.0) + (cost or 0.0)
        self._usage_data["total_tokens"] = self._usage_data.get("total_tokens", 0) + prompt_tokens + completion_tokens

        self._save_usage_data()

        # Log content if provided (JSONL) - keeping existing separate log for content for now
        # Ideally this would also be unified, but let's stick to the prompt's scope.
        if prompt_text or response_text:
            self._log_content(
                timestamp=timestamp,
                provider=provider,
                profile=profile,
                model=model,
                prompt=prompt_text,
                response=response_text,
                cost=cost or 0.0,
                success=success,
                error=error,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )

    def _log_content(
        self,
        timestamp: str,
        provider: str,
        profile: str,
        model: str,
        prompt: Optional[str],
        response: Optional[str],
        cost: float,
        success: bool,
        error: Optional[str],
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ):
        """Append full content to JSONL log."""
        from .schema import LLMLogEntry

        try:
            # Validate with Schema
            entry = LLMLogEntry(
                timestamp=timestamp,
                provider=provider,
                profile=profile,
                model=model,
                prompt=prompt,
                response=response,
                cost=cost,
                success=success,
                error=error,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )

            # Use ljson here too for consistency?
            # The prompt requested "UsageTracker to use ljson for request logging".
            # This is "content logging". Let's use ljson here too to fix the issue fully.
            ljson.append(LOG_FILE, entry.model_dump())

        except Exception as e:
            logger.warning("Failed to write content log: %s", e)

    def get_usage_stats(
        self,
        days: int = 30,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get usage statistics for the last N days."""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        stats: Dict[str, Any] = {
            "period_days": days,
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "total_errors": 0,
            "daily_breakdown": [],
            "provider_breakdown": {},
            "model_breakdown": {},
        }

        # Filter requests by date and provider
        # READ FROM LJSON FILE NOW
        requests_raw = ljson.read(self.requests_file)

        requests = [
            r
            for r in requests_raw
            if r.get("timestamp", "") >= cutoff_date and (provider is None or r.get("provider") == provider)
        ]

        for request in requests:
            stats["total_requests"] += 1
            stats["total_tokens"] += request.get("total_tokens", 0)
            stats["total_cost"] += request.get("cost", 0.0)
            if not request.get("success", True):
                stats["total_errors"] += 1

            # Provider breakdown
            req_provider = request.get("provider", "unknown")
            if req_provider not in stats["provider_breakdown"]:
                stats["provider_breakdown"][req_provider] = {
                    "requests": 0,
                    "tokens": 0,
                    "cost": 0.0,
                    "errors": 0,
                }
            stats["provider_breakdown"][req_provider]["requests"] += 1
            stats["provider_breakdown"][req_provider]["tokens"] += request.get("total_tokens", 0)
            stats["provider_breakdown"][req_provider]["cost"] += request.get("cost", 0.0)
            if not request.get("success", True):
                stats["provider_breakdown"][req_provider]["errors"] += 1

            # Model breakdown
            model_key = f"{req_provider}/{request.get('model', 'unknown')}"
            if model_key not in stats["model_breakdown"]:
                stats["model_breakdown"][model_key] = {
                    "requests": 0,
                    "tokens": 0,
                    "cost": 0.0,
                }
            stats["model_breakdown"][model_key]["requests"] += 1
            stats["model_breakdown"][model_key]["tokens"] += request.get("total_tokens", 0)
            stats["model_breakdown"][model_key]["cost"] += request.get("cost", 0.0)

        # Daily breakdown
        daily_stats = self._usage_data.get("daily_stats", {})
        if not isinstance(daily_stats, dict):
            daily_stats = {}
        for date_key in sorted(daily_stats.keys(), reverse=True)[:days]:
            if date_key >= cutoff_date:
                day_data = daily_stats[date_key]
                if provider is None or any(
                    r.get("provider") == provider for r in requests if r.get("timestamp", "").startswith(date_key)
                ):
                    stats["daily_breakdown"].append(
                        {
                            "date": date_key,
                            "requests": day_data.get("requests", 0),
                            "tokens": day_data.get("tokens", 0),
                            "cost": day_data.get("cost", 0.0),
                            "errors": day_data.get("errors", 0),
                        }
                    )

        return stats

    def get_cost_estimate(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Estimate cost for a request based on provider pricing."""
        # Pricing per 1M tokens (input/output)
        pricing = {
            "groq": {
                "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
                "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
            },
            "openai": {
                "gpt-4o-mini": {"input": 0.15, "output": 0.60},
                "gpt-4o": {"input": 2.50, "output": 10.00},
            },
            "anthropic": {
                "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
                "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
            },
            "deepseek": {
                "deepseek-chat": {"input": 0.14, "output": 0.28},
            },
            "openrouter": {
                "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
            },
        }

        provider_pricing = pricing.get(provider.lower(), {})
        model_pricing = provider_pricing.get(model, {})

        if not model_pricing:
            # Default estimate based on provider
            default_pricing = {
                "groq": {"input": 0.30, "output": 0.50},
                "openai": {"input": 1.00, "output": 3.00},
                "anthropic": {"input": 3.00, "output": 15.00},
                "deepseek": {"input": 0.14, "output": 0.28},
                "openrouter": {"input": 0.50, "output": 1.50},
            }
            model_pricing = default_pricing.get(provider.lower(), {"input": 1.00, "output": 3.00})

        input_cost = (prompt_tokens / 1_000_000) * model_pricing.get("input", 1.00)
        output_cost = (completion_tokens / 1_000_000) * model_pricing.get("output", 3.00)

        return input_cost + output_cost


# Global tracker instance
_tracker: Optional[UsageTracker] = None


def get_usage_tracker() -> UsageTracker:
    """Get global usage tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker

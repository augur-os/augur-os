#!/usr/bin/env python3
"""
Notification Service - Proactive notifications horizontal for Augur.

Enables all verticals to send notifications via multiple channels:
- System native notifications (macOS, Windows, Linux)
- Slack webhooks
- Email (SMTP)

Usage:
    from notification_service import NotificationService

    service = NotificationService()
    service.send("Hello from Augur!")
    service.remind("Follow up with recruiter", in_minutes=60 * 24 * 3)  # 3 days
"""
# TODO_CLEANUP: This file is 812 lines — consider splitting into smaller modules

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import CompletedProcess, run  # nosec B404
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path to absolute when available."""
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if not resolved:
        return command

    return [resolved, *command[1:]]


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess:
    """Run subprocess command with resolved executable."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


def _windows_backend_from_stdout(stdout: object) -> str:
    """Extract the Windows toast backend marker emitted by the PowerShell fallback."""
    if not isinstance(stdout, str):
        return "powershell"

    marker = "AUGUR_BACKEND:"
    for line in stdout.splitlines():
        value = line.strip()
        if not value.startswith(marker):
            continue
        backend = value.removeprefix(marker).strip().lower()
        if backend in {"burnttoast", "winrt"}:
            return backend
    return "powershell"


try:
    from bootstrap_paths import ensure_project_paths
except ImportError:
    _SCRIPTS_DIR = Path(__file__).resolve().parent
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    from bootstrap_paths import ensure_project_paths

project_root = ensure_project_paths(__file__)

from src.config.paths import get_project_port

try:
    from runtime_paths import (
        get_notification_history_path,
        get_notification_pending_path,
        get_notification_preferences_path,
        get_notifications_runtime_dir,
    )
except ImportError:
    from src.lib.skill_paths import get_own_data_dir

    def get_notifications_runtime_dir() -> Path:
        return get_own_data_dir(__file__) / "notifications"

    def get_notification_pending_path() -> Path:
        return get_notifications_runtime_dir() / "pending.yaml"

    def get_notification_history_path() -> Path:
        return get_notifications_runtime_dir() / "history.yaml"

    def get_notification_preferences_path() -> Path:
        return get_notifications_runtime_dir() / "preferences.yaml"


@dataclass
class ScheduledNotification:
    """A scheduled notification."""

    id: str
    message: str
    channel: str
    scheduled_for: datetime
    created_at: datetime = field(default_factory=datetime.now)
    vertical: str = ""
    recurring: Optional[str] = None  # "daily", "weekly", None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "message": self.message,
            "channel": self.channel,
            "scheduled_for": self.scheduled_for.isoformat(),
            "created_at": self.created_at.isoformat(),
            "vertical": self.vertical,
            "recurring": self.recurring,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledNotification":
        return cls(
            id=data["id"],
            message=data["message"],
            channel=data["channel"],
            scheduled_for=datetime.fromisoformat(data["scheduled_for"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            vertical=data.get("vertical", ""),
            recurring=data.get("recurring"),
        )


@dataclass
class NotificationResult:
    """Result of sending a notification."""

    success: bool
    channel: str
    message: str = ""
    error: Optional[str] = None
    backend: str = ""


class NotificationService:
    """
    Horizontal notification service for proactive agents.

    Provides multi-channel notifications:
    - System: Native notifications (macOS, Windows, Linux)
    - Slack: Webhook-based messaging
    - Email: SMTP-based email (uses existing telemetry pattern)
    """

    def __init__(self, data_dir: Path | None = None):
        if data_dir:
            self.data_dir = data_dir
            self.pending_file = self.data_dir / "pending.yaml"
            self.history_file = self.data_dir / "history.yaml"
            self.preferences_file = self.data_dir / "preferences.yaml"
        else:
            self.data_dir = get_notifications_runtime_dir()
            self.pending_file = get_notification_pending_path()
            self.history_file = get_notification_history_path()
            self.preferences_file = get_notification_preferences_path()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._system = platform.system()
        self._cooldowns: dict[str, datetime] = {}  # Track last notification per category

        # Load preferences
        self._preferences = self._load_preferences()

        # Default channel - use "system" for cross-platform native notifications
        self.default_channels = self._preferences.get("default_channels", ["system"])

    def _load_preferences(self) -> dict:
        """Load notification preferences from YAML file."""
        if self.preferences_file.exists():
            try:
                with open(self.preferences_file) as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {"enabled": True, "default_channels": ["system"]}
        return {"enabled": True, "default_channels": ["system"]}

    def _is_in_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        quiet = self._preferences.get("quiet_hours", {})
        if not quiet.get("enabled"):
            return False

        try:
            now = datetime.now()
            start_str = quiet.get("start", "22:00")
            end_str = quiet.get("end", "08:00")
            start_h, start_m = map(int, start_str.split(":"))
            end_h, end_m = map(int, end_str.split(":"))

            current_minutes = now.hour * 60 + now.minute
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m

            # Handle overnight quiet hours (e.g., 22:00 - 08:00)
            if start_minutes > end_minutes:
                return current_minutes >= start_minutes or current_minutes < end_minutes
            return start_minutes <= current_minutes < end_minutes
        except Exception:
            return False

    def _check_category_enabled(self, category: str) -> bool:
        """Check if notifications are enabled for a category."""
        if not self._preferences.get("enabled", True):
            return False

        categories = self._preferences.get("categories", {})
        cat_config = categories.get(category, {})
        return cat_config.get("enabled", True)

    def _check_cooldown(self, category: str) -> bool:
        """Check if we're within cooldown period for a category. Returns True if should send."""
        categories = self._preferences.get("categories", {})
        cat_config = categories.get(category, {})
        cooldown_secs = cat_config.get("cooldown", 0)

        if cooldown_secs <= 0:
            return True

        last_sent = self._cooldowns.get(category)
        if last_sent is None:
            return True

        return (datetime.now() - last_sent).total_seconds() >= cooldown_secs

    def _record_notification(self, category: str) -> None:
        """Record that a notification was sent for cooldown tracking."""
        self._cooldowns[category] = datetime.now()

    def _get_channels_for_category(self, category: str) -> list[str]:
        """Get the notification channels for a category."""
        categories = self._preferences.get("categories", {})
        cat_config = categories.get(category, {})
        return cat_config.get("channels", self.default_channels)

    def notify(
        self,
        message: str,
        category: str,
        event: str = "",
        title: str = "Augur",
        open_url: str = "",
        copy_text: str = "",
    ) -> list[NotificationResult]:
        """
        Send a notification respecting user preferences.

        This is the preferred method for daemon monitors to send notifications.
        It checks:
        - Global enabled flag
        - Quiet hours
        - Category-specific settings
        - Event filtering
        - Cooldown periods

        Args:
            message: Notification message
            category: Category (dashboard, mcp, runtime, tech_debt)
            event: Specific event type (e.g., "crash", "stalled")
            title: Notification title

        Returns:
            List of NotificationResult for each channel attempted
        """
        results = []

        # Check global enabled
        if not self._preferences.get("enabled", True):
            return [NotificationResult(success=False, channel="none", error="Notifications disabled")]

        # Check quiet hours
        if self._is_in_quiet_hours():
            return [NotificationResult(success=False, channel="none", error="Quiet hours active")]

        # Check category enabled
        if not self._check_category_enabled(category):
            return [
                NotificationResult(
                    success=False,
                    channel="none",
                    error=f"Category '{category}' disabled",
                )
            ]

        # Check event filter (if specified)
        categories = self._preferences.get("categories", {})
        cat_config = categories.get(category, {})
        allowed_events = cat_config.get("events", [])
        if allowed_events and event and event not in allowed_events:
            return [
                NotificationResult(
                    success=False,
                    channel="none",
                    error=f"Event '{event}' not in allowed list",
                )
            ]

        # Check cooldown
        if not self._check_cooldown(category):
            return [
                NotificationResult(
                    success=False,
                    channel="none",
                    error=f"Category '{category}' in cooldown",
                )
            ]

        # Send to all configured channels for this category
        channels = self._get_channels_for_category(category)
        for channel in channels:
            result = self.send(message, channel=channel, title=title, open_url=open_url, copy_text=copy_text)
            results.append(result)

        # Record notification for cooldown
        if any(r.success for r in results):
            self._record_notification(category)

        return results

    def send(
        self,
        message: str,
        channel: str = "system",
        title: str = "Augur",
        open_url: str = "",
        copy_text: str = "",
    ) -> NotificationResult:
        """
        Send an immediate notification (low-level, bypasses preferences).

        For preference-aware notifications, use notify() instead.

        Args:
            message: Notification message
            channel: Target channel (system, macos, windows, slack, email)
            title: Notification title

        Returns:
            NotificationResult with success status
        """
        # Map "system" to platform-specific channel
        if channel == "system":
            if self._system == "Darwin":
                channel = "macos"
            elif self._system == "Windows":
                channel = "windows"
            else:
                channel = "linux"

        # Also accept legacy "macos" on macOS
        if channel == "macos":
            return self._send_macos(message, title, open_url=open_url, copy_text=copy_text)
        elif channel == "windows":
            return self._send_windows(message, title)
        elif channel == "linux":
            return self._send_linux(message, title)
        elif channel == "slack":
            return self._send_slack(message)
        elif channel == "email":
            return self._send_email(message, title)
        else:
            return NotificationResult(success=False, channel=channel, error=f"Unknown channel: {channel}")

    def _send_macos(
        self,
        message: str,
        title: str = "Augur",
        open_url: str = "",
        copy_text: str = "",
    ) -> NotificationResult:
        """Send macOS native notification.

        Prefers terminal-notifier (supports click actions) with
        osascript as fallback.  Install terminal-notifier via:
            brew install terminal-notifier

        When copy_text is provided, clicking the notification copies it
        to clipboard via pbcopy (instead of opening a URL).
        """
        # Try terminal-notifier first (supports -open and -execute)
        tn_path = shutil.which("terminal-notifier")
        if tn_path:
            try:
                cmd = [
                    tn_path,
                    "-title",
                    title,
                    "-message",
                    message[:200],
                    "-group",
                    "augur",
                    "-sound",
                    "default",
                ]

                if copy_text:
                    # Click copies error context to clipboard via pbcopy
                    safe_text = copy_text.replace("'", "'\\''")
                    cmd.extend(["-execute", f"printf '%s' '{safe_text}' | pbcopy"])
                elif open_url:
                    cmd.extend(["-open", open_url])
                else:
                    cmd.extend(["-open", f"http://localhost:{get_project_port()}/observe"])

                _run_command(cmd, capture_output=True, timeout=5)
                self._log_notification("macos", message, success=True)
                return NotificationResult(success=True, channel="macos", message=message)
            except Exception:
                pass  # Fall through to osascript

        # Fallback: osascript (no click action, but still shows notification)
        try:
            safe_message = message.replace('"', '\\"')
            safe_title = title.replace('"', '\\"')
            script = f'display notification "{safe_message}" with title "{safe_title}"'
            _run_command(["osascript", "-e", script], capture_output=True, timeout=5)
            self._log_notification("macos", message, success=True)
            return NotificationResult(success=True, channel="macos", message=message)
        except Exception as e:
            return NotificationResult(success=False, channel="macos", error=str(e))

    def _send_windows(self, message: str, title: str = "Augur") -> NotificationResult:
        """Send Windows toast notification."""
        # Try plyer first (cross-platform library)
        try:
            from plyer import notification as plyer_notification

            plyer_notification.notify(
                title=title,
                message=message,
                app_name="Augur",
                timeout=10,
            )
            self._log_notification("windows", message, success=True)
            return NotificationResult(success=True, channel="windows", message=message, backend="plyer")
        except ImportError:
            _ = False
        except Exception:
            # plyer failed, try PowerShell fallback
            _ = True

        # Fallback: PowerShell BurntToast or built-in toast
        try:
            # Escape quotes for PowerShell
            safe_message = message.replace("'", "''").replace('"', '`"')
            safe_title = title.replace("'", "''").replace('"', '`"')

            # Try BurntToast module first (richer notifications)
            ps_script = f"""
            $ErrorActionPreference = 'Stop'
            if (Get-Module -ListAvailable -Name BurntToast) {{
                Write-Output 'AUGUR_BACKEND:burnttoast'
                New-BurntToastNotification -Text '{safe_title}', '{safe_message}'
            }} else {{
                Write-Output 'AUGUR_BACKEND:winrt'
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
                $template = '<toast><visual><binding template="ToastText02"><text id="1">{safe_title}</text><text id="2">{safe_message}</text></binding></visual></toast>'
                $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
                $xml.LoadXml($template)
                $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Augur').Show($toast)
            }}
            """

            result = _run_command(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10,
            )

            backend = _windows_backend_from_stdout(result.stdout)
            if result.returncode == 0:
                self._log_notification("windows", message, success=True)
                return NotificationResult(success=True, channel="windows", message=message, backend=backend)
            else:
                return NotificationResult(
                    success=False,
                    channel="windows",
                    error=f"PowerShell error: {(result.stderr or '').strip()}",
                    backend=backend,
                )
        except Exception as e:
            return NotificationResult(success=False, channel="windows", backend="powershell", error=str(e))

    def _send_linux(self, message: str, title: str = "Augur") -> NotificationResult:
        """Send Linux notification via notify-send or plyer."""
        # Try plyer first
        try:
            from plyer import notification as plyer_notification

            plyer_notification.notify(
                title=title,
                message=message,
                app_name="Augur",
                timeout=10,
            )
            self._log_notification("linux", message, success=True)
            return NotificationResult(success=True, channel="linux", message=message)
        except ImportError:
            _ = False
        except Exception:
            _ = True

        # Fallback: notify-send (requires libnotify)
        try:
            _run_command(
                ["notify-send", title, message],
                capture_output=True,
                timeout=5,
            )
            self._log_notification("linux", message, success=True)
            return NotificationResult(success=True, channel="linux", message=message)
        except Exception as e:
            return NotificationResult(success=False, channel="linux", error=str(e))

    def _send_slack(self, message: str) -> NotificationResult:
        """Send Slack notification via webhook."""
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

        if not webhook_url:
            return NotificationResult(success=False, channel="slack", error="SLACK_WEBHOOK_URL not configured")

        try:
            payload = json.dumps({"text": f"🧠 *Augur*: {message}"}).encode("utf-8")
            req = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})

            with urlopen(req, timeout=10) as response:  # nosec B310
                if response.status == 200:
                    self._log_notification("slack", message, success=True)
                    return NotificationResult(success=True, channel="slack", message=message)
                else:
                    return NotificationResult(success=False, channel="slack", error=f"HTTP {response.status}")
        except URLError as e:
            return NotificationResult(success=False, channel="slack", error=str(e))

    def _send_email(self, message: str, subject: str = "Augur Notification") -> NotificationResult:
        """Send email notification via SMTP."""
        import smtplib
        from email.mime.text import MIMEText

        email_prefs = self._preferences.get("email", {})
        smtp_host = email_prefs.get("smtp_host") or os.environ.get("SMTP_HOST", "")
        smtp_port = int(email_prefs.get("smtp_port", 0)) or int(os.environ.get("SMTP_PORT", "587"))
        recipient = email_prefs.get("recipient") or os.environ.get("ALERT_EMAIL", "")

        if not smtp_host or not recipient:
            return NotificationResult(
                success=False,
                channel="email",
                error="Email not configured — set smtp_host and recipient in preferences",
            )

        try:
            msg = MIMEText(message, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = f"Augur <augur@{smtp_host}>"
            msg["To"] = recipient

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.ehlo()
                if smtp_port != 25:
                    server.starttls()
                    server.ehlo()
                server.sendmail(msg["From"], [recipient], msg.as_string())

            self._log_notification("email", message, success=True)
            return NotificationResult(success=True, channel="email", message=message)
        except Exception as e:
            return NotificationResult(success=False, channel="email", error=str(e))

    def remind(self, message: str, in_minutes: int, channel: str = "macos", vertical: str = "") -> str:
        """
        Schedule a reminder notification.

        Args:
            message: Reminder message
            in_minutes: Minutes from now to send
            channel: Target channel
            vertical: Source vertical (for tracking)

        Returns:
            Reminder ID
        """
        reminder_id = str(uuid.uuid4())[:8]
        scheduled_for = datetime.now() + timedelta(minutes=in_minutes)

        notification = ScheduledNotification(
            id=reminder_id,
            message=message,
            channel=channel,
            scheduled_for=scheduled_for,
            vertical=vertical,
        )

        self._save_pending(notification)

        return reminder_id

    def cancel(self, notification_id: str) -> bool:
        """Cancel a pending notification."""
        pending = self._load_pending()

        updated = [n for n in pending if n.id != notification_id]

        if len(updated) < len(pending):
            self._save_all_pending(updated)
            return True

        return False

    def get_pending(self) -> list[ScheduledNotification]:
        """Get all pending notifications."""
        return self._load_pending()

    def get_due(self) -> list[ScheduledNotification]:
        """Get notifications that are due now."""
        now = datetime.now()
        pending = self._load_pending()
        return [n for n in pending if n.scheduled_for <= now]

    def process_due(self) -> list[NotificationResult]:
        """
        Process and send all due notifications.

        This should be called periodically (e.g., every minute by a cron/launchd).
        """
        results = []
        due = self.get_due()

        for notification in due:
            result = self.send(notification.message, notification.channel)
            results.append(result)

            if result.success:
                # Remove from pending (or reschedule if recurring)
                if notification.recurring == "daily":
                    notification.scheduled_for += timedelta(days=1)
                    self._save_pending(notification)
                elif notification.recurring == "weekly":
                    notification.scheduled_for += timedelta(weeks=1)
                    self._save_pending(notification)
                else:
                    self.cancel(notification.id)

        return results

    def _load_pending(self) -> list[ScheduledNotification]:
        """Load pending notifications from file."""
        if not self.pending_file.exists():
            return []

        try:
            with open(self.pending_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            return [ScheduledNotification.from_dict(n) for n in data.get("pending", [])]
        except Exception:
            return []

    def _save_pending(self, notification: ScheduledNotification):
        """Add a notification to pending list."""
        pending = self._load_pending()

        # Update existing or add new
        existing_ids = {n.id for n in pending}
        if notification.id in existing_ids:
            pending = [n if n.id != notification.id else notification for n in pending]
        else:
            pending.append(notification)

        self._save_all_pending(pending)

    def _save_all_pending(self, notifications: list[ScheduledNotification]):
        """Save all pending notifications."""
        data = {
            "pending": [n.to_dict() for n in notifications],
            "updated": datetime.now().isoformat(),
        }

        with open(self.pending_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False)

    def _log_notification(self, channel: str, message: str, success: bool):
        """Log sent notification to history."""
        history = []
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                history = data.get("history", [])
            except Exception:
                history = []

        history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "channel": channel,
                "message": message[:100],
                "success": success,
            }
        )

        # Keep last 100
        history = history[-100:]

        with open(self.history_file, "w", encoding="utf-8") as f:
            yaml.safe_dump({"history": history}, f, default_flow_style=False)


# Convenience functions
def notify(message: str, channel: str = "system") -> NotificationResult:
    """Send an immediate notification (uses native system notifications)."""
    return NotificationService().send(message, channel)


def remind(message: str, in_minutes: int, channel: str = "system") -> str:
    """Schedule a reminder (uses native system notifications)."""
    return NotificationService().remind(message, in_minutes, channel)


def _run_loop(interval_seconds: int = 60) -> None:
    """Process due notifications in a loop (used by unified daemon)."""
    import time

    service = NotificationService()
    _out(f"Notification processor started (interval={interval_seconds}s)")

    while True:
        try:
            due = service.get_due()
            if due:
                results = service.process_due()
                sent = sum(1 for r in results if r.success)
                _out(f"Processed {len(due)} due notifications ({sent} sent)")
            else:
                pass  # No due notifications — silent
        except Exception as e:
            _out(f"Error processing notifications: {e}", file=sys.stderr)

        time.sleep(interval_seconds)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Augur Notification Service")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop mode (used by daemon)")
    parser.add_argument("--process-due", action="store_true", help="Process due notifications once and exit")
    args = parser.parse_args()

    if args.loop:
        _run_loop()
    elif args.process_due:
        service = NotificationService()
        due = service.get_due()
        if due:
            results = service.process_due()
            sent = sum(1 for r in results if r.success)
            _out(f"Processed {len(due)} due ({sent} sent)")
        else:
            _out("No due notifications")
    else:
        # Default: test mode
        _out("Testing Notification Service")
        _out("=" * 50)
        _out(f"Platform: {platform.system()}")

        service = NotificationService()

        _out("\n--- Sending System Notification ---")
        result = service.send("Test notification from Augur!", channel="system")
        _out(f"  Channel: {result.channel}")
        _out(f"  Success: {result.success}")
        if result.error:
            _out(f"  Error: {result.error}")

        _out("\n--- Scheduling Reminder ---")
        reminder_id = service.remind("This is a test reminder!", in_minutes=1)
        _out(f"  Reminder ID: {reminder_id}")

        _out("\n--- Pending Notifications ---")
        pending = service.get_pending()
        for n in pending:
            _out(f"  [{n.id}] {n.message} @ {n.scheduled_for}")

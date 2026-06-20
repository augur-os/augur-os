#!/usr/bin/env python3
"""
Verify API Endpoints
-------------------
Tests connectivity to the Dashboard Backend API endpoints.
Use this to debug the Python backend layer without reloading the UI.
"""

import json
import sys
import time
from typing import Any, Optional

import requests

BASE_URL = "http://localhost:3000"

COLORS = {
    "HEADER": "\033[95m",
    "OKBLUE": "\033[94m",
    "OKCYAN": "\033[96m",
    "OKGREEN": "\033[92m",
    "WARNING": "\033[93m",
    "FAIL": "\033[91m",
    "ENDC": "\033[0m",
    "BOLD": "\033[1m",
}


def print_status(name: str, status: str, details: str = "") -> None:
    """Print endpoint test result with color-coded status."""
    color = COLORS["OKGREEN"] if status == "PASS" else COLORS["FAIL"]
    print(f"{name:<20} [{color}{status}{COLORS['ENDC']}] {details}")


def test_endpoint(name: str, path: str, method: str = "GET", data: Optional[dict[str, Any]] = None) -> bool:
    """Test a single API endpoint and print result."""
    url = f"{BASE_URL}{path}"
    try:
        start_time = time.time()
        response = requests.request(method, url, json=data, timeout=5)
        latency = (time.time() - start_time) * 1000
        response.raise_for_status()
        content = response.text
        try:
            json_content = json.loads(content)
            status_msg = f"{latency:.0f}ms"

            # Check for specific success indicators
            if "error" in json_content:
                print_status(name, "FAIL", f"Error in response: {json_content['error']}")
                return False

            print_status(name, "PASS", status_msg)
            return True
        except json.JSONDecodeError:
            print_status(name, "PASS", f"{latency:.0f}ms (Non-JSON)")
            return True

    except requests.exceptions.RequestException as e:
        print_status(name, "FAIL", str(e))
        return False
    except (json.JSONDecodeError, ValueError) as e:
        # Shouldn't happen since we already handle JSONDecodeError above,
        # but catch any parsing edge cases
        print_status(name, "FAIL", f"Parse error: {e}")
        return False


def main() -> None:
    """Run API endpoint connectivity tests."""
    print(f"{COLORS['HEADER']}=== Augur API Connectivity Check ==={COLORS['ENDC']}")
    print(f"Target: {BASE_URL}\n")

    # 1. Check Root (Next.js)
    if not test_endpoint("Dashboard Root", "/"):
        print(f"\n{COLORS['FAIL']}Critical: Dashboard is not running at {BASE_URL}{COLORS['ENDC']}")
        sys.exit(1)

    # 2. Check Control/Agent Endpoints (Real Backend)
    print(f"\n{COLORS['BOLD']}Checking Backend API (Python/MCP)...{COLORS['ENDC']}")
    test_endpoint("Agent Status", "/api/agents/status")
    test_endpoint("MCP Context", "/api/mcp/context/stats")

    # 3. Check IDE Bridge
    test_endpoint("IDE Bridge", "/api/ide/status")

    # 4. Agent Routing (POST Test)
    routing_payload = {"task": "Test connectivity", "context_preset": "lightweight"}
    test_endpoint("Agent Routing", "/api/agents/route", method="POST", data=routing_payload)

    # 5. Terminal Automation Connectivity
    print(f"\n{COLORS['BOLD']}Checking Terminal Automation Endpoints...{COLORS['ENDC']}")

    # Terminal Status (No creds needed)
    test_endpoint("Term Execute (Status)", "/api/terminal-automation-template/terminal/execute", method="POST", data={"action": "status"})

    # Automation (Mock run)
    automation_payload = {
        "automationId": "create-invoices",
        "credentials": {"host": "localhost", "username": "test", "password": "pwd"},
    }
    test_endpoint("Run Automation", "/api/terminal-automation-template/automations", method="POST", data=automation_payload)


if __name__ == "__main__":
    main()

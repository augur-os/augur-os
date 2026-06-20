"""Code-quality auto-command modules (ADR-200).

Each module implements the OpsCommand protocol (scan/fix) for one
code-quality category. The adaptive engine discovers these via
augur.yaml `protocol: scan-fix` entries.
"""

#!/usr/bin/env python3
import sys
import yaml
from pathlib import Path
import argparse
import json

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "agentic_tools.yaml"


def read_catalog():
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, 'r') as f:
        return yaml.safe_load(f)


def write_catalog(data):
    # Ensure parent directory exists
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def main():
    parser = argparse.ArgumentParser(description="Manage Agentic Tools Catalog")
    parser.add_argument("--action", choices=["read", "update"], default="read")
    parser.add_argument("--data", help="JSON string for update action")

    args = parser.parse_args()

    if args.action == "read":
        try:
            catalog = read_catalog()
            sys.stdout.write(f"{json.dumps(catalog)}\n")
        except Exception as e:
            # Fallback for errors
            sys.stdout.write(f"{json.dumps({'error': str(e)})}\n")

    elif args.action == "update":
        if not args.data:
            sys.stdout.write(f"{json.dumps({'success': False, 'error': '--data is required for update action'})}\n")
            sys.exit(1)
        try:
            new_data = json.loads(args.data)
            write_catalog(new_data)
            sys.stdout.write(f"{json.dumps({'success': True})}\n")
        except Exception as e:
            sys.stdout.write(f"{json.dumps({'success': False, 'error': str(e)})}\n")


if __name__ == "__main__":
    main()

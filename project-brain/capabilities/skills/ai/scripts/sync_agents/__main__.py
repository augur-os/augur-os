"""
Entry point for running the sync_agents package via python -m:
    PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync all
"""

import os
import sys

# Support both `python -m sync_agents` (relative import) and direct execution
try:
    from . import main
except ImportError:
    # Running directly (not as package) — add parent to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from sync_agents import main

sys.exit(main())

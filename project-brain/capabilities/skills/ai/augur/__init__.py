"""Bootstrap package imports for the canonical AI skill tree.

Several legacy modules inside ``skills/ai/augur`` still import sibling
packages as top-level ``lib`` / ``adapters`` modules. Ensure the augur skill
root is on ``sys.path`` so those imports resolve from the canonical skill tree
rather than an old plugin package.
"""

from __future__ import annotations

import sys
from pathlib import Path

_AUGUR_ROOT = Path(__file__).resolve().parent
if str(_AUGUR_ROOT) not in sys.path:
    sys.path.insert(0, str(_AUGUR_ROOT))

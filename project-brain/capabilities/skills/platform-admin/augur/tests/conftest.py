import sys
from pathlib import Path

# Add package root to path at module level so imports resolve during collection
pkg_root = Path(__file__).parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

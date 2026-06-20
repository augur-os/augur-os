
import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import argparse
import json
import sys
from pathlib import Path


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Setup paths
PLUGIN_ROOT = Path(__file__).parent.parent

try:
    from src.config.paths import get_project_root
    AUGUR_ROOT = get_project_root()
except ImportError:
    AUGUR_ROOT = PLUGIN_ROOT.parent.parent.parent.parent  # fallback

if str(AUGUR_ROOT) not in sys.path:
    sys.path.insert(0, str(AUGUR_ROOT))

# Global flag for module availability
UNIFIED_SEARCH_AVAILABLE = False
try:
    from src.lib.knowledge.unified_search import UnifiedSearcher

    UNIFIED_SEARCH_AVAILABLE = True
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(description='RAG Reasoning CLI — unified cross-scope search')
    parser.add_argument('--query', '-q', required=True, help='Search query')
    parser.add_argument('--scopes', '-s', default=None, help='Comma-separated scopes (memory,knowledge,skills,rag,decisions)')
    parser.add_argument('--max-results', '-n', type=int, default=10, help='Max results')

    args = parser.parse_args()

    if not UNIFIED_SEARCH_AVAILABLE:
        _out(
            json.dumps(
                {
                    "success": False,
                    "error": "UnifiedSearcher unavailable (src.lib.knowledge.unified_search).",
                }
            )
        )
        return

    scopes = [s.strip() for s in args.scopes.split(',')] if args.scopes else None

    try:
        searcher = UnifiedSearcher(scopes=scopes)
        results = searcher.search(
            query=args.query,
            scopes=scopes,
            top_k=args.max_results,
        )
        _out(json.dumps({
            "success": True,
            "query": args.query,
            "scopes": scopes or ["memory", "knowledge", "skills", "rag", "decisions"],
            "result_count": len(results),
            "results": results,
        }, default=str))

    except Exception as e:
        _out(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == '__main__':
    main()

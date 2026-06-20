#!/usr/bin/env python3
"""
Re-run RAG Analysis and Regenerate Dashboard

This script re-runs RAG analysis for an existing skill and regenerates the dashboard
with proper context from analyzed content.
"""

import sys
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add project root to path
try:
    from src.config.paths import get_project_root
    sys.path.insert(0, str(get_project_root()))
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  # fallback

from ..analyze_rag_content import analyze_content  # noqa: E402
from ..comprehensive_dashboard_generator import generate_comprehensive_dashboard  # noqa: E402


def index_folder_for_rag(folder_path: str, rag_project_id: str) -> Dict[str, Any]:
    """Index a folder for RAG analysis."""
    try:
        # Determine paths
        try:
            from src.config.paths import get_project_root as _get_root
            repo_root = _get_root()
        except ImportError:
            repo_root = Path(__file__).parent.parent.parent.parent  # fallback
        plugins_dir = repo_root / 'plugins'

        # Add plugins to path for imports
        if str(plugins_dir) not in sys.path:
            sys.path.insert(0, str(plugins_dir))

        # Determine data directory
        import os

        data_root = os.environ.get('AUGUR_ROOT') or str(Path.home() / 'Projects' / 'augur')

        user_data_dir = str(Path(data_root) / 'local-rag' / 'projects' / rag_project_id)

        # Initialize Indexer
        try:
            from horizontal.memory.local_rag.services.index_service import DocumentIndexer
        except ImportError:
            from plugins.horizontal.memory.local_rag.services.index_service import DocumentIndexer

        indexer = DocumentIndexer(user_data_dir=user_data_dir)

        folder_path_obj = Path(folder_path)
        if not folder_path_obj.exists():
            return {'error': f'Folder not found: {folder_path}'}

        _out(f"Indexing folder: {folder_path}")
        stats = indexer.index_directory(folder_path_obj, force=True)  # Force re-index
        _out(f"Indexing complete: {stats['files_processed']} files processed")

        return {'success': True, 'stats': stats}

    except ImportError as e:
        return {'error': f'RAG dependencies not available: {e}'}
    except Exception as e:
        import traceback

        traceback.print_exc()
        return {'error': f'Failed to index folder: {e}'}


def fetch_website_content(url: str) -> Optional[str]:
    """Fetch content from a website URL."""
    try:
        import urllib.request
        import html2text

        _out(f"Fetching website content from: {url}")
        with urllib.request.urlopen(url, timeout=10) as response:  # nosec B310
            html_content = response.read().decode('utf-8')

        # Convert HTML to text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        text_content = h.handle(html_content)

        return text_content
    except ImportError:
        _out("Warning: html2text not available. Install with: pip install html2text")
        return None
    except Exception as e:
        _out(f"Warning: Failed to fetch website: {e}")
        return None


def save_website_content_to_temp(url: str, rag_project_id: str) -> Optional[str]:
    """Save website content to a temporary file for indexing."""
    content = fetch_website_content(url)
    if not content:
        return None

    import os

    data_root = os.environ.get('AUGUR_ROOT') or str(Path.home() / 'Projects' / 'augur')

    temp_dir = Path(data_root) / 'local-rag' / 'projects' / rag_project_id / 'temp'
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Extract domain from URL
    from urllib.parse import urlparse

    domain = urlparse(url).netloc.replace('.', '_')

    temp_file = temp_dir / f'{domain}.md'
    temp_file.write_text(f"# Website Content: {url}\n\n{content}", encoding='utf-8')

    return str(temp_dir)


def rerun_rag_analysis(
    skill_name: str,
    folder_path: Optional[str] = None,
    website_url: Optional[str] = None,
    rag_project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Re-run RAG analysis for a skill."""

    # Generate RAG project ID if not provided
    if not rag_project_id:
        rag_project_id = f"rerun-{skill_name}-{uuid.uuid4().hex[:8]}"
        _out(f"Generated RAG Project ID: {rag_project_id}")

    # Index folder if provided
    if folder_path:
        result = index_folder_for_rag(folder_path, rag_project_id)
        if 'error' in result:
            return result

    # Index website if provided
    if website_url:
        temp_folder = save_website_content_to_temp(website_url, rag_project_id)
        if temp_folder:
            result = index_folder_for_rag(temp_folder, rag_project_id)
            if 'error' in result:
                _out(f"Warning: {result['error']}")

    # Run analysis
    _out("Running comprehensive RAG content analysis...")
    _out("  - Identifying domain and business context...")
    _out("  - Mapping to Five Pillars...")
    _out("  - Analyzing business opportunities...")
    _out("  - Generating action plan...")
    try:
        analysis = analyze_content(rag_project_id)
        _out("Analysis complete!")

        # Print summary
        if 'business_opportunities' in analysis:
            opps = analysis['business_opportunities']
            _out("\n📊 Business Opportunities Found:")
            _out(f"  - Agent opportunities: {len(opps.get('agent_opportunities', []))}")
            _out(f"  - Data structures needed: {len(opps.get('data_structure_needs', []))}")

        if 'action_plan' in analysis:
            plan = analysis['action_plan']
            _out("\n🎯 Action Plan Generated:")
            _out(f"  - Priority capabilities: {len(plan.get('priority_capabilities', []))}")
            _out(f"  - Implementation steps: {len(plan.get('implementation_steps', []))}")
            _out(f"  - Quick wins: {len(plan.get('quick_wins', []))}")

        return {'success': True, 'rag_project_id': rag_project_id, 'analysis': analysis}
    except Exception as e:
        import traceback

        traceback.print_exc()
        return {'error': f'Analysis failed: {e}'}


def regenerate_dashboard_with_rag(skill_name: str, analysis: Dict[str, Any], rag_project_id: str) -> Dict[str, Any]:
    """Regenerate dashboard using RAG analysis results."""

    try:
        from src.config.paths import get_project_root as _get_root
        _project_root = _get_root()
    except ImportError:
        _project_root = Path(__file__).parent.parent.parent.parent  # fallback
    skill_dir = _project_root / 'plugins' / 'vertical' / skill_name

    if not skill_dir.exists():
        return {'error': f'Skill directory not found: {skill_dir}'}

    # Extract information from analysis
    domain = analysis.get('domain', {}).get('primary', 'general')
    pillars = analysis.get('five_pillar_mapping', {})
    patterns = analysis.get('suggested_skill', {}).get('patterns', ['database'])
    use_cases = analysis.get('use_cases', [])
    description = analysis.get('suggested_skill', {}).get('description') or analysis.get('summary', '')

    # Extract business opportunities and action plan
    business_opportunities = analysis.get('business_opportunities', {})
    action_plan = analysis.get('action_plan', {})

    # Use data structures from business opportunities if available
    data_structures = business_opportunities.get('data_structure_needs', [])
    if data_structures:
        # Override entities with business-identified structures
        [ds['name'] for ds in data_structures]
    else:
        pass

    # Read SKILL.md to get title
    skill_md_path = skill_dir / 'skill-package' / 'SKILL.md'
    if skill_md_path.exists():
        content = skill_md_path.read_text()
        # Extract title from frontmatter or content
        import re

        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else skill_name.replace('-', ' ').title()
    else:
        title = skill_name.replace('-', ' ').title()

    _out(f"Regenerating dashboard for {skill_name}...")
    _out(f"  Domain: {domain}")
    _out(f"  Patterns: {patterns}")
    _out(f"  Use cases: {len(use_cases)}")

    success, error, generated = generate_comprehensive_dashboard(
        skill_dir=skill_dir,
        skill_name=skill_name,
        skill_title=title,
        layer='vertical',
        patterns=patterns,
        domain=domain,
        rag_project_id=rag_project_id,
        pillars=pillars,
    )

    if success:
        # Generate business report
        try:
            from ..generate_business_report import generate_business_report

            report_path = skill_dir / 'skill-package' / 'BUSINESS_ANALYSIS.md'
            generate_business_report(analysis, report_path)
            _out(f"\n📄 Business analysis report saved to: {report_path}")
        except Exception as e:
            _out(f"Warning: Could not generate business report: {e}")

        return {
            'success': True,
            'generated': generated,
            'analysis': {
                'domain': domain,
                'patterns': patterns,
                'use_cases': use_cases,
                'description': description,
                'business_opportunities': business_opportunities,
                'action_plan': action_plan,
            },
        }
    else:
        return {'error': error or 'Dashboard generation failed'}


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Re-run RAG analysis and regenerate dashboard')
    parser.add_argument('skill_name', help='Skill name (e.g., smb-client-template)')
    parser.add_argument('--folder', help='Folder path to index')
    parser.add_argument('--website', help='Website URL to fetch and index')
    parser.add_argument('--rag-project-id', help='Existing RAG project ID')
    parser.add_argument('--regenerate-dashboard', action='store_true', help='Regenerate dashboard after analysis')

    args = parser.parse_args()

    if not args.folder and not args.website:
        _out("Error: Must provide either --folder or --website")
        sys.exit(1)

    # Run RAG analysis
    result = rerun_rag_analysis(
        skill_name=args.skill_name,
        folder_path=args.folder,
        website_url=args.website,
        rag_project_id=args.rag_project_id,
    )

    if 'error' in result:
        _out(f"Error: {result['error']}")
        sys.exit(1)

    _out("\n" + "=" * 60)
    _out("RAG Analysis Results:")
    _out("=" * 60)
    _out(json.dumps(result['analysis'], indent=2))
    _out("=" * 60 + "\n")

    # Regenerate dashboard if requested
    if args.regenerate_dashboard:
        dashboard_result = regenerate_dashboard_with_rag(
            skill_name=args.skill_name, analysis=result['analysis'], rag_project_id=result['rag_project_id']
        )

        if 'error' in dashboard_result:
            _out(f"Error regenerating dashboard: {dashboard_result['error']}")
            sys.exit(1)

        _out("\n" + "=" * 60)
        _out("Dashboard Regeneration Complete!")
        _out("=" * 60)
        _out(f"Generated files: {dashboard_result['generated']}")
        _out("=" * 60 + "\n")
    else:
        _out(f"\nRAG Project ID: {result['rag_project_id']}")
        _out("Use --regenerate-dashboard to regenerate the dashboard with this analysis.")


if __name__ == '__main__':
    main()

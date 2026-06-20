"""
Comprehensive Dashboard Generator

DEPRECATED: This module is deprecated as of Phase 6 (ADR-012).
Use dashboard_yaml_generator.py instead, which generates config-driven dashboard.yaml files
that HubRenderer interprets at runtime.

This file is kept for backwards compatibility but will be removed in a future release.

Migration:
    # Old approach (generates React pages)
    from .comprehensive_dashboard_generator import generate_comprehensive_dashboard

    # New approach (generates dashboard.yaml)
    from .dashboard_yaml_generator import generate_dashboard_yaml

See: docs/architecture/proposals/PROPOSAL-starter-template-wizard-unification.md
"""

from typing import Any, Optional, Dict, List
import warnings

# Re-export moved functions for backward compatibility
from .component_templates import (
    entity_to_component_name,
    generate_entity_component,
    generate_rag_search_component,
)
from .route_templates import (
    generate_service_layer,
    generate_data_api_route,
    generate_entity_api_route,
    generate_rag_search_route,
    generate_enhanced_dashboard_page,
    generate_layout,
    update_parent_layout,
    generate_productization_plan_page,
)


warnings.warn(
    "comprehensive_dashboard_generator is deprecated. Use dashboard_yaml_generator instead.",
    DeprecationWarning,
    stacklevel=2,
)


def generate_comprehensive_dashboard(
    skill_dir: Any,
    skill_name: str,
    skill_title: str,
    layer: str,
    patterns: Optional[List[str]] = None,
    data_folder: Optional[str] = None,
    domain: Optional[str] = None,
    rag_project_id: Optional[str] = None,
    pillars: Optional[Dict[str, Any]] = None,
) -> tuple[bool, Optional[str], Dict[str, Any]]:
    """
    RETIRED (ADR-802): This function previously generated pages into hub-routed
    directories (/lifestyle/, /hands/, /agents/) that no longer exist.

    Skill dashboard pages are now declared via x-augur-dashboard-pages in SKILL.md
    or as ADR-491 config pages in augur/pages/*.yaml.
    """
    raise NotImplementedError(
        "generate_comprehensive_dashboard() has been retired (ADR-802). "
        "Declare skill pages via x-augur-dashboard-pages in SKILL.md or "
        "as ADR-491 config pages in augur/pages/*.yaml."
    )

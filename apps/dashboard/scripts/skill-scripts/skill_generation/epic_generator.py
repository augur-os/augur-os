"""
Epic Generator Service

Generates backlog epics with features, user stories, and priorities
based on RAG analysis and 5 pillars framework.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import os

try:
    from src.config.paths import get_project_root
    _WORKSPACE = str(get_project_root())
except Exception:  # pragma: no cover - fallback when src is not importable
    _WORKSPACE = str(Path(__file__).resolve().parents[5])


def generate_epic(
    skill_name: str,
    skill_title: str,
    layer: str,
    analysis: Dict[str, Any],
    action_plan: Dict[str, Any],
    business_opportunities: Dict[str, Any],
    pillars: Dict[str, Any],
    domain: Optional[str] = None,
) -> tuple[bool, Optional[str], Optional[Path]]:
    """
    Generate an epic file in the backlog folder.

    Args:
        skill_name: Skill name (kebab-case)
        skill_title: Display title
        layer: Layer (factory, horizontal, vertical)
        analysis: RAG analysis results
        action_plan: Action plan from 5 pillars
        business_opportunities: Business opportunities analysis
        pillars: Five pillar mapping
        domain: Domain name (optional)

    Returns:
        Tuple of (success, error_message, epic_path)
    """
    try:
        # Determine backlog directory
        data_root = os.environ.get('AUGUR_ROOT') or str(Path.home() / 'Projects' / 'augur')

        # Create epic in appropriate backlog location
        if layer == 'vertical':
            epic_dir = Path(data_root) / 'factory' / 'executor' / 'backlog' / 'vertical' / skill_name
        elif layer == 'horizontal':
            epic_dir = Path(data_root) / 'factory' / 'executor' / 'backlog' / 'horizontal' / skill_name
        else:  # factory
            epic_dir = Path(data_root) / 'factory' / 'executor' / 'backlog' / 'factory' / skill_name

        epic_dir.mkdir(parents=True, exist_ok=True)

        # Generate epic ID
        epic_id = f"epic-{skill_name}"

        # Generate features from action plan
        features = []
        user_stories = []

        # Priority capabilities become features
        priority_caps = action_plan.get('priority_capabilities', [])
        for i, cap in enumerate(priority_caps[:5], 1):  # Top 5 capabilities
            pillar = cap.get('pillar', '').upper()
            relevance = cap.get('relevance', 0)
            priority = 'high' if relevance > 0.7 else 'medium' if relevance > 0.5 else 'low'

            feat_id = f"feat-{skill_name}-{pillar.lower()}-{i:03d}"
            features.append(
                {
                    'id': feat_id,
                    'title': f"{pillar} Capabilities",
                    'priority': priority,
                    'pillar': pillar,
                    'capabilities': cap.get('capabilities', [])[:3],
                    'applications': cap.get('applications', [])[:3],
                }
            )

            # Generate user stories for each feature
            for j, capability in enumerate(cap.get('capabilities', [])[:2], 1):
                user_stories.append(
                    {
                        'feature': feat_id,
                        'title': f"As a user, I want {capability.lower()}",
                        'description': f"Enable {capability.lower()} for {skill_title}",
                        'priority': priority,
                        'acceptance_criteria': [
                            f"User can {capability.lower()}",
                            "Results are stored and accessible",
                            f"Dashboard displays {capability.lower()} data",
                        ],
                    }
                )

        # Implementation steps become additional features
        impl_steps = action_plan.get('implementation_steps', [])
        for i, step in enumerate(impl_steps[:3], 1):
            feat_id = f"feat-{skill_name}-impl-{i:03d}"
            features.append(
                {
                    'id': feat_id,
                    'title': step.get('step', 'Implementation Step'),
                    'priority': step.get('priority', 'medium'),
                    'description': step.get('description', ''),
                }
            )

        # Generate epic content
        epic_content = generate_epic_content(
            epic_id=epic_id,
            skill_name=skill_name,
            skill_title=skill_title,
            layer=layer,
            domain=domain or analysis.get('domain', {}).get('primary', 'general'),
            features=features,
            user_stories=user_stories,
            pillars=pillars,
            business_opportunities=business_opportunities,
            action_plan=action_plan,
        )

        # Write epic file
        epic_path = epic_dir / 'EPIC.md'
        epic_path.write_text(epic_content, encoding='utf-8')

        # Generate feature files
        for feature in features:
            feat_content = generate_feature_content(
                feature_id=feature['id'],
                skill_name=skill_name,
                feature=feature,
                user_stories=[us for us in user_stories if us.get('feature') == feature['id']],
            )
            feat_path = epic_dir / f"{feature['id']}.md"
            feat_path.write_text(feat_content, encoding='utf-8')

        # Generate separate user story files
        for i, story in enumerate(user_stories, 1):
            story_id = f"story-{skill_name}-{i:03d}"
            story_content = generate_user_story_content(
                story_id=story_id, skill_name=skill_name, story=story, feature_id=story.get('feature')
            )
            story_path = epic_dir / 'user-stories' / f"{story_id}.md"
            story_path.parent.mkdir(parents=True, exist_ok=True)
            story_path.write_text(story_content, encoding='utf-8')

        # Generate data structure definition file
        data_structures = business_opportunities.get('data_structures', [])
        if data_structures:
            data_structure_content = generate_data_structure_content(
                skill_name=skill_name,
                skill_title=skill_title,
                data_structures=data_structures,
                domain=domain or analysis.get('domain', {}).get('primary', 'general'),
            )
            data_structure_path = epic_dir / 'data-structure.md'
            data_structure_path.write_text(data_structure_content, encoding='utf-8')

        return True, None, epic_path

    except Exception as e:
        import traceback

        traceback.print_exc()
        return False, f"Failed to generate epic: {e}", None


def generate_epic_content(
    epic_id: str,
    skill_name: str,
    skill_title: str,
    layer: str,
    domain: str,
    features: list[Dict[str, Any]],
    user_stories: list[Dict[str, Any]],
    pillars: Dict[str, Any],
    business_opportunities: Dict[str, Any],
    action_plan: Dict[str, Any],
) -> str:
    """Generate epic markdown content."""

    # Frontmatter
    frontmatter = {
        'id': epic_id,
        'type': 'epic',
        'priority': 'high',
        'skill': skill_name,
        'workspace': _WORKSPACE,
        'created': datetime.now().strftime('%Y-%m-%d'),
        'status': 'ready',
        'source': 'wizard-generated',
        'child_features': [f['id'] for f in features],
    }

    frontmatter_yaml = yaml.dump(frontmatter, sort_keys=False).strip()

    # Pillar summary
    pillar_summary = []
    sorted_pillars = sorted(pillars.items(), key=lambda x: x[1].get('relevance', 0), reverse=True)
    for pillar, data in sorted_pillars:
        relevance = data.get('relevance', 0)
        if relevance > 0.5:
            pillar_summary.append(f"- **{pillar.upper()}** ({int(relevance * 100)}% relevant)")

    # Features table
    features_table = "| ID | Feature | Priority | Pillar |\n"
    features_table += "|----|---------|----------|--------|\n"
    for feat in features:
        pillar = feat.get('pillar', 'N/A')
        priority = feat.get('priority', 'medium')
        features_table += f"| {feat['id']} | {feat['title']} | {priority} | {pillar} |\n"

    # Business opportunities
    agent_opps = business_opportunities.get('agent_opportunities', [])
    data_structures = business_opportunities.get('data_structures', [])

    content = f"""---
{frontmatter_yaml}
---

# Epic: {skill_title} - AI-Powered Skill Implementation

## 🎯 Vision

Transform {domain} domain knowledge into a fully functional Augur skill with AI-powered capabilities, intelligent dashboard, and seamless integration with the Five Pillar Framework.

**Domain**: {domain}  
**Layer**: {layer}  
**Skill**: {skill_name}

## 📊 Business Analysis Summary

### Agent Opportunities

"""

    for opp in agent_opps[:5]:
        impact = opp.get('impact', 'medium')
        content += f"- **{opp.get('opportunity', 'N/A')}** (Impact: {impact.upper()})\n"

    content += """
### Data Structures Needed

"""

    for ds in data_structures[:5]:
        fields = ', '.join([f if isinstance(f, str) else f.get('name', 'unknown') for f in ds.get('fields', [])[:3]])
        content += f"- **{ds.get('name', 'N/A')}**: {fields or 'No fields specified'}\n"

    content += """
## 🏛️ Five Pillars Application

"""

    content += '\n'.join(pillar_summary)

    content += f"""

## 📋 Child Features

{features_table}

## 🎯 Priority Implementation Plan

### Quick Wins

"""

    quick_wins = action_plan.get('quick_wins', [])
    for win in quick_wins[:3]:
        content += f"- ✅ **{win.get('capability', 'N/A')}**: Impact: {win.get('impact', 'medium')}, Effort: {win.get('effort', 'low')}\n"

    content += """
### Long-term Goals

"""

    long_term = action_plan.get('long_term_goals', [])
    for goal in long_term[:3]:
        content += f"- 📈 **{goal.get('goal', 'N/A')}**: {goal.get('description', '')} (Timeline: {goal.get('timeline', 'TBD')})\n"

    content += f"""
## 🚀 Expected Impact

By implementing this epic, {skill_title} will provide:
- **AI-Powered Insights**: Leverage RAG analysis for intelligent recommendations
- **Domain-Specific Dashboard**: Custom UI tailored to {domain} workflows
- **Five Pillar Integration**: Full support for Capture, Analyze, Execute, Recall, and Grow
- **Scalable Architecture**: Foundation for future enhancements

## 📝 Next Steps

1. Review this epic and adjust priorities as needed
2. Review generated feature files in this directory
3. Review user stories in `user-stories/` directory
4. Review data structure definition in `data-structure.md`
5. Approve epic to proceed with skill generation
6. Skill generation will create the complete implementation

---

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Source**: Skill Wizard (RAG Analysis + 5 Pillars Framework)
"""

    return content


def generate_feature_content(
    feature_id: str, skill_name: str, feature: Dict[str, Any], user_stories: list[Dict[str, Any]]
) -> str:
    """Generate feature markdown content."""

    frontmatter = {
        'id': feature_id,
        'type': 'feature',
        'priority': feature.get('priority', 'medium'),
        'skill': skill_name,
        'workspace': _WORKSPACE,
        'created': datetime.now().strftime('%Y-%m-%d'),
        'status': 'ready',
        'source': 'wizard-generated',
        'parent': f"epic-{skill_name}",
    }

    frontmatter_yaml = yaml.dump(frontmatter, sort_keys=False).strip()

    capabilities = feature.get('capabilities', [])
    applications = feature.get('applications', [])

    content = f"""---
{frontmatter_yaml}
---

# Feature: {feature['title']}

## 📖 User Story

{feature.get('description', feature['title'])}

## 🎯 Acceptance Criteria

"""

    for story in user_stories:
        content += f"""### {story['title']}

{story.get('description', '')}

**Acceptance Criteria:**
"""
        for ac in story.get('acceptance_criteria', []):
            content += f"- [ ] {ac}\n"
        content += "\n"

    if capabilities:
        content += """## 🔧 Capabilities

"""
        for cap in capabilities:
            content += f"- {cap}\n"
        content += "\n"

    if applications:
        content += """## 📊 Applications

"""
        for app in applications:
            content += f"- {app}\n"
        content += "\n"

    content += f"""## 🔗 Related

- Parent Epic: `epic-{skill_name}`
- Skill: `{skill_name}`

---

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    return content


def generate_user_story_content(
    story_id: str, skill_name: str, story: Dict[str, Any], feature_id: Optional[str] = None
) -> str:
    """Generate user story markdown content."""

    frontmatter = {
        'id': story_id,
        'type': 'user-story',
        'priority': story.get('priority', 'medium'),
        'skill': skill_name,
        'workspace': _WORKSPACE,
        'created': datetime.now().strftime('%Y-%m-%d'),
        'status': 'ready',
        'source': 'wizard-generated',
    }

    if feature_id:
        frontmatter['parent'] = feature_id
        frontmatter['epic'] = f"epic-{skill_name}"

    frontmatter_yaml = yaml.dump(frontmatter, sort_keys=False).strip()

    content = f"""---
{frontmatter_yaml}
---

# User Story: {story['title']}

## 📖 Description

{story.get('description', story['title'])}

## 🎯 Acceptance Criteria

"""

    for ac in story.get('acceptance_criteria', []):
        content += f"- [ ] {ac}\n"

    content += f"""
## 📊 Priority

**Priority**: {story.get('priority', 'medium').upper()}

## 🔗 Related

"""

    if feature_id:
        content += f"- Parent Feature: `{feature_id}`\n"

    content += f"""- Epic: `epic-{skill_name}`
- Skill: `{skill_name}`

## 📝 Notes

Add implementation notes here as you work on this story.

---

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    return content


def generate_data_structure_content(
    skill_name: str, skill_title: str, data_structures: list[Dict[str, Any]], domain: str
) -> str:
    """Generate data structure definition file."""

    content = f"""# Data Structure Definition: {skill_title}

**Domain**: {domain}  
**Skill**: {skill_name}  
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📋 Overview

This document defines the data structures needed for the {skill_title} skill, based on RAG analysis and business requirements.

## 🗂️ Data Structures

"""

    for i, ds in enumerate(data_structures, 1):
        name = ds.get('name', f'Entity{i}')
        description = ds.get('description', '')
        fields = ds.get('fields', [])

        content += f"""### {i}. {name}

"""

        if description:
            content += f"{description}\n\n"

        content += """**Fields:**

"""

        if fields:
            content += "| Field | Type | Description | Required |\n"
            content += "|-------|------|-------------|----------|\n"

            for field in fields:
                field_name = field if isinstance(field, str) else field.get('name', 'unknown')
                field_type = 'string' if isinstance(field, str) else field.get('type', 'string')
                field_desc = '' if isinstance(field, str) else field.get('description', '')
                field_required = 'Yes' if isinstance(field, str) else ('Yes' if field.get('required', True) else 'No')

                content += f"| `{field_name}` | {field_type} | {field_desc} | {field_required} |\n"
        else:
            content += "*No fields specified*\n"

        content += "\n"

    content += """## 📝 TypeScript Interface Definitions

```typescript
"""

    for ds in data_structures:
        name = ds.get('name', 'Entity')
        fields = ds.get('fields', [])
        capitalized = name[0].upper() + name[1:] if name else 'Entity'

        content += f"export interface {capitalized} {{\n"

        if fields:
            for field in fields:
                field_name = field if isinstance(field, str) else field.get('name', 'unknown')
                field_type = 'string' if isinstance(field, str) else field.get('type', 'string')
                field_required = '' if isinstance(field, str) else ('' if field.get('required', True) else '?')

                content += f"  {field_name}{field_required}: {field_type};\n"
        else:
            content += "  id: string;\n"
            content += "  name: string;\n"
            content += "  createdAt: string;\n"
            content += "  updatedAt: string;\n"

        content += "}\n\n"

    content += """export interface SkillData {
"""

    for ds in data_structures:
        name = ds.get('name', 'Entity')
        capitalized = name[0].upper() + name[1:] if name else 'Entity'
        plural = name + 's' if not name.endswith('s') else name

        content += f"  {plural}: {capitalized}[];\n"

    content += """  lastUpdated?: string;
}
```
"""

    content += """
## 📦 YAML Database Schema

The skill will use a YAML database with the following structure:

```yaml
"""

    for ds in data_structures:
        name = ds.get('name', 'Entity')
        plural = name + 's' if not name.endswith('s') else name

        content += f"{plural}:\n"
        content += "  - id: example-1\n"

        fields = ds.get('fields', [])
        if fields:
            for field in fields[:3]:  # Show first 3 fields as examples
                field_name = field if isinstance(field, str) else field.get('name', 'unknown')
                field_type = 'string' if isinstance(field, str) else field.get('type', 'string')
                example_value = 'example-value' if field_type == 'string' else '0' if field_type == 'number' else 'true'
                content += f"    {field_name}: {example_value}\n"
        else:
            content += "    name: Example Item\n"
            content += "    createdAt: '2025-01-01T00:00:00Z'\n"

        content += "\n"

    content += """lastUpdated: '2025-01-01T00:00:00Z'
```
"""

    content += f"""
## 🔗 Related Files

- Epic: `epic-{skill_name}`
- Skill: `plugins/*/{skill_name}/`
- Service Layer: `apps/dashboard/lib/services/{skill_name}.ts`
- API Routes: `apps/dashboard/app/api/{skill_name}/`

---

**Note**: This data structure definition will be used to generate:
- TypeScript interfaces in the service layer
- API route handlers
- Dashboard components
- YAML database schema

"""

    return content

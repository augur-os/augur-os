#!/usr/bin/env python3
"""
Generate Business Analysis Report

Creates a comprehensive report showing how Augur can help a business
based on RAG analysis of their content.
"""

import json
from pathlib import Path
from typing import Dict, Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def generate_business_report(analysis: Dict[str, Any], output_path: Path) -> str:
    """
    Generate a comprehensive business report from RAG analysis.

    Args:
        analysis: Complete RAG analysis result
        output_path: Path to save the report

    Returns:
        Report content as string
    """
    domain = analysis.get('domain', {}).get('primary', 'general')
    business_opps = analysis.get('business_opportunities', {})
    action_plan = analysis.get('action_plan', {})
    pillars = analysis.get('five_pillar_mapping', {})

    report = f"""# 🎯 Business Analysis Report: SMB Design Office

## 📊 Executive Summary

Based on comprehensive analysis of your business documents and content, this report identifies
how Augur can transform your design business operations using AI-powered automation
and intelligent data management.

**Domain Identified**: {domain.replace('-', ' ').title()}
**Confidence**: {analysis.get('domain', {}).get('confidence', 0) * 100:.0f}%

---

## 🚀 Business Opportunities

### Agent Opportunities

"""

    agent_opps = business_opps.get('agent_opportunities', [])
    for opp in agent_opps:
        impact_emoji = '🔥' if opp.get('impact') == 'high' else '⚡'
        report += f"{impact_emoji} **{opp.get('type', '').replace('_', ' ').title()}**\n"
        report += f"   - {opp.get('description', '')}\n"
        report += f"   - Impact: {opp.get('impact', '').upper()}\n\n"

    report += "\n### Data Structures Needed\n\n"
    data_structures = business_opps.get('data_structure_needs', [])
    for ds in data_structures:
        report += f"📋 **{ds.get('name', '').title()}**\n"
        report += f"   - {ds.get('description', '')}\n"
        report += f"   - Fields: {', '.join(ds.get('fields', [])[:5])}\n\n"

    report += "\n---\n\n## 🏛️ Five Pillars Application\n\n"

    # Show how each pillar applies
    pillar_apps = business_opps.get('pillar_applications', {})
    pillar_emojis = {'capture': '📥', 'analyze': '🔬', 'execute': '⚡', 'recall': '🔍', 'grow': '🌱'}

    for pillar, data in pillars.items():
        relevance = data.get('relevance', 0)
        if relevance > 0.5:
            emoji = pillar_emojis.get(pillar, '•')
            report += f"{emoji} **{pillar.upper()}** ({relevance * 100:.0f}% relevant)\n"
            report += f"   - {data.get('reasoning', '')}\n"

            apps = pillar_apps.get(pillar, [])
            if apps:
                report += "   - Applications:\n"
                for app in apps[:3]:
                    report += f"     • {app}\n"
            report += "\n"

    report += "\n---\n\n## 🎯 Action Plan\n\n"

    # Priority capabilities
    priority_caps = action_plan.get('priority_capabilities', [])
    if priority_caps:
        report += "### Priority Capabilities\n\n"
        for cap in priority_caps[:3]:
            pillar = cap.get('pillar', '')
            report += f"**{pillar.upper()}** ({cap.get('relevance', 0) * 100:.0f}% relevance)\n"
            capabilities = cap.get('capabilities', [])
            if capabilities:
                report += f"   - {', '.join(capabilities[:3])}\n"
            report += "\n"

    # Implementation steps
    impl_steps = action_plan.get('implementation_steps', [])
    if impl_steps:
        report += "### Implementation Steps\n\n"
        for i, step in enumerate(impl_steps, 1):
            priority = step.get('priority', 'medium')
            priority_emoji = '🔥' if priority == 'high' else '⚡'
            report += f"{priority_emoji} **Step {i}**: {step.get('step', '')}\n"
            report += f"   - {step.get('description', '')}\n"
            report += f"   - Priority: {priority.upper()}\n\n"

    # Quick wins
    quick_wins = action_plan.get('quick_wins', [])
    if quick_wins:
        report += "### ⚡ Quick Wins\n\n"
        for win in quick_wins:
            report += f"✅ **{win.get('capability', '')}**\n"
            report += f"   - Impact: {win.get('impact', '').upper()}\n"
            report += f"   - Effort: {win.get('effort', '').upper()}\n\n"

    # Long-term goals
    long_term = action_plan.get('long_term_goals', [])
    if long_term:
        report += "### 🌟 Long-term Goals\n\n"
        for goal in long_term:
            report += f"🎯 **{goal.get('goal', '')}**\n"
            report += f"   - {goal.get('description', '')}\n"
            report += f"   - Timeline: {goal.get('timeline', '')}\n\n"

    report += "\n---\n\n## 💡 The Wow Factor\n\n"
    report += "### How Augur Transforms Your Business\n\n"

    # Generate wow factor insights
    if agent_opps:
        report += "**🤖 Intelligent Automation**\n"
        report += "   - Automate repetitive tasks that currently take hours\n"
        report += "   - Free up time for creative design work\n"
        report += "   - Never miss a follow-up or deadline\n\n"

    if data_structures:
        report += "**📊 Centralized Data Management**\n"
        report += "   - All customer, project, and document data in one place\n"
        report += "   - Instant search across all business knowledge\n"
        report += "   - Data-driven insights for better decision making\n\n"

    if any(p.get('relevance', 0) > 0.7 for p in pillars.values()):
        report += "**🔬 Smart Analysis**\n"
        report += "   - AI-powered analysis of business patterns\n"
        report += "   - Identify trends and opportunities\n"
        report += "   - Score and prioritize leads automatically\n\n"

    report += "**🔍 Instant Knowledge Recall**\n"
    report += "   - Search across all documents and conversations\n"
    report += "   - Find similar past projects instantly\n"
    report += "   - Learn from historical data\n\n"

    report += "\n---\n\n## 📈 Expected Impact\n\n"
    report += "- **Time Savings**: 10-15 hours per week on administrative tasks\n"
    report += "- **Better Customer Service**: Faster response times, better follow-ups\n"
    report += "- **Data-Driven Decisions**: Insights from all business data\n"
    report += "- **Scalability**: Handle more projects without proportional overhead\n"

    report += "\n---\n\n*Report generated by Augur Business Analysis*\n"

    # Save report
    output_path.write_text(report, encoding='utf-8')

    return report


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        _out("Usage: generate_business_report.py <analysis_json> <output_path>")
        sys.exit(1)

    analysis_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    analysis = json.loads(analysis_path.read_text())
    report = generate_business_report(analysis, output_path)
    _out(f"Report saved to: {output_path}")

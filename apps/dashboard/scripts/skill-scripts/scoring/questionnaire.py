"""
Default assessment questions for quality scoring.

Provides fallback questionnaire when template files are not found.
"""

from __future__ import annotations

from typing import Any, Dict, List


def get_default_questions() -> List[Dict[str, Any]]:
    """Get default assessment questions if template not found."""
    return [
        {
            "id": "problem_clarity",
            "text": "How clearly does this plugin define the problem it solves?",
            "type": "choice",
            "options": [
                {"value": 5, "label": "Very clear - I immediately understand what it does"},
                {"value": 4, "label": "Mostly clear - Purpose is evident with minor ambiguity"},
                {"value": 3, "label": "Somewhat clear - General idea but details are fuzzy"},
                {"value": 2, "label": "Unclear - Have to dig through files to understand"},
                {"value": 1, "label": "Very unclear - Cannot determine the purpose"},
            ],
            "required": True,
        },
        {
            "id": "problem_relevance",
            "text": "How relevant is this plugin to your actual needs?",
            "type": "choice",
            "options": [
                {"value": 5, "label": "Essential - I would use this daily"},
                {"value": 4, "label": "Very useful - I would use this weekly"},
                {"value": 3, "label": "Somewhat useful - I would use occasionally"},
                {"value": 2, "label": "Marginally useful - Nice to have"},
                {"value": 1, "label": "Not useful - Does not address my needs"},
            ],
            "required": True,
        },
        {
            "id": "action_completeness",
            "text": "How complete is the set of actions/buttons?",
            "type": "choice",
            "options": [
                {"value": 5, "label": "Complete - All actions I need are available"},
                {"value": 4, "label": "Mostly complete - Missing 1-2 minor actions"},
                {"value": 3, "label": "Partially complete - Missing several useful actions"},
                {"value": 2, "label": "Incomplete - Many obvious actions missing"},
                {"value": 1, "label": "Very incomplete - Only basic actions exist"},
            ],
            "required": True,
        },
        {
            "id": "missing_actions",
            "text": "What key actions are missing? (comma-separated)",
            "type": "text",
            "default": "",
            "required": False,
        },
        {
            "id": "data_organization",
            "text": "How well does the data structure match how you think about this domain?",
            "type": "choice",
            "options": [
                {"value": 5, "label": "Perfect match - Exactly how I organize this data"},
                {"value": 4, "label": "Good match - Minor adjustments would help"},
                {"value": 3, "label": "Acceptable - Works but feels awkward"},
                {"value": 2, "label": "Poor match - I would organize differently"},
                {"value": 1, "label": "Wrong approach - Fundamentally misaligned"},
            ],
            "required": True,
        },
        {
            "id": "data_growth_concern",
            "text": "What concerns you most about data accumulation over time?",
            "type": "choice",
            "options": [
                {"value": "search", "label": "Finding specific items will become difficult"},
                {"value": "performance", "label": "Plugin will slow down with lots of data"},
                {"value": "organization", "label": "Data will become messy and disorganized"},
                {"value": "backup", "label": "Losing data or not having good backups"},
                {"value": "none", "label": "No significant concerns"},
            ],
            "required": True,
        },
        {
            "id": "ui_navigation",
            "text": "How easy is it to navigate and find things in the UI?",
            "type": "choice",
            "options": [
                {"value": 5, "label": "Very easy - Intuitive navigation throughout"},
                {"value": 4, "label": "Easy - Minor friction in some areas"},
                {"value": 3, "label": "Moderate - Takes some time to find things"},
                {"value": 2, "label": "Difficult - Frequently get lost or confused"},
                {"value": 1, "label": "Very difficult - UI is confusing"},
            ],
            "required": True,
        },
        {
            "id": "quick_access_priority",
            "text": "What do you need quickest access to?",
            "type": "choice",
            "options": [
                {"value": "recent", "label": "Most recent items"},
                {"value": "frequent", "label": "Most frequently used items"},
                {"value": "important", "label": "Items marked as important/starred"},
                {"value": "pending", "label": "Items requiring action"},
                {"value": "search", "label": "Global search across everything"},
            ],
            "required": True,
        },
        {
            "id": "biggest_gap",
            "text": "What is the single biggest gap in this plugin?",
            "type": "choice",
            "options": [
                {"value": "actions", "label": "Missing or incomplete actions"},
                {"value": "data", "label": "Poor data structure or storage"},
                {"value": "ui", "label": "Bad UI/UX design"},
                {"value": "integration", "label": "Lack of integrations"},
                {"value": "automation", "label": "No automation or workflows"},
                {"value": "none", "label": "No significant gaps"},
            ],
            "required": True,
        },
        {
            "id": "improvement_priority",
            "text": "What are your top improvement priorities?",
            "type": "multi_choice",
            "max_selections": 3,
            "options": [
                {"value": "more_actions", "label": "Add more actions/buttons"},
                {"value": "better_data", "label": "Improve data organization"},
                {"value": "better_ui", "label": "Improve UI/navigation"},
                {"value": "automation", "label": "Add automation/triggers"},
                {"value": "search", "label": "Better search/filtering"},
                {"value": "reporting", "label": "Add reports/analytics"},
                {"value": "integrations", "label": "Add external integrations"},
            ],
            "required": True,
        },
        {
            "id": "action_flow_preference",
            "text": "For the main workflow, what action dispatch type do you prefer?",
            "type": "choice",
            "options": [
                {"value": "fire", "label": "Fire - Immediate execution"},
                {"value": "oneshot", "label": "Oneshot - Single AI task"},
                {"value": "modal", "label": "Modal forms - Structured input"},
                {"value": "mixed", "label": "Mixed - Different dispatches for different actions"},
            ],
            "required": True,
        },
        {
            "id": "missing_problem_aspects",
            "text": "Which aspects of the problem are NOT addressed?",
            "type": "multi_choice",
            "options": [
                {"value": "data_import", "label": "Importing existing data"},
                {"value": "data_export", "label": "Exporting data for backup/sharing"},
                {"value": "automation", "label": "Automated workflows/triggers"},
                {"value": "search", "label": "Searching and filtering"},
                {"value": "reporting", "label": "Reports or analytics"},
                {"value": "collaboration", "label": "Sharing or collaboration"},
                {"value": "mobile", "label": "Mobile or offline access"},
                {"value": "none", "label": "All key aspects are covered"},
            ],
            "required": True,
        },
    ]

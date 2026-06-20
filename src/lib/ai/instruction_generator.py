"""Instruction Generator for Mode 3 (Enterprise IDE Integration).

Generates IDE-specific instructions, configurations, and workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Instruction:
    """Generated instruction for an IDE."""

    content: str
    format: str  # 'markdown', 'yaml', 'json', 'script'
    filename: str | None = None
    description: str | None = None


class InstructionGenerator:
    """Generates IDE-specific instructions and configurations."""

    def generate_cursor_instructions(self, action: str, params: dict[str, Any]) -> Instruction:
        """Generate Cursor-specific instructions."""
        if action == "create_skill":
            return self._generate_cursor_skill_creation(params)
        elif action == "analyze_skill":
            return self._generate_cursor_skill_analysis(params)
        elif action == "generate_dashboard":
            return self._generate_cursor_dashboard_generation(params)
        elif action == "run_investor_demo":
            return self._generate_cursor_investor_demo(params)
        else:
            return Instruction(
                content=f"# Cursor Instructions\n\nAction: {action}\n\nRun this in Cursor chat:\n```\n{action}: {params}\n```",
                format="markdown",
                description=f"Cursor instructions for {action}",
            )

    def _generate_cursor_investor_demo(self, params: dict[str, Any]) -> Instruction:
        """Generate Cursor instructions for the Investor Demo."""
        instructions = """# Run Investor Demo

## 🚀 Launching the Self-Evolving Enterprise Demo

You are about to simulate the entire lifecycle of an Augur Vertical.

## Step 1: Execute The Master Command
Copy and paste this into your terminal:

```bash
python3 run_demo_orchestrator.py
```

## What will happen?
1. **Architect Agent**: Will design the "Investor Relations" vertical (simulated).
2. **System Planner**: Will schedule the work in `sprint-202X.md`.
3. **Builder Agent**: Will scaffold the code and React Dashboard.
4. **Validator**: Will check the build and verify the UI.

## Step 2: View the Result
Once the script completes, open:
`http://localhost:3000/venture/investors`
"""
        return Instruction(
            content=instructions,
            format="markdown",
            filename="cursor-investor-demo.md",
            description="Cursor instructions for running the investor demo",
        )

    def _generate_cursor_skill_creation(self, params: dict[str, Any]) -> Instruction:
        """Generate Cursor instructions for skill creation."""
        name = params.get("name", "new-skill")
        patterns = params.get("patterns", [])
        layer = params.get("layer", "vertical")
        title = params.get("title", name.replace("-", " ").title())

        patterns_str = ", ".join(patterns) if patterns else "basic"
        instructions = f"""# Create Augur Skill: {title}

## Step 1: Open Cursor Chat
Press `Cmd+L` (Mac) or `Ctrl+L` (Windows/Linux) to open Cursor chat.

## Step 2: Run This Command
Copy and paste this into Cursor chat:

```
Create a new Augur skill called "{name}" with the following specifications:

- Skill Name: {name}
- Title: {title}
- Layer: {layer}
- Patterns: {patterns_str}

The skill should include:
1. SKILL.md file with skill definition
2. Python scripts for processing (if needed)
3. Dashboard components (if dashboard pattern is included)
4. Test files
5. Configuration files

Generate the complete skill structure following Augur conventions.
```

## Step 3: Cursor Will Generate
Cursor will create the following structure:
- `project-brain/capabilities/skills/{name}/SKILL.md`
- `project-brain/capabilities/skills/{name}/scripts/` (if needed)
- `apps/dashboard/app/.../{name}/` (if dashboard pattern)
- Test files and configuration

## Step 4: Validate Dashboard (if dashboard pattern included)
If the skill includes a dashboard pattern, run validation to ensure all API routes have corresponding service functions:

```bash
cd <PROJECT_ROOT>
python3 .github/scripts/validate_dashboard.py {name}
```

This will check:
- All API route imports match service file exports
- TypeScript types and interfaces are properly exported
- No missing function exports

Fix any validation errors before proceeding.

## Step 5: Review and Customize
Review the generated files and customize as needed.
"""

        return Instruction(
            content=instructions,
            format="markdown",
            filename="cursor-skill-creation.md",
            description="Cursor instructions for creating a new skill",
        )

    def _generate_cursor_skill_analysis(self, params: dict[str, Any]) -> Instruction:
        """Generate Cursor instructions for skill analysis and refactoring."""
        skill_path = params.get("skill_path", "")

        # Extract skill name from path
        skill_name = skill_path.split("/")[-1] if "/" in skill_path else skill_path

        instructions = f"""# Review and Refactor Augur Skill: {skill_name}

## 🎯 Your Task
You are now reviewing and refactoring a newly generated Augur skill. Use your LLM capabilities to analyze, improve, and develop the skill and its dashboard.

## 📋 Step 1: Analyze the Skill Structure

First, examine the skill at: `{skill_path}`

**Read these files:**
1. `{skill_path}/SKILL.md` - Skill definition and capabilities
2. `{skill_path}/scripts/` - Python scripts (if any)
3. `apps/dashboard/app/` - Dashboard components (if generated)
4. `apps/dashboard/app/api/{skill_name}/` - API routes (if generated)

**Analyze:**
- ✅ Does the skill structure follow Augur conventions?
- ✅ Are patterns (inbox, database, dashboard, RAG) properly implemented?
- ✅ Is the code quality good? Any obvious bugs or issues?
- ✅ Are TypeScript/React components following best practices?
- ✅ Are API routes properly structured?
- ✅ Is error handling present?

## 🔧 Step 2: Review Dashboard Components

**Check dashboard files:**
- `apps/dashboard/app/lifestyle/{skill_name}/page.tsx` (or appropriate domain)
- `apps/dashboard/app/lifestyle/{skill_name}/*Panel.tsx` components
- `apps/dashboard/lib/services/{skill_name}.ts` service layer
- `apps/dashboard/app/api/{skill_name}/**/route.ts` API routes

**Review for:**
- ✅ Component structure and organization
- ✅ State management patterns
- ✅ API integration
- ✅ Error handling
- ✅ Loading states
- ✅ TypeScript types
- ✅ Accessibility
- ✅ Performance optimizations

## 🚀 Step 3: Refactor and Improve

**Now actively refactor the code:**

1. **Fix any issues you found:**
   - Fix bugs
   - Improve error handling
   - Add missing types
   - Optimize performance

2. **Enhance code quality:**
   - Improve component structure
   - Add proper TypeScript types
   - Extract reusable logic
   - Improve naming conventions
   - Add comments where needed

3. **Enhance dashboard:**
   - Improve UI/UX
   - Add loading states
   - Add error boundaries
   - Improve responsive design
   - Add accessibility features

4. **Enhance API routes:**
   - Add proper validation
   - Improve error responses
   - Add request logging
   - Optimize database queries

## 📝 Step 4: Document Improvements

After refactoring, update:
- `{skill_path}/SKILL.md` if needed
- Add comments to complex code
- Update README if significant changes

## 🎨 Step 5: Validate Dashboard

**Run validation to ensure all API routes have corresponding service functions:**

```bash
cd <PROJECT_ROOT>
python3 .github/scripts/validate_dashboard.py {skill_name}
```

This will check:
- ✅ All API route imports match service file exports
- ✅ TypeScript types and interfaces are properly exported
- ✅ No missing function exports

**Fix any validation errors before proceeding.**

## 🧪 Step 6: Test the Changes

**Verify:**
- Dashboard loads correctly
- API routes work
- Components render properly
- No TypeScript errors
- No console errors
- Validation passes

## 💡 Pro Tips

- Use Cursor's multi-file editing to refactor across files
- Ask Cursor to explain complex code before refactoring
- Use Cursor's code generation to add missing features
- Leverage Cursor's context awareness to understand the full skill

## 🎯 Expected Outcome

After this review and refactoring:
- ✅ Code quality improved
- ✅ Dashboard polished and functional
- ✅ API routes robust and error-handled
- ✅ TypeScript types complete
- ✅ Best practices followed
- ✅ Ready for production use

---

**Start by reading the skill files, then provide a detailed analysis, then proceed with refactoring.**
"""

        return Instruction(
            content=instructions,
            format="markdown",
            filename="cursor-skill-review-refactor.md",
            description="Cursor instructions for skill review and refactoring",
        )

    def _generate_cursor_dashboard_generation(self, params: dict[str, Any]) -> Instruction:
        """Generate Cursor instructions for dashboard generation."""
        skill_name = params.get("skill_name", "")
        instructions = f"""# Generate Dashboard for Skill: {skill_name}

## Run in Cursor Chat
```
Generate a comprehensive dashboard for the Augur skill "{skill_name}".

The dashboard should include:
1. Main page component with EditableMasonryGrid
2. Service layer for data operations
3. API routes for CRUD operations
4. Interactive components based on skill patterns
5. Integration with existing dashboard structure

Follow Augur dashboard conventions and patterns.
```

## Step 2: Validate Dashboard

After generation, run validation to ensure all API routes have corresponding service functions:

```bash
cd <PROJECT_ROOT>
python3 .github/scripts/validate_dashboard.py {skill_name}
```

This will check:
- ✅ All API route imports match service file exports
- ✅ TypeScript types and interfaces are properly exported
- ✅ No missing function exports

**Fix any validation errors before proceeding.**
"""

        return Instruction(
            content=instructions,
            format="markdown",
            filename="cursor-dashboard-generation.md",
            description="Cursor instructions for dashboard generation",
        )

    def generate_copilot_instructions(self, action: str, params: dict[str, Any]) -> Instruction:
        """Generate GitHub Copilot-specific instructions."""
        if action == "create_skill":
            return self._generate_copilot_skill_creation(params)
        else:
            return Instruction(
                content=f"# GitHub Copilot Instructions\n\nAction: {action}\n\nUse Copilot chat to: {action}",
                format="markdown",
                description=f"Copilot instructions for {action}",
            )

    def _generate_copilot_skill_creation(self, params: dict[str, Any]) -> Instruction:
        """Generate Copilot instructions for skill creation."""
        name = params.get("name", "new-skill")
        patterns = params.get("patterns", [])

        instructions = f"""# Create Augur Skill with GitHub Copilot

## Step 1: Open Copilot Chat
Open GitHub Copilot chat in your IDE.

## Step 2: Use This Prompt
```
Create an Augur skill named "{name}" with patterns: {', '.join(patterns) if patterns else 'basic'}.

Generate:
- SKILL.md with skill definition
- Python scripts for processing
- Dashboard components
- Test files

Follow Augur conventions.
```

## Step 3: Validate Dashboard (if dashboard pattern included)
If the skill includes a dashboard pattern, run validation:

```bash
cd <PROJECT_ROOT>
python3 .github/scripts/validate_dashboard.py {name}
```

Fix any validation errors before proceeding.

## Step 4: Review Generated Code
Copilot will generate the code. Review and customize as needed.
"""

        return Instruction(
            content=instructions,
            format="markdown",
            filename="copilot-skill-creation.md",
            description="GitHub Copilot instructions for skill creation",
        )

    def generate_antigravity_workflow(self, action: str, params: dict[str, Any]) -> Instruction:
        """Generate Antigravity workflow Markdown."""
        if action == "create_skill":
            return self._generate_antigravity_skill_creation(params)
        elif action == "analyze_skill":
            return self._generate_antigravity_skill_analysis(params)
        else:
            return Instruction(
                content=f"---\ndescription: Antigravity workflow for {action}\n---\n\n# Workflow: {action}\n\nExecute the following action:\n{action}\n\nParameters: {params}",
                format="markdown",
                filename=f"antigravity-{action}.md",
                description=f"Antigravity workflow for {action}",
            )

    def _generate_antigravity_skill_creation(self, params: dict[str, Any]) -> Instruction:
        """Generate Antigravity workflow for skill creation."""
        name = params.get("name", "new-skill")
        params.get("patterns", [])

        description = f"Create a new Augur skill '{name}'"

        workflow = f"""---
description: {description}
---

# Create Augur Skill: {name}

This workflow guides the creation of a new Augur skill named "{name}".

## Prerequisites

- Ensure you are in the project root.

## Step 1: Create Skill Structure

Create the skill directory and basic files.

```bash
mkdir -p project-brain/capabilities/skills/{name}
touch project-brain/capabilities/skills/{name}/SKILL.md
```

## Step 2: Define Skill

Edit `project-brain/capabilities/skills/{name}/SKILL.md` to define the skill capabilities.

## Step 3: Create Dashboard Components (Optional)

If patterns include 'dashboard', create the necessary components in `apps/dashboard`.

## Step 4: Validate

```bash
# Validate dashboard structure if applicable
python3 .github/scripts/validate_dashboard.py {name}
```
"""

        return Instruction(
            content=workflow,
            format="markdown",
            filename=f"create-skill-{name}.md",
            description="Antigravity workflow for skill creation",
        )

    def _generate_antigravity_skill_analysis(self, params: dict[str, Any]) -> Instruction:
        """Generate Antigravity workflow for skill analysis."""
        skill_path = params.get("skill_path", "")
        skill_name = Path(skill_path).name if skill_path else "unknown"

        description = f"Analyze and refactor skill '{skill_name}'"

        workflow = f"""---
description: {description}
---

# Analyze Skill: {skill_name}

## Step 1: Review SKILL.md

Read contents of `{skill_path}/SKILL.md`.

## Step 2: Analyze Code Structure

List files in `{skill_path}` and analyze their purpose.

## Step 3: Check Dashboard Integration

Check for existence of dashboard components in `apps/dashboard/app`.

## Step 4: Run Validation

```bash
python3 .github/scripts/validate_dashboard.py {skill_name}
```
"""

        return Instruction(
            content=workflow,
            format="markdown",
            filename=f"analyze-skill-{skill_name}.md",
            description="Antigravity workflow for skill analysis",
        )

    def generate_cursorrules(self, skill_config: dict[str, Any]) -> Instruction:
        """Generate .cursorrules file for Cursor."""
        name = skill_config.get("name", "augur")
        patterns = skill_config.get("patterns", [])

        cursorrules = f"""# Cursor Rules for {name}

## Augur Skill Development Guidelines

### Skill Structure
- Follow Augur skill conventions
- Include SKILL.md with skill definition
- Use patterns: {', '.join(patterns) if patterns else 'basic'}

### Code Style
- Use Python type hints
- Follow PEP 8
- Include docstrings

### Testing
- Write tests for all functions
- Use pytest
- Maintain > 80% coverage

### Dashboard
- Use Next.js/React
- Follow dashboard component patterns
- Include API routes for data operations
"""

        return Instruction(
            content=cursorrules,
            format="text",
            filename=".cursorrules",
            description="Cursor rules file for Augur skill development",
        )

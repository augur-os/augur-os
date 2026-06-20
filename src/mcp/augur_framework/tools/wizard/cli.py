"""
CLI interface for the Augur Skill Wizard.

Provides commands for creating and validating skills from the terminal.
"""

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from src.config.paths import get_project_root
except ImportError:

    def get_project_root() -> Path:
        return _PROJECT_ROOT


app = typer.Typer(
    name='augur-wizard',
    help='Create and manage Augur skills from the command line.',
    add_completion=False,
)

console = Console()


# Available patterns for skill creation
AVAILABLE_PATTERNS = ['inbox', 'database', 'dashboard', 'scheduler', 'rag', 'api', 'scoring']

# Available layers
AVAILABLE_LAYERS = ['vertical', 'horizontal', 'factory']

SKILL_DIR_ARGUMENT = typer.Argument(
    ...,
    help='Path to skill directory to validate',
    exists=True,
    file_okay=False,
    dir_okay=True,
)


def _get_generator_path() -> Path:
    """Get path to the skill generation module."""
    # skill_generation is in mcp-app-factory plugin
    possible_paths = [
        # In monorepo (skill_generation is relative to project root)
        get_project_root() / 'plugins' / 'factory' / 'skills' / 'mcp-app-factory' / 'scripts' / 'skill_generation',
        # Via AUGUR_ROOT
        Path.home()
        / 'Projects'
        / 'augur'
        / 'plugins'
        / 'factory'
        / 'skills'
        / 'mcp-app-factory'
        / 'scripts'
        / 'skill_generation',
    ]

    import os

    if root := os.environ.get('AUGUR_ROOT'):
        possible_paths.insert(
            0, Path(root) / 'plugins' / 'factory' / 'skills' / 'mcp-app-factory' / 'scripts' / 'skill_generation'
        )

    for path in possible_paths:
        if path.exists():
            return path

    return possible_paths[0]  # Return default even if not found


@app.command()
def create(
    name: str | None = typer.Option(
        None,
        '--name',
        '-n',
        help='Skill name in kebab-case (e.g., expense-tracker)',
    ),
    patterns: str | None = typer.Option(
        None,
        '--patterns',
        '-p',
        help=f'Comma-separated patterns: {", ".join(AVAILABLE_PATTERNS)}',
    ),
    layer: str | None = typer.Option(
        None,
        '--layer',
        '-l',
        help=f'Layer: {", ".join(AVAILABLE_LAYERS)}',
    ),
    description: str | None = typer.Option(
        None,
        '--description',
        '-d',
        help='Skill description',
    ),
    interactive: bool = typer.Option(
        False,
        '--interactive',
        '-i',
        help='Run in interactive mode with prompts',
    ),
) -> None:
    """
    Create a new skill with the specified configuration.

    If options are not provided, runs in interactive mode.
    """
    # If any required option is missing, run interactive mode
    if not name or not patterns or not layer or interactive:
        name, patterns, layer, description = _interactive_create(name, patterns, layer, description)

    # Validate inputs
    if not name:
        console.print('[red]Error: Skill name is required[/red]')
        raise typer.Exit(1)

    # Parse patterns
    pattern_list = [p.strip() for p in patterns.split(',')] if patterns else ['database']

    # Validate patterns
    invalid_patterns = [p for p in pattern_list if p not in AVAILABLE_PATTERNS]
    if invalid_patterns:
        console.print(f'[red]Error: Invalid patterns: {", ".join(invalid_patterns)}[/red]')
        console.print(f'Available patterns: {", ".join(AVAILABLE_PATTERNS)}')
        raise typer.Exit(1)

    # Validate layer
    layer = layer or 'vertical'
    if layer not in AVAILABLE_LAYERS:
        console.print(f'[red]Error: Invalid layer: {layer}[/red]')
        console.print(f'Available layers: {", ".join(AVAILABLE_LAYERS)}')
        raise typer.Exit(1)

    # Show creation summary
    console.print(
        Panel(
            f'''[bold]Creating Skill[/bold]
Name: [cyan]{name}[/cyan]
Layer: [green]{layer}[/green]
Patterns: [yellow]{", ".join(pattern_list)}[/yellow]
Description: {description or "(none)"}''',
            title='Skill Wizard',
        )
    )

    # Run the generator
    try:
        result = _run_generator(
            name=name,
            patterns=pattern_list,
            layer=layer,
            description=description,
        )

        if result.get('success'):
            skill_info = result.get('skill', {})
            console.print('\n[green]Skill created successfully![/green]\n')

            # Show results table
            table = Table(title='Created Files')
            table.add_column('Component', style='cyan')
            table.add_column('Status', style='green')

            generated = result.get('generated', {})
            table.add_row('Structure', 'Created' if generated.get('structure') else 'Skipped')
            table.add_row('SKILL.md', 'Created' if generated.get('skill_md') else 'Skipped')
            table.add_row('dashboard.yaml', 'Created' if generated.get('dashboard_yaml') else 'Skipped')
            table.add_row('Tests', 'Created' if generated.get('tests') else 'Skipped')

            console.print(table)

            # Show next steps
            console.print('\n[bold]Next Steps:[/bold]')
            for step in result.get('next_steps', []):
                console.print(f'  - {step}')

            console.print(f'\n[dim]Skill path: {skill_info.get("path")}[/dim]')
        else:
            console.print('[red]Error creating skill:[/red]')
            for error in result.get('errors', ['Unknown error']):
                console.print(f'  - {error}')
            raise typer.Exit(1)

    except ImportError as e:
        console.print(f'[red]Error: Could not import generator module: {e}[/red]')
        console.print('[dim]Make sure you are in the augur monorepo or have AUGUR_ROOT set.[/dim]')
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f'[red]Error: {e}[/red]')
        raise typer.Exit(1) from e


def _interactive_create(
    name: str | None,
    patterns: str | None,
    layer: str | None,
    description: str | None,
) -> tuple[str, str, str, str | None]:
    """Run interactive prompts for skill creation."""
    try:
        import questionary
        from questionary import Style

        custom_style = Style(
            [
                ('qmark', 'fg:cyan bold'),
                ('question', 'bold'),
                ('answer', 'fg:cyan'),
                ('pointer', 'fg:cyan bold'),
                ('highlighted', 'fg:cyan bold'),
                ('selected', 'fg:green'),
            ]
        )

        console.print(
            Panel(
                '[bold]Skill Creation Wizard[/bold]\n' 'Answer the following questions to create a new skill.',
                title='Augur Wizard',
            )
        )

        # Name
        if not name:
            name = questionary.text(
                'Skill name (kebab-case):',
                validate=lambda x: len(x) > 0 and x.replace('-', '').isalnum(),
                style=custom_style,
            ).ask()

        # Layer
        if not layer:
            layer = questionary.select(
                'Select layer:',
                choices=[
                    questionary.Choice('vertical (personal skills)', 'vertical'),
                    questionary.Choice('horizontal (src/lib services)', 'horizontal'),
                    questionary.Choice('factory (development tools)', 'factory'),
                ],
                style=custom_style,
            ).ask()

        # Patterns
        if not patterns:
            pattern_choices = questionary.checkbox(
                'Select patterns (space to toggle):',
                choices=[
                    questionary.Choice('inbox - Process incoming items', 'inbox'),
                    questionary.Choice('database - Store and query data', 'database', checked=True),
                    questionary.Choice('dashboard - Visual metrics', 'dashboard'),
                    questionary.Choice('scheduler - Automated tasks', 'scheduler'),
                    questionary.Choice('rag - Document search', 'rag'),
                    questionary.Choice('api - REST/GraphQL endpoints', 'api'),
                ],
                style=custom_style,
            ).ask()
            patterns = ','.join(pattern_choices) if pattern_choices else 'database'

        # Description
        if not description:
            description = questionary.text(
                'Description (optional):',
                style=custom_style,
            ).ask()

        return name or '', patterns or 'database', layer or 'vertical', description

    except ImportError:
        # Fallback to basic input if questionary not available
        console.print('[yellow]questionary not installed, using basic prompts[/yellow]')

        if not name:
            name = typer.prompt('Skill name (kebab-case)')
        if not layer:
            layer = typer.prompt(f'Layer ({"/".join(AVAILABLE_LAYERS)})', default='vertical')
        if not patterns:
            patterns = typer.prompt('Patterns (comma-separated)', default='database')
        if not description:
            description = typer.prompt('Description (optional)', default='')

        return name, patterns, layer, description if description else None


def _run_generator(
    name: str,
    patterns: list[str],
    layer: str,
    description: str | None,
) -> dict:
    """Run the unified generator to create the skill."""
    from src.mcp.augur_shared.compat import get_skill_generator

    generate_skill = get_skill_generator()

    if generate_skill is None:
        # Fallback: try direct import with path manipulation
        gen_path = _get_generator_path()
        parent_path = str(gen_path.parent.parent)
        if parent_path not in sys.path:
            sys.path.insert(0, parent_path)

        try:
            from skill_generation.unified_generator import generate_skill as _gen

            generate_skill = _gen
        except ImportError:
            return {
                'success': False,
                'errors': ['Skill generator not available. Run within augur monorepo or set AUGUR_ROOT.'],
            }

    config = {
        'source': 'create',
        'name': name,
        'patterns': patterns,
        'layer': layer,
        'description': description or '',
    }

    return generate_skill(config)


@app.command()
def validate(
    skill_dir: Path = SKILL_DIR_ARGUMENT,
) -> None:
    """
    Validate an existing skill directory structure and configuration.
    """
    console.print(f'[bold]Validating skill at:[/bold] {skill_dir}')

    errors = []
    warnings = []

    # Check required files
    required_files = ['SKILL.md', 'dashboard.yaml']
    for filename in required_files:
        filepath = skill_dir / filename
        if not filepath.exists():
            # Also check skill-package subdirectory for SKILL.md
            alt_path = skill_dir / 'skill-package' / filename
            if not alt_path.exists():
                errors.append(f'Missing required file: {filename}')

    # Check SKILL.md format
    skill_md_path = skill_dir / 'SKILL.md'
    if not skill_md_path.exists():
        skill_md_path = skill_dir / 'skill-package' / 'SKILL.md'

    if skill_md_path.exists():
        content = skill_md_path.read_text()
        if not content.startswith('---'):
            warnings.append('SKILL.md should start with YAML frontmatter (---)')

    # Check dashboard.yaml
    dashboard_yaml_path = skill_dir / 'dashboard.yaml'
    if dashboard_yaml_path.exists():
        try:
            import yaml

            with open(dashboard_yaml_path) as f:
                config = yaml.safe_load(f)
            if not config.get('version'):
                warnings.append('dashboard.yaml missing version field')
            if not config.get('hub'):
                errors.append('dashboard.yaml missing hub definition')
            if not config.get('tabs'):
                errors.append('dashboard.yaml missing tabs definition')
        except yaml.YAMLError as e:
            errors.append(f'Invalid dashboard.yaml: {e}')

    # Display results
    if errors:
        console.print('\n[red bold]Validation Failed[/red bold]')
        for error in errors:
            console.print(f'  [red]- {error}[/red]')
    else:
        console.print('\n[green bold]Validation Passed[/green bold]')

    if warnings:
        console.print('\n[yellow]Warnings:[/yellow]')
        for warning in warnings:
            console.print(f'  [yellow]- {warning}[/yellow]')

    if errors:
        raise typer.Exit(1)


@app.command()
def list_patterns() -> None:
    """
    List all available patterns for skill creation.
    """
    table = Table(title='Available Patterns')
    table.add_column('Pattern', style='cyan')
    table.add_column('Description')

    pattern_descriptions = {
        'inbox': 'Process incoming items from external sources',
        'database': 'Store and query structured data (YAML/JSON)',
        'dashboard': 'Visual metrics and KPI displays',
        'scheduler': 'Automated tasks and scheduled jobs',
        'rag': 'Document search and retrieval (RAG)',
        'api': 'REST/GraphQL API endpoints',
        'scoring': 'Score and rank items with algorithms',
    }

    for pattern, desc in pattern_descriptions.items():
        table.add_row(pattern, desc)

    console.print(table)


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == '__main__':
    main()

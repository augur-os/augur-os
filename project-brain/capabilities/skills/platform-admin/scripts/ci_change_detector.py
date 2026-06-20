import os
import sys
import json
import logging
import re
import shutil
from subprocess import CalledProcessError, CompletedProcess, run as subprocess_run  # nosec B404

logger = logging.getLogger(__name__)


def _resolve_command(command: list[str]) -> list[str]:
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess[str]:
    return subprocess_run(_resolve_command(command), **kwargs)  # nosec B603


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def get_changed_files(base_sha, head_sha):
    try:
        cmd = ["git", "diff", "--name-only", base_sha, head_sha]
        result = _run_command(cmd, capture_output=True, text=True, check=True)
        return result.stdout.splitlines()
    except CalledProcessError as e:
        _out(f"Error running git diff: {e}", file=sys.stderr)
        return []


def get_skill_name(package_path):
    skill_md = os.path.join(package_path, "SKILL.md")
    if os.path.exists(skill_md):
        try:
            with open(skill_md, "r") as f:
                content = f.read()
                match = re.search(r"name:\s*(.+)", content)
                if match:
                    return match.group(1).strip()
        except Exception as exc:
            logger.debug("Failed to parse SKILL.md in %s: %s", skill_md, exc)
    return os.path.basename(package_path)


def scan_all_skills():
    """Scan all plugin skills and return full matrix (for nightly/dispatch runs)."""
    skills = {}
    plugins_root = os.path.join(os.getcwd(), "plugins")
    if os.path.exists(plugins_root):
        for bundle in os.listdir(plugins_root):
            bundle_path = os.path.join(plugins_root, bundle, "skills")
            if not os.path.isdir(bundle_path):
                continue
            for d in os.listdir(bundle_path):
                full_path = os.path.join(bundle_path, d)
                if os.path.isdir(full_path):
                    plugin_path = f"plugins/{bundle}/skills/{d}"
                    name = get_skill_name(full_path)
                    skills[name] = {"name": name, "path": plugin_path, "layer": bundle}

    project_brain_skills_root = os.path.join(
        os.getcwd(), "project-brain", "capabilities", "skills"
    )
    if os.path.isdir(project_brain_skills_root):
        for d in os.listdir(project_brain_skills_root):
            full_path = os.path.join(project_brain_skills_root, d)
            if os.path.isdir(full_path):
                skill_path = f"project-brain/capabilities/skills/{d}"
                name = get_skill_name(full_path)
                skills[name] = {"name": name, "path": skill_path, "layer": "project-brain"}

    skill_list = list(skills.values())
    outputs = {
        "matrix": json.dumps(skill_list),
        "has_skills": "true" if skill_list else "false",
        "ops_changed": "true",
        "dashboard_changed": "true",
    }

    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            for k, v in outputs.items():
                f.write(f"{k}={v}\n")
    else:
        _out(json.dumps(outputs, indent=2))


def main():
    # Support --all flag for nightly/dispatch runs
    if "--all" in sys.argv:
        _out("Running in --all mode: scanning all skills...", file=sys.stderr)
        scan_all_skills()
        return

    if len(sys.argv) < 3:
        _out("Usage: python ci_change_detector.py <base_sha> <head_sha>", file=sys.stderr)
        _out("       python ci_change_detector.py --all", file=sys.stderr)
        sys.exit(1)

    base_sha = sys.argv[1]
    head_sha = sys.argv[2]

    _out(f"Detecting changes between {base_sha} and {head_sha}...", file=sys.stderr)

    changed_files = get_changed_files(base_sha, head_sha)

    skills = {}  # Use dict to deduplicate by name
    ops_changed = False
    dashboard_changed = False

    # Scan skill paths: project-brain/capabilities/skills/{skill}/... and plugins/{bundle}/skills/{skill}/...
    shared_vault_pattern = re.compile(r"project-brain/capabilities/skills/([^/]+)/")
    plugin_pattern = re.compile(r"plugins/([^/]+)/skills/([^/]+)/")

    for f in changed_files:
        if f.startswith("apps/dashboard/"):
            dashboard_changed = True

        shared_vault_match = shared_vault_pattern.match(f)
        if shared_vault_match and shared_vault_match.group(1) == "frontend":
            dashboard_changed = True

        plugin_frontend_match = plugin_pattern.match(f)
        if plugin_frontend_match and plugin_frontend_match.group(2) == "frontend":
            dashboard_changed = True

        if f.startswith("src/") and not f.startswith("apps/dashboard/"):
            ops_changed = True

        if f.endswith("/dependencies.yaml") or f.startswith(
            "project-brain/capabilities/skills/platform-admin/data/dependencies.yaml"
        ):
            ops_changed = True

        if shared_vault_match:
            folder_name = shared_vault_match.group(1)
            skill_path = f"project-brain/capabilities/skills/{folder_name}"

            full_path = os.path.join(os.getcwd(), skill_path)
            if os.path.isdir(full_path):
                name = get_skill_name(full_path)
                skills[name] = {"name": name, "path": skill_path, "layer": "project-brain"}

        plugin_match = plugin_pattern.match(f)
        if plugin_match:
            bundle = plugin_match.group(1)
            folder_name = plugin_match.group(2)
            plugin_path = f"plugins/{bundle}/skills/{folder_name}"

            full_path = os.path.join(os.getcwd(), plugin_path)
            if os.path.isdir(full_path):
                name = get_skill_name(full_path)
                skills[name] = {"name": name, "path": plugin_path, "layer": bundle}

    # If Ops changed, we might want to test everything or specific things.
    # The original logic tested ALL skills if ops changed.
    # For now, let's keep the list of detected skills.
    # If ops_changed is true, the workflow might decide to run all test suites or just linting.
    # But usually, if src/lib lib changes, everything that depends on it should be tested.
    # For simplicity, we'll output the explicitly changed skills.
    # The workflow can handle the "test all" case if needed, or we can expand the list here.

    # Actually, in the original YAML:
    # "If src/lib/ops changed, validate all skills"
    # We can replicate this logic.

    if ops_changed:
        _out("Ops layer changed. Adding all skills.", file=sys.stderr)
        # Scan all skills across all bundles.
        plugins_root = os.path.join(os.getcwd(), "plugins")
        if os.path.exists(plugins_root):
            for bundle in os.listdir(plugins_root):
                bundle_path = os.path.join(plugins_root, bundle, "skills")
                if not os.path.isdir(bundle_path):
                    continue
                for d in os.listdir(bundle_path):
                    full_path = os.path.join(bundle_path, d)
                    if os.path.isdir(full_path):
                        plugin_path = f"plugins/{bundle}/skills/{d}"
                        name = get_skill_name(full_path)
                        skills[name] = {"name": name, "path": plugin_path, "layer": bundle}

        project_brain_skills_root = os.path.join(
            os.getcwd(), "project-brain", "capabilities", "skills"
        )
        if os.path.isdir(project_brain_skills_root):
            for d in os.listdir(project_brain_skills_root):
                full_path = os.path.join(project_brain_skills_root, d)
                if os.path.isdir(full_path):
                    skill_path = f"project-brain/capabilities/skills/{d}"
                    name = get_skill_name(full_path)
                    skills[name] = {"name": name, "path": skill_path, "layer": "project-brain"}

    skill_list = list(skills.values())

    # Output JSONs for GitHub Actions
    # We need:
    # matrix (json list of objects)
    # has_skills (boolean)
    # ops_changed (boolean)
    # dashboard_changed (boolean)

    outputs = {
        "matrix": json.dumps(skill_list),
        "has_skills": "true" if skill_list else "false",
        "ops_changed": "true" if ops_changed else "false",
        "dashboard_changed": "true" if dashboard_changed else "false",
    }

    # Print to GITHUB_OUTPUT
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            for k, v in outputs.items():
                f.write(f"{k}={v}\n")
    else:
        # Local debugging
        _out(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()

# Mode: --templates

Template-based onboarding. Instead of showing individual plugins, present a catalog of dashboard templates grouped by hub. The user picks the templates they want, and required plugins are auto-derived and enabled. Falls back to current plugin-based onboarding if `--templates` is not used.

## Steps

1. **Discover templates** — Scan `plugins/ui/templates/{hub}/*.yaml` for all available template YAML files. Parse each file to extract `name`, `description`, `hub`, `icon`, and `requires` fields (see `TemplateYAML` in `apps/dashboard/lib/templates/types.ts` for schema).

2. **Display template catalog** — Group templates by hub and present them as a selectable catalog. For each template show:
   - Template name and description
   - Hub it belongs to
   - Icon (Lucide icon name)
   - Required plugins (from the `requires` field)

   Example catalog format:
   ```
   brain:
     - Library — Reading list and knowledge documents browser (requires: reading-list, knowledge)
     - Memory — ... (requires: ...)
   career:
     - Pipeline — ... (requires: ...)
   life:
     - Home — ... (requires: ...)
     - Wellness — ... (requires: ...)
   ```

3. **User selects templates** — Let the user pick one or more templates from the catalog. Accept template names or IDs (the YAML filename without extension, e.g., `library`, `pipeline`).

4. **Auto-derive required plugins** — For each selected template, collect all entries from its `requires` array. Deduplicate across all selected templates to produce a flat list of required plugins.

5. **Auto-enable plugins** — Enable all required plugins derived in step 4. For each plugin, locate its skill directory (`plugins/{hub}/skills/{skill}/`) and write a `.config` file with `enabled: true` using the `write_config_file(dir_path, enabled=True)` pattern from `src.plugins.skill_config`. If the skill directory does not exist locally (community skill), skip it and note it as missing. This ensures every block in the selected templates has its data source available without the user manually toggling individual plugins.

6. **Write active templates** — Write the user's selections to `get_vault_config_dir()/dashboard/active.yaml`. The file schema maps each hub to its list of active template IDs (see `ActiveTemplates` in `apps/dashboard/lib/templates/types.ts`):
   ```yaml
   brain:
     templates:
       - library
       - memory
   career:
     templates:
       - pipeline
   ```
   If the file already exists, merge new selections with existing entries (do not drop previously activated templates from other hubs).

7. **Confirm** — Display a summary of activated templates and auto-enabled plugins. Inform the user they can customize layouts later through the dashboard UI or by editing override files in `get_vault_config_dir()/dashboard/templates/`.

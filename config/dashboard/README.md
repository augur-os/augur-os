# config/dashboard/

Dashboard configuration that is still central must be classified here. Project/team skill-owned dashboard metadata belongs in `project-brain/capabilities/skills/{skill}/SKILL.md` frontmatter or the owning skill's `augur/` tree.

Do not add new central dashboard YAML without classifying it here.

| File | Classification | Owner | Rule |
|------|----------------|-------|------|
| `cli_parser_profiles.yaml` | legitimate central system config | operation-mode CLI stream parsing | Keep central. Update only when external CLI stream protocols or parser behavior changes; do not migrate to skill metadata. |
| `generated_surfaces.yaml` | legitimate central system policy | dashboard generated-artifact tracking/ignore policy | Keep central. Update whenever dashboard generators add or retire repo-visible generated surfaces. |

Generated files under `config/dashboard/generated/` are derived artifacts and are not hand-maintained policy sources.

Browse per-item action catalogs are not central dashboard config. Put
category-specific actions in the owning skill's `augur/browse-actions.yaml`;
`generated_surfaces.yaml` only classifies the ignored generated registry output.

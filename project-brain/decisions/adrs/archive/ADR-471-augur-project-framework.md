---
status: Implemented
date: '2026-03-22'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- project-framework
- multi-project
- paths
superseded_by: null
---

# ADR-471: Augur Project Framework

## Decision summary

Transform augur-os into a project framework where each clone is an independent project with scoped paths, isolated plugins, and per-project daemons:

## Status notes

 | Flipped to Implemented 2026-05-10 — project.yaml exists at repo root; src/config/paths.py has 5 get_project_* functions with 80+ project_root/project_name references; src/config/path_primitives.py reads project.yaml. Framework shipped.

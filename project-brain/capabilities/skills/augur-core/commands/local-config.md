---
description: Configure per-action AI client routing for local and remote clients.
visibility: core
---

# /local config

Configure per-action AI client routing.

## Usage

```bash
/local config <action-id> <client-id>
/local config <action-id> --clear
/local config --list
/local config --default <client-id>
```

## Behavior

- set an override with `set-client-override`
- clear an override with `set-client-override` and `clear: true`
- list current routing with `resolve-client`
- set the global default with `action_id: "__global__"`


"""Resolve /skillify mode: 'help' / 'optimize' (single token naming an existing skill) / 'create'."""


def resolve_mode(arg, *, skill_exists_fn):
    a = (arg or "").strip()
    if a in ("--help", "-h"):
        return "help"
    tokens = a.split()
    if len(tokens) == 1 and tokens[0] and skill_exists_fn(tokens[0]):
        return "optimize"
    return "create"

"""Combined accuracy+speed score and a deterministic train/validation split."""
import random


def combined(accuracy: float, tokens: int, wall_ms: float, *,
             lam: float, mu: float, baseline_tokens: int, baseline_ms: float) -> float:
    """accuracy minus normalized token + time penalties (relative to the run baseline).
    Higher is better; same accuracy with fewer tokens/less time scores higher."""
    tok_norm = tokens / baseline_tokens if baseline_tokens else 0.0
    ms_norm = wall_ms / baseline_ms if baseline_ms else 0.0
    return accuracy - lam * tok_norm - mu * ms_norm


def split_cases(cases: list, *, validation_frac: float, seed: int) -> tuple[list, list]:
    """Deterministic disjoint split. Returns (train, validation)."""
    items = list(cases)
    if not items:
        return [], []
    rng = random.Random(seed)
    rng.shuffle(items)
    n_val = max(1, round(len(items) * validation_frac))
    validation = items[:n_val]
    train = items[n_val:]
    return train, validation

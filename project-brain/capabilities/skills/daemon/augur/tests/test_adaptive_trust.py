"""Tests for adaptive trust ledger."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ── Setup import path ──────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from skills.daemon.scripts.adaptive.trust_ledger import TrustLedger, CategoryState, LoopState
from skills.daemon.scripts.adaptive.trust_constants import (
    CASCADE_TRUST_FLOOR,
    CONSECUTIVE_FAILURES_TO_DISABLE,
    DORMANT_CLEAN_THRESHOLD,
    MAX_DISABLE_RETRIES,
    MAX_DIFFICULTY,
)


@pytest.fixture
def config():
    """Minimal adaptive_loops.yaml structure as dict."""
# TODO_CLEANUP: This file is 1338 lines — consider splitting into smaller modules
    return {
        "engine": {
            "enabled": True,
            "nightly_time": "03:00",
            "max_concurrent_sessions": 1,
            "session_timeout_minutes": 30,
            "history_retention_days": 30,
        },
        "loops": {
            "code-quality": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 10,
                "budget_growth_rate": 2,
                "categories": {
                    "format": {"enabled": True, "trust": 0.0, "tier": 0},
                    "lint-autofix": {"enabled": True, "trust": 0.0, "tier": 0},
                    "todo-cleanup": {"enabled": False, "trust": 0.0, "tier": 1},
                },
            },
        },
    }


@pytest.fixture
def ledger(tmp_path, config):
    return TrustLedger(config, state_dir=tmp_path)


class TestTrustLedger:
    def test_load_initial_state(self, ledger):
        state = ledger.get_loop_state("code-quality")
        assert state.budget == 10
        assert state.budget_remaining == 10
        assert state.enabled is True
        cat = state.categories["format"]
        assert cat.trust == 0.0
        assert cat.enabled is True

    def test_check_allowed_enabled_category(self, ledger):
        assert ledger.check_allowed("code-quality", "format") is True

    def test_check_allowed_disabled_category(self, ledger):
        assert ledger.check_allowed("code-quality", "todo-cleanup") is False

    def test_check_allowed_no_budget(self, ledger):
        # Exhaust budget
        for _ in range(10):
            ledger.consume_budget("code-quality")
        assert ledger.check_allowed("code-quality", "format") is False

    def test_consume_budget(self, ledger):
        ledger.consume_budget("code-quality")
        state = ledger.get_loop_state("code-quality")
        assert state.budget_remaining == 9

    def test_record_success_increases_trust(self, ledger):
        ledger.record_success("code-quality", "format")
        state = ledger.get_loop_state("code-quality")
        assert state.categories["format"].trust > 0.0
        assert state.categories["format"].success_count == 1

    def test_record_failure_decreases_trust(self, ledger):
        # First give some trust
        for _ in range(5):
            ledger.record_success("code-quality", "format")
        trust_before = ledger.get_loop_state("code-quality").categories["format"].trust
        ledger.record_failure("code-quality", "format")
        trust_after = ledger.get_loop_state("code-quality").categories["format"].trust
        assert trust_after < trust_before

    def test_failure_decrements_budget(self, ledger):
        ledger.record_failure("code-quality", "format")
        state = ledger.get_loop_state("code-quality")
        assert state.budget == 9  # Was 10

    def test_budget_floor_at_1(self, ledger):
        for _ in range(20):
            ledger.record_failure("code-quality", "format")
        state = ledger.get_loop_state("code-quality")
        assert state.budget >= 1

    def test_consecutive_failures_disable_category(self, ledger):
        for _ in range(CONSECUTIVE_FAILURES_TO_DISABLE):
            ledger.record_failure("code-quality", "format")
        state = ledger.get_loop_state("code-quality")
        assert state.categories["format"].enabled is False

    def test_promotion_unlocks_next_tier(self, ledger):
        # 10+ successes and trust > 0.8 should unlock next tier
        for _ in range(20):
            ledger.record_success("code-quality", "format")
        state = ledger.get_loop_state("code-quality")
        assert state.categories["format"].trust > 0.8
        # Check if next tier (todo-cleanup) got enabled
        assert state.categories["todo-cleanup"].enabled is True

    def test_budget_growth_on_consecutive_successes(self, ledger):
        for _ in range(10):
            ledger.record_success("code-quality", "format")
        state = ledger.get_loop_state("code-quality")
        assert state.budget > 10  # Should have grown

    def test_probation_mode(self, ledger):
        # Drive budget to 1
        for _ in range(20):
            ledger.record_failure("code-quality", "lint-autofix")
        state = ledger.get_loop_state("code-quality")
        assert state.probation is True
        # In probation, only tier 0 should be allowed
        assert ledger.check_allowed("code-quality", "lint-autofix") is False
        assert ledger.check_allowed("code-quality", "format") is True

    def test_persist_and_reload(self, tmp_path, config):
        ledger1 = TrustLedger(config, state_dir=tmp_path)
        ledger1.record_success("code-quality", "format")
        ledger1.save()
        # Reload from disk
        ledger2 = TrustLedger(config, state_dir=tmp_path)
        state = ledger2.get_loop_state("code-quality")
        assert state.categories["format"].success_count == 1

    def test_enable_disable_loop(self, ledger):
        ledger.set_loop_enabled("code-quality", False)
        assert ledger.get_loop_state("code-quality").enabled is False
        assert ledger.check_allowed("code-quality", "format") is False

    def test_manual_promote(self, ledger):
        ledger.promote_category("code-quality", "todo-cleanup")
        state = ledger.get_loop_state("code-quality")
        assert state.categories["todo-cleanup"].enabled is True
        assert state.categories["todo-cleanup"].consecutive_failures == 0
        assert state.categories["todo-cleanup"].disable_count == 0

    def test_reset_loop(self, ledger):
        for _ in range(5):
            ledger.record_success("code-quality", "format")
        ledger.reset_loop("code-quality")
        state = ledger.get_loop_state("code-quality")
        assert state.categories["format"].trust == 0.0
        assert state.categories["format"].success_count == 0


def test_promotion_does_not_cascade_tiers(tmp_path):
    """A tier-1 category with high trust should only promote tier 2, not tier 3+."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 200,
                "budget_growth_rate": 1,
                "categories": {
                    "tier0": {"enabled": True, "trust": 0.0, "tier": 0},
                    "tier1": {"enabled": True, "trust": 0.0, "tier": 1},
                    "tier2": {"enabled": False, "trust": 0.0, "tier": 2},
                    "tier3": {"enabled": False, "trust": 0.0, "tier": 3},
                    "tier4": {"enabled": False, "trust": 0.0, "tier": 4},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Drive tier1 past promotion threshold (10+ successes, trust > 0.8)
    for _ in range(30):
        ledger.record_success("test-loop", "tier1")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["tier1"].trust > 0.8
    # tier2 should be promoted (tier1+1 = tier2)
    assert state.categories["tier2"].enabled is True
    # tier3 and tier4 should NOT be promoted — tier1 can only reach tier2
    assert state.categories["tier3"].enabled is False
    assert state.categories["tier4"].enabled is False


def test_explicit_tier_from_config(tmp_path):
    """Verify tier is read from config when present, not inferred from dict order."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "cat-a": {"enabled": True, "trust": 0.5, "tier": 3},
                    "cat-b": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    state = ledger.get_loop_state("test-loop")
    assert state.categories["cat-a"].tier == 3
    assert state.categories["cat-b"].tier == 0


# ── Fix #1: Budget sync from config ──────────────────────────────────────

def test_budget_sync_from_config(tmp_path):
    """reset_budget_cycle picks up budget increases from config."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 15, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Simulate stale trust_state with lower budget (from old config)
    ls = ledger.get_loop_state("test-loop")
    ls.budget = 6
    ls.budget_remaining = 0
    ledger.save()

    ledger.reset_budget_cycle("test-loop")
    ls = ledger.get_loop_state("test-loop")
    assert ls.budget == 15  # Synced up from config
    assert ls.budget_remaining == 15


def test_budget_sync_does_not_decrease(tmp_path):
    """Budget sync doesn't lower budget that grew above config via budget_growth."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    ls = ledger.get_loop_state("test-loop")
    ls.budget = 18  # Grew from successes
    ledger.save()

    ledger.reset_budget_cycle("test-loop")
    ls = ledger.get_loop_state("test-loop")
    assert ls.budget == 18  # Not lowered to config's 10


# ── Fix #4: Promotion cascade ────────────────────────────────────────────

def test_promotion_cascades_through_trusted_tiers(tmp_path):
    """tier-0 with high trust cascades through enabled+trusted tier-1 to promote tier-2."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 200, "budget_growth_rate": 1,
                "categories": {
                    "tier0": {"enabled": True, "trust": 0.0, "tier": 0},
                    "tier1": {"enabled": True, "trust": 0.5, "tier": 1},
                    "tier2": {"enabled": False, "trust": 0.0, "tier": 2},
                    "tier3": {"enabled": False, "trust": 0.0, "tier": 3},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Drive tier0 past promotion threshold
    for _ in range(20):
        ledger.record_success("test-loop", "tier0")
    state = ledger.get_loop_state("test-loop")
    # tier1 already enabled with trust 0.5 >= 0.4 — cascade skips to tier2
    assert state.categories["tier2"].enabled is True
    # tier3 should NOT be promoted (tier2 just enabled with trust 0.0 < 0.4)
    assert state.categories["tier3"].enabled is False


def test_cascade_stops_at_low_trust_tier(tmp_path):
    """Cascade doesn't skip through enabled tiers with trust below CASCADE_TRUST_FLOOR."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 200, "budget_growth_rate": 1,
                "categories": {
                    "tier0": {"enabled": True, "trust": 0.0, "tier": 0},
                    "tier1": {"enabled": True, "trust": CASCADE_TRUST_FLOOR - 0.01, "tier": 1},
                    "tier2": {"enabled": False, "trust": 0.0, "tier": 2},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    for _ in range(20):
        ledger.record_success("test-loop", "tier0")
    state = ledger.get_loop_state("test-loop")
    # tier1 trust remains below the configured cascade floor, so no promotion target.
    assert state.categories["tier2"].enabled is False


# ── Fix #5: No budget shrink on disable ──────────────────────────────────

def test_disable_does_not_shrink_budget(tmp_path):
    """The 3rd consecutive failure disables category but doesn't shrink budget."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    for _ in range(CONSECUTIVE_FAILURES_TO_DISABLE - 1):
        ledger.record_failure("test-loop", "cat")
    budget_before_disable = ledger.get_loop_state("test-loop").budget
    # The disabling failure should not also shrink the budget.
    ledger.record_failure("test-loop", "cat")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["cat"].enabled is False
    assert state.budget == budget_before_disable


# ── Fix #6: Per-category budget growth ───────────────────────────────────

def test_per_category_budget_growth(tmp_path):
    """Budget grows from one category's streak even if another category failed."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 2,
                "categories": {
                    "cat-a": {"enabled": True, "trust": 0.0, "tier": 0},
                    "cat-b": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Failure in cat-b (old behavior would reset cross-category counter)
    ledger.record_failure("test-loop", "cat-b")
    # 10 consecutive successes in cat-a
    for _ in range(10):
        ledger.record_success("test-loop", "cat-a")
    state = ledger.get_loop_state("test-loop")
    # Budget should have grown despite cat-b's failure
    assert state.budget > 10


def test_budget_growth_resets_category_streak(tmp_path):
    """Budget growth resets the triggering category's streak, not all categories."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat-a": {"enabled": True, "trust": 0.0, "tier": 0},
                    "cat-b": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Build streaks in both
    for _ in range(5):
        ledger.record_success("test-loop", "cat-a")
        ledger.record_success("test-loop", "cat-b")
    # Both categories hit their own budget-growth threshold and reset.
    # Push cat-a through another full streak to trigger its next reset.
    for _ in range(5):
        ledger.record_success("test-loop", "cat-a")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["cat-a"].consecutive_successes == 0  # Reset
    assert state.categories["cat-b"].consecutive_successes == 0  # Reset on its own threshold


# ── Fix #7: Clean scan trust credit ──────────────────────────────────────

def test_clean_scan_trust_credit(tmp_path):
    """Clean scan gives small trust bump to enabled categories only."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "enabled-cat": {"enabled": True, "trust": 0.0, "tier": 0},
                    "disabled-cat": {"enabled": False, "trust": 0.0, "tier": 1},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    ledger.record_clean_scan("test-loop")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["enabled-cat"].trust > 0.0  # Got credit
    assert state.categories["disabled-cat"].trust == 0.0  # Skipped
    # Should NOT increment success_count (no real fix happened)
    assert state.categories["enabled-cat"].success_count == 0


def test_clean_scan_accumulates(tmp_path):
    """Multiple clean scans build trust up to saturation, then stop."""
    from skills.daemon.scripts.adaptive.trust_ledger import CLEAN_SCAN_SATURATION

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    for _ in range(50):
        ledger.record_clean_scan("test-loop")
    state = ledger.get_loop_state("test-loop")
    # Only CLEAN_SCAN_SATURATION scans give credit, then saturated
    assert state.categories["cat"].trust > 0.0
    # Trust should be small — only 3 scans at 0.02 increment
    assert state.categories["cat"].trust < 0.1
    # Difficulty should have escalated from saturation
    assert state.categories["cat"].difficulty > 0


# ── Fix #8: Cooldown retry for disabled categories ───────────────────────

def test_cooldown_reenables_disabled_category(tmp_path):
    """Disabled category gets re-enabled after COOLDOWN_CYCLES cycles."""
    from skills.daemon.scripts.adaptive.trust_ledger import COOLDOWN_CYCLES

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 20, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Disable via the configured consecutive-failure threshold.
    for _ in range(CONSECUTIVE_FAILURES_TO_DISABLE):
        ledger.record_failure("test-loop", "cat")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["cat"].enabled is False
    disabled_cycle = state.categories["cat"].disabled_at_cycle

    # Run cycles up to cooldown - 1 (should stay disabled)
    for _ in range(COOLDOWN_CYCLES - 1):
        ledger.reset_budget_cycle("test-loop")
    assert ledger.get_loop_state("test-loop").categories["cat"].enabled is False

    # One more cycle = cooldown reached (base cooldown for first disable)
    notifications = ledger.reset_budget_cycle("test-loop")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["cat"].enabled is True
    assert state.categories["cat"].trust == 0.0  # Reset to zero
    assert state.categories["cat"].consecutive_failures == 0
    assert any("re-enabled" in n for n in notifications)


def test_cooldown_does_not_affect_manually_disabled(tmp_path):
    """Categories disabled via config (disabled_at_cycle=0) are not auto-re-enabled."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": False, "trust": 0.0, "tier": 1},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Run many cycles — should NOT re-enable (disabled_at_cycle = 0)
    for _ in range(20):
        ledger.reset_budget_cycle("test-loop")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["cat"].enabled is False


# ── Difficulty escalation tests ────────────────────────────────────────

def test_difficulty_escalation_on_successes(tmp_path):
    """5 consecutive successes escalate difficulty from 0 to 1."""
    from skills.daemon.scripts.adaptive.trust_ledger import DIFFICULTY_ESCALATION_THRESHOLD

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 50, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    for _ in range(DIFFICULTY_ESCALATION_THRESHOLD):
        ledger.record_success("test-loop", "cat")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["cat"].difficulty == 1


def test_difficulty_deescalation_on_failure(tmp_path):
    """Failure at difficulty 2 drops to 1."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 50, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Manually set difficulty to 2
    ledger.get_loop_state("test-loop").categories["cat"].difficulty = 2
    ledger.record_failure("test-loop", "cat")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["cat"].difficulty == 1


def test_difficulty_caps_at_max(tmp_path):
    """Difficulty doesn't exceed MAX_DIFFICULTY."""
    from skills.daemon.scripts.adaptive.trust_ledger import MAX_DIFFICULTY, DIFFICULTY_ESCALATION_THRESHOLD

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 200, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Run enough successes to try to exceed MAX_DIFFICULTY
    for _ in range(DIFFICULTY_ESCALATION_THRESHOLD * (MAX_DIFFICULTY + 3)):
        ledger.record_success("test-loop", "cat")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["cat"].difficulty <= MAX_DIFFICULTY


def test_mastery_auto_promotes_next_tier(tmp_path):
    """Difficulty reaching MAX auto-promotes next disabled tier."""
    from skills.daemon.scripts.adaptive.trust_ledger import MAX_DIFFICULTY, DIFFICULTY_ESCALATION_THRESHOLD

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 200, "budget_growth_rate": 1,
                "categories": {
                    "tier0": {"enabled": True, "trust": 0.0, "tier": 0},
                    "tier1": {"enabled": False, "trust": 0.0, "tier": 1},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Set difficulty to MAX so next threshold triggers mastery promotion
    ledger.get_loop_state("test-loop").categories["tier0"].difficulty = MAX_DIFFICULTY
    # Run DIFFICULTY_ESCALATION_THRESHOLD more successes at MAX_DIFFICULTY
    for _ in range(DIFFICULTY_ESCALATION_THRESHOLD):
        ledger.record_success("test-loop", "tier0")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["tier1"].enabled is True


def test_clean_scan_saturation_stops_credit(tmp_path):
    """After CLEAN_SCAN_SATURATION clean scans, no trust bump."""
    from skills.daemon.scripts.adaptive.trust_ledger import CLEAN_SCAN_SATURATION

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Exhaust the saturation window
    for _ in range(CLEAN_SCAN_SATURATION):
        ledger.record_clean_scan("test-loop")
    trust_after_saturation = ledger.get_loop_state("test-loop").categories["cat"].trust
    assert trust_after_saturation > 0.0  # Got credit up to saturation

    # One more — should NOT increase trust
    ledger.record_clean_scan("test-loop")
    trust_after_extra = ledger.get_loop_state("test-loop").categories["cat"].trust
    assert trust_after_extra == trust_after_saturation


def test_clean_scan_saturation_escalates_difficulty(tmp_path):
    """Saturated clean scan raises difficulty."""
    from skills.daemon.scripts.adaptive.trust_ledger import CLEAN_SCAN_SATURATION

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Run past saturation
    for _ in range(CLEAN_SCAN_SATURATION + 1):
        ledger.record_clean_scan("test-loop")
    state = ledger.get_loop_state("test-loop")
    assert state.categories["cat"].difficulty == 1


def test_record_convergence_rewards_issue_decay(tmp_path):
    """Resolving recurring actionable fingerprints increases trust."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.2, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    ledger.record_convergence(
        "test-loop",
        "cat",
        issues=[{"kind": "actionable", "fingerprint": "abc"}],
    )
    trust_before_resolution = ledger.get_loop_state("test-loop").categories["cat"].trust

    ledger.record_convergence("test-loop", "cat", issues=[])
    cs = ledger.get_loop_state("test-loop").categories["cat"]

    assert cs.trust > trust_before_resolution
    assert cs.issue_decay_streak == 1
    assert cs.strategy == "scan"


def test_record_convergence_enters_self_repair_on_stagnation(tmp_path):
    """Repeated unchanged actionable fingerprints at low trust trigger self-repair."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.1, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)

    ledger.record_convergence(
        "test-loop",
        "cat",
        issues=[{"kind": "actionable", "fingerprint": "abc"}],
    )
    notifications = ledger.record_convergence(
        "test-loop",
        "cat",
        issues=[{"kind": "actionable", "fingerprint": "abc"}],
    )
    cs = ledger.get_loop_state("test-loop").categories["cat"]

    assert cs.strategy == "self-repair"
    assert cs.stagnation_streak >= 2
    assert cs.difficulty >= 2
    assert any("self-repair mode" in msg for msg in notifications)


def test_record_convergence_does_not_enter_dormant_without_snapshot_fingerprint(tmp_path):
    """Dormant mode requires snapshot support so categories can wake later."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 10,
                "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    cs.difficulty = MAX_DIFFICULTY
    cs.consecutive_clean_scans = DORMANT_CLEAN_THRESHOLD

    notifications = ledger.record_convergence(
        "test-loop",
        "cat",
        issues=[],
        snapshot_fingerprint="",
    )

    assert cs.strategy == "scan"
    assert not any("entered dormant mode" in msg for msg in notifications)


def test_clean_scan_streak_resets_on_actions(tmp_path):
    """Finding actions resets consecutive_clean_scans."""
    from skills.daemon.scripts.adaptive.trust_ledger import CLEAN_SCAN_SATURATION

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Build up clean scan streak
    for _ in range(CLEAN_SCAN_SATURATION):
        ledger.record_clean_scan("test-loop")
    assert ledger.get_loop_state("test-loop").categories["cat"].consecutive_clean_scans == CLEAN_SCAN_SATURATION

    # Reset via engine path
    ledger.reset_clean_scan_streaks("test-loop")
    assert ledger.get_loop_state("test-loop").categories["cat"].consecutive_clean_scans == 0


# ── Fix: Exponential backoff cooldown ──────────────────────────────────

def test_exponential_backoff_cooldown(tmp_path):
    """Second disable doubles the cooldown period."""
    from skills.daemon.scripts.adaptive.trust_ledger import COOLDOWN_CYCLES

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 50, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)

    # First disable
    for _ in range(CONSECUTIVE_FAILURES_TO_DISABLE):
        ledger.record_failure("test-loop", "cat")
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    assert cs.enabled is False
    assert cs.disable_count == 1

    # Wait base cooldown (5 cycles) → re-enabled
    for _ in range(COOLDOWN_CYCLES):
        ledger.reset_budget_cycle("test-loop")
    assert ledger.get_loop_state("test-loop").categories["cat"].enabled is True

    # Second disable
    for _ in range(CONSECUTIVE_FAILURES_TO_DISABLE):
        ledger.record_failure("test-loop", "cat")
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    assert cs.enabled is False
    assert cs.disable_count == 2

    # Base cooldown (5 cycles) should NOT re-enable this time
    for _ in range(COOLDOWN_CYCLES):
        ledger.reset_budget_cycle("test-loop")
    assert ledger.get_loop_state("test-loop").categories["cat"].enabled is False

    # Need double cooldown (10 total - already did 5)
    for _ in range(COOLDOWN_CYCLES):
        ledger.reset_budget_cycle("test-loop")
    assert ledger.get_loop_state("test-loop").categories["cat"].enabled is True


def test_permanent_disable_after_max_retries(tmp_path):
    """After MAX_DISABLE_RETRIES disables, category stays permanently disabled."""
    from skills.daemon.scripts.adaptive.trust_ledger import COOLDOWN_CYCLES, MAX_DISABLE_RETRIES

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 200, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)

    # Cycle through disable/re-enable MAX_DISABLE_RETRIES times
    for i in range(MAX_DISABLE_RETRIES):
        # Disable via the configured consecutive-failure threshold.
        for _ in range(CONSECUTIVE_FAILURES_TO_DISABLE):
            ledger.record_failure("test-loop", "cat")
        cs = ledger.get_loop_state("test-loop").categories["cat"]
        assert cs.enabled is False
        assert cs.disable_count == i + 1

        if i < MAX_DISABLE_RETRIES - 1:
            # Wait enough cycles for exponential cooldown
            cooldown = COOLDOWN_CYCLES * (2 ** i)
            for _ in range(cooldown):
                ledger.reset_budget_cycle("test-loop")
            assert ledger.get_loop_state("test-loop").categories["cat"].enabled is True

    # After MAX_DISABLE_RETRIES, no amount of cycles should re-enable
    for _ in range(500):
        ledger.reset_budget_cycle("test-loop")
    assert ledger.get_loop_state("test-loop").categories["cat"].enabled is False
    assert ledger.get_loop_state("test-loop").categories["cat"].disable_count == MAX_DISABLE_RETRIES


def test_disable_count_persists_across_reload(tmp_path):
    """Save/load preserves disable_count."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger1 = TrustLedger(config, state_dir=tmp_path)
    cs = ledger1.get_loop_state("test-loop").categories["cat"]
    cs.disable_count = 2
    cs.enabled = False
    cs.disabled_at_cycle = 5
    ledger1.save()

    ledger2 = TrustLedger(config, state_dir=tmp_path)
    cs2 = ledger2.get_loop_state("test-loop").categories["cat"]
    assert cs2.disable_count == 2
    assert cs2.enabled is False


def test_reset_loop_clears_disable_count(tmp_path):
    """reset_loop clears disable_count, allowing fresh retry."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 50, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    # Drive to permanent disable
    for _ in range(MAX_DISABLE_RETRIES * CONSECUTIVE_FAILURES_TO_DISABLE):
        ledger.record_failure("test-loop", "cat")
        # Re-enable manually between sets to accumulate disable_count
        cs = ledger.get_loop_state("test-loop").categories["cat"]
        if not cs.enabled and cs.disable_count < MAX_DISABLE_RETRIES:
            cs.enabled = True
            cs.consecutive_failures = 0
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    assert cs.disable_count >= MAX_DISABLE_RETRIES

    # Reset should clear everything
    ledger.reset_loop("test-loop")
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    assert cs.disable_count == 0
    assert cs.enabled is True


def test_promotion_skips_permanently_disabled(tmp_path):
    """Promotion and mastery-promotion skip permanently disabled categories."""
    from skills.daemon.scripts.adaptive.trust_ledger import (
        PROMOTION_MIN_SUCCESSES,
        MAX_DISABLE_RETRIES,
    )

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 200, "budget_growth_rate": 1,
                "categories": {
                    "tier0": {"enabled": True, "trust": 0.0, "tier": 0},
                    "tier1": {"enabled": False, "trust": 0.0, "tier": 1},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)

    # Permanently disable tier1
    cs1 = ledger.get_loop_state("test-loop").categories["tier1"]
    cs1.disable_count = MAX_DISABLE_RETRIES

    # Drive tier0 to promotion threshold
    for _ in range(PROMOTION_MIN_SUCCESSES + 1):
        ledger.record_success("test-loop", "tier0")

    # tier1 should NOT be promoted (permanently disabled)
    assert ledger.get_loop_state("test-loop").categories["tier1"].enabled is False


def test_difficulty_persists_across_reload(tmp_path):
    """Save/load preserves difficulty and consecutive_clean_scans."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger1 = TrustLedger(config, state_dir=tmp_path)
    cs = ledger1.get_loop_state("test-loop").categories["cat"]
    cs.difficulty = 3
    cs.consecutive_clean_scans = 2
    ledger1.save()

    # Reload
    ledger2 = TrustLedger(config, state_dir=tmp_path)
    cs2 = ledger2.get_loop_state("test-loop").categories["cat"]
    assert cs2.difficulty == 3
    assert cs2.consecutive_clean_scans == 2


def test_clean_loop_streak_and_forced_deep_persist(tmp_path):
    """Loop clean streaks and forced-deep flags survive save/load."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    assert ledger.note_clean_loop("test-loop") == 1
    ledger.arm_forced_deep_scan("test-loop", "cat", runs=2)
    ledger.consume_forced_deep_scan("test-loop", "cat")
    ledger.mark_completed_expansion("test-loop", "cat->cat-advanced@d2")
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    cs.self_repair_count = 2
    cs.self_repair_successes = 1
    cs.issue_cycles = 4
    cs.false_positive_signal_count = 1
    ledger.save()

    ledger2 = TrustLedger(config, state_dir=tmp_path)
    state = ledger2.get_loop_state("test-loop")
    assert state.consecutive_clean_cycles == 1
    assert state.categories["cat"].force_deep_runs_remaining == 1
    assert state.categories["cat"].self_repair_successes == 1
    assert state.categories["cat"].issue_cycles == 4
    assert state.categories["cat"].false_positive_signal_count == 1
    assert ledger2.has_completed_expansion("test-loop", "cat->cat-advanced@d2") is True

    ledger2.reset_clean_loop_streak("test-loop")
    assert ledger2.get_loop_state("test-loop").consecutive_clean_cycles == 0


# ── check_consistency tests ───────────────────────────────────────────

def test_check_consistency_fixes_zombie_enabled(tmp_path):
    """enabled=True + disable_count >= MAX_DISABLE_RETRIES → enabled=False."""
    from skills.daemon.scripts.adaptive.trust_ledger import MAX_DISABLE_RETRIES

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    cs.disable_count = MAX_DISABLE_RETRIES  # Zombie state

    fixes = ledger.check_consistency("test-loop")
    assert len(fixes) >= 1
    assert any("enabled" in f and "disable_count" in f for f in fixes)
    assert ledger.get_loop_state("test-loop").categories["cat"].enabled is False


def test_check_consistency_fixes_uncaught_disable(tmp_path):
    """enabled=True + 3 consecutive failures → disabled."""
    from skills.daemon.scripts.adaptive.trust_ledger import CONSECUTIVE_FAILURES_TO_DISABLE

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    cs.consecutive_failures = CONSECUTIVE_FAILURES_TO_DISABLE

    fixes = ledger.check_consistency("test-loop")
    assert len(fixes) >= 1
    assert any("consecutive failures" in f for f in fixes)
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    assert cs.enabled is False
    assert cs.disable_count == 1


def test_check_consistency_clamps_negative_budget(tmp_path):
    """budget_remaining < 0 → clamped to 0."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    ledger.get_loop_state("test-loop").budget_remaining = -5

    fixes = ledger.check_consistency("test-loop")
    assert any("negative" in f for f in fixes)
    assert ledger.get_loop_state("test-loop").budget_remaining == 0


def test_check_consistency_fixes_stale_disable_cycle(tmp_path):
    """disabled_at_cycle > cycle_count → reset to -1."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": False, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    ls = ledger.get_loop_state("test-loop")
    ls.cycle_count = 5
    ls.categories["cat"].disabled_at_cycle = 100  # Stale

    fixes = ledger.check_consistency("test-loop")
    assert any("disabled_at_cycle" in f for f in fixes)
    assert ledger.get_loop_state("test-loop").categories["cat"].disabled_at_cycle == -1


def test_check_consistency_no_save_when_clean(tmp_path):
    """No issues → no save call."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)

    # Record initial state file mtime
    ledger.save()
    import os
    mtime_before = os.path.getmtime(tmp_path / "trust_state.json")

    # Small sleep to ensure mtime would differ if save were called
    import time
    time.sleep(0.05)

    fixes = ledger.check_consistency("test-loop")
    assert fixes == []

    mtime_after = os.path.getmtime(tmp_path / "trust_state.json")
    assert mtime_before == mtime_after


def test_check_consistency_unknown_loop(tmp_path):
    """Unknown loop returns empty list."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {},
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    assert ledger.check_consistency("nonexistent") == []


# ── diagnose tests ────────────────────────────────────────────────────

def test_diagnose_detects_zombie_enabled(tmp_path):
    """Returns critical issue for zombie state."""
    from skills.daemon.scripts.adaptive.trust_ledger import MAX_DISABLE_RETRIES

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    cs.disable_count = MAX_DISABLE_RETRIES

    report = ledger.diagnose()
    critical = [i for i in report["issues"] if i["severity"] == "critical"]
    assert any("Zombie" in i["issue"] for i in critical)
    assert report["summary"]["critical"] >= 1


def test_diagnose_detects_death_spiral(tmp_path):
    """5+ same-action failures in journal → critical."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    journal_entries = [
        {"loop": "test-loop", "action": "fix-lint", "category": "cat", "result": "failure"}
        for _ in range(6)
    ]

    report = ledger.diagnose(journal_entries=journal_entries)
    critical = [i for i in report["issues"] if i["severity"] == "critical"]
    assert any("Death spiral" in i["issue"] for i in critical)


def test_diagnose_detects_budget_exhaustion(tmp_path):
    """budget_remaining=0 → warning."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    ledger.get_loop_state("test-loop").budget_remaining = 0

    report = ledger.diagnose()
    warnings = [i for i in report["issues"] if i["severity"] == "warning"]
    assert any("Budget exhausted" in i["issue"] for i in warnings)
    assert report["summary"]["warning"] >= 1


def test_diagnose_detects_permanently_disabled(tmp_path):
    """disable_count >= MAX_DISABLE_RETRIES → critical."""
    from skills.daemon.scripts.adaptive.trust_ledger import MAX_DISABLE_RETRIES

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": False, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    ledger.get_loop_state("test-loop").categories["cat"].disable_count = MAX_DISABLE_RETRIES

    report = ledger.diagnose()
    criticals = [i for i in report["issues"] if i["severity"] == "critical"]
    assert any("Permanently disabled" in i["issue"] for i in criticals)
    assert report["summary"]["critical"] >= 1


def test_diagnose_detects_script_errors(tmp_path):
    """Journal entries with tracebacks → warning."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    journal_entries = [
        {
            "loop": "test-loop", "action": "rebuild-index",
            "category": "cat", "result": "failure",
            "error": "Traceback (most recent call last): TypeError: unsupported operand",
        },
    ]

    report = ledger.diagnose(journal_entries=journal_entries)
    warnings = [i for i in report["issues"] if i["severity"] == "warning"]
    assert any("Script error" in i["issue"] for i in warnings)


def test_diagnose_empty_state(tmp_path):
    """Empty state returns clean report."""
    config = {"loops": {}}
    ledger = TrustLedger(config, state_dir=tmp_path)
    report = ledger.diagnose()
    assert report["summary"]["total_issues"] == 0
    assert report["issues"] == []


# ── Dead end regression tests ─────────────────────────────────────────

def test_promote_survives_consistency_check(tmp_path):
    """Promoting a permanently disabled category must survive check_consistency.

    Regression: promote_category only set enabled=True without resetting
    consecutive_failures/disable_count, so check_consistency immediately
    re-disabled it on the next cycle.
    """
    from skills.daemon.scripts.adaptive.trust_ledger import MAX_DISABLE_RETRIES

    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)

    # Drive to permanently disabled state
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    cs.enabled = False
    cs.consecutive_failures = 3
    cs.disable_count = MAX_DISABLE_RETRIES
    cs.disabled_at_cycle = 5

    # Promote
    ledger.promote_category("test-loop", "cat")
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    assert cs.enabled is True
    assert cs.consecutive_failures == 0
    assert cs.disable_count == 0

    # check_consistency must NOT undo the promote
    fixes = ledger.check_consistency("test-loop")
    assert fixes == []
    assert ledger.get_loop_state("test-loop").categories["cat"].enabled is True


def test_promote_clears_stale_failures(tmp_path):
    """Promote resets consecutive_failures so category isn't immediately re-disabled."""
    config = {
        "loops": {
            "test-loop": {
                "enabled": True, "trigger": "nightly",
                "budget": 10, "budget_growth_rate": 1,
                "categories": {
                    "cat": {"enabled": False, "trust": 0.0, "tier": 0},
                },
            },
        },
    }
    ledger = TrustLedger(config, state_dir=tmp_path)
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    cs.consecutive_failures = 5  # Stale high value
    cs.disable_count = 1

    ledger.promote_category("test-loop", "cat")
    cs = ledger.get_loop_state("test-loop").categories["cat"]
    assert cs.enabled is True
    assert cs.consecutive_failures == 0
    assert cs.disable_count == 0
    assert cs.disabled_at_cycle == -1
    assert cs.trust == 0.0

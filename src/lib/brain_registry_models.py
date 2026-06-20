from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePath, PurePosixPath
from typing import Optional


class BrainType(str, Enum):
    GLOBAL = "global"
    PERSONAL = "personal"
    TEAM = "team"
    PROJECT = "project"


class GitArrangement(str, Enum):
    STANDALONE = "standalone"
    BUNDLED = "bundled"
    UNTRACKED = "untracked"


@dataclass(frozen=True)
class GitConfig:
    arrangement: GitArrangement
    remote: Optional[str] = None
    branch: str = "main"
    auto_commit: bool = True
    auto_push: bool = True
    host_repo: Optional[PurePath] = None

    def __post_init__(self) -> None:
        if self.host_repo is not None:
            object.__setattr__(self, "host_repo", _normalize_cross_platform_path(self.host_repo))
        if self.arrangement is GitArrangement.BUNDLED and self.host_repo is None:
            raise ValueError("bundled arrangement requires host_repo")
        if self.arrangement is GitArrangement.STANDALONE and self.host_repo is not None:
            raise ValueError("standalone arrangement must not set host_repo")
        if self.host_repo is not None and not _is_cross_platform_absolute(self.host_repo):
            raise ValueError("host_repo must be an absolute path")


@dataclass(frozen=True)
class PropagationPolicy:
    allow_from: tuple[str, ...] = ()
    allow_to: tuple[str, ...] = ()


_VALID_WRITE_POLICIES = frozenset({"free", "packets_only", "read_only"})


@dataclass(frozen=True)
class Brain:
    id: str
    type: BrainType
    data_root: PurePath
    git: GitConfig
    description: Optional[str] = None
    write_policy: str = "free"
    auto_activate_cwd_under: tuple[PurePath, ...] = ()
    propagation: PropagationPolicy = field(default_factory=PropagationPolicy)
    skills_allow: Optional[tuple[str, ...]] = None
    skills_deny: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", _normalize_cross_platform_path(self.data_root))
        object.__setattr__(
            self,
            "auto_activate_cwd_under",
            tuple(_normalize_cross_platform_path(path) for path in self.auto_activate_cwd_under),
        )
        if not _is_cross_platform_absolute(self.data_root):
            raise ValueError(f"data_root must be absolute: {self.data_root}")
        if self.write_policy not in _VALID_WRITE_POLICIES:
            raise ValueError(f"unknown write_policy: {self.write_policy}")
        for path in self.auto_activate_cwd_under:
            if not _is_cross_platform_absolute(path):
                raise ValueError(f"auto_activate_cwd_under path must be absolute: {path}")


def _normalize_cross_platform_path(path: PurePath) -> PurePath:
    """Preserve POSIX absolute registry paths when running on Windows."""
    text = str(path)
    if not path.is_absolute() and text.startswith("\\") and not text.startswith("\\\\"):
        return PurePosixPath(text.replace("\\", "/"))
    return path


def _is_cross_platform_absolute(path: PurePath) -> bool:
    return path.is_absolute() or (isinstance(path, PurePosixPath) and str(path).startswith("/"))


@dataclass(frozen=True)
class BrainRegistry:
    version: int
    brains: dict[str, Brain]

    def __post_init__(self) -> None:
        for key, brain in self.brains.items():
            if key != brain.id:
                raise ValueError(f"registry key '{key}' does not match brain id '{brain.id}'")
        self._enforce_singleton_tier(BrainType.PERSONAL, "personal")
        self._enforce_singleton_tier(BrainType.GLOBAL, "global")

    def _enforce_singleton_tier(self, brain_type: BrainType, label: str) -> None:
        matches = [b.id for b in self.brains.values() if b.type is brain_type]
        if len(matches) > 1:
            raise ValueError(f"registry must hold at most one {label} brain, found: {sorted(matches)}")

    def get(self, brain_id: str) -> Optional[Brain]:
        return self.brains.get(brain_id)

    def ids(self) -> list[str]:
        return list(self.brains.keys())

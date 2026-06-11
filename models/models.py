"""Data models for Claude Manage."""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class SkillType(str, Enum):
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    STANDALONE_MD = "standalone-md"


class SkillStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    BROKEN = "broken"


@dataclass
class SkillFrontmatter:
    name: str = ""
    description: str = ""
    invocation: str = ""
    triggers: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "invocation": self.invocation,
            "triggers": self.triggers,
        }


@dataclass
class Skill:
    name: str
    path: Path
    type: SkillType
    status: SkillStatus = SkillStatus.ACTIVE
    symlink_target: Optional[str] = None
    skill_md_path: Optional[Path] = None
    frontmatter: Optional[SkillFrontmatter] = None
    files: list[str] = field(default_factory=list)
    description_cn: str = ""

    @property
    def display_name(self) -> str:
        if self.frontmatter and self.frontmatter.name:
            return self.frontmatter.name
        return self.name

    @property
    def display_description(self) -> str:
        if self.frontmatter and self.frontmatter.description:
            return self.frontmatter.description
        return ""

    @property
    def status_icon(self) -> str:
        if self.status == SkillStatus.ACTIVE:
            return "✓"
        elif self.status == SkillStatus.DISABLED:
            return "—"
        elif self.status == SkillStatus.BROKEN:
            return "✗"
        return "?"


@dataclass
class Plugin:
    name: str
    version: str
    description: str
    author: str = ""
    author_email: str = ""
    homepage: str = ""
    repository: str = ""
    license: str = ""
    marketplace: str = ""
    install_path: Path = field(default_factory=Path)
    skills: list['PluginSkill'] = field(default_factory=list)
    enabled: bool = True
    description_cn: str = ""


@dataclass
class PluginSkill:
    name: str
    description: str = ""
    path: Path = field(default_factory=Path)
    enabled: bool = True


@dataclass
class MCPServer:
    name: str
    type: str  # stdio, sse, etc.
    command: str = ""
    args: list[str] = field(default_factory=list)
    url: str = ""
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class Hook:
    event: str
    matcher: str
    type: str  # command, http
    command: str = ""
    shell: str = ""
    timeout: int = 60
    is_async: bool = True
    enabled: bool = True
    raw_index: int = 0  # position in the entries array


@dataclass
class MemoryFile:
    name: str  # slug filename without .md
    path: Path
    description: str = ""
    memory_type: str = ""  # user, feedback, project, reference
    content: str = ""
    size: int = 0


@dataclass
class ClaudeMdFile:
    path: Path
    label: str  # "全局" or project name
    content: str = ""
    size: int = 0
    is_global: bool = False


@dataclass
class DashboardSummary:
    skill_count: int = 0
    skill_active: int = 0
    skill_disabled: int = 0
    skill_broken: int = 0
    plugin_count: int = 0
    mcp_count: int = 0
    hook_count: int = 0
    memory_count: int = 0
    claudemd_count: int = 0
    claude_dir: str = ""

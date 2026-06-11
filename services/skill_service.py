"""Skill service — discovers, manages, and imports Claude Code skills."""
import os
import json
import re
import shutil
from pathlib import Path
from typing import Optional

import yaml

from models.models import (
    Skill, SkillType, SkillStatus, SkillFrontmatter,
)
from services.claude_config import ClaudeConfigService


def _parse_frontmatter(md_path: Path) -> Optional[SkillFrontmatter]:
    """Extract YAML frontmatter from a markdown file."""
    try:
        text = md_path.read_text(encoding='utf-8')
    except OSError:
        return None

    # Look for YAML frontmatter between --- delimiters
    if not text.startswith('---'):
        return None

    end = text.find('---', 3)
    if end == -1:
        return None

    yaml_str = text[3:end].strip()
    if not yaml_str:
        return None

    try:
        fm = yaml.safe_load(yaml_str)
    except yaml.YAMLError:
        return None

    if not isinstance(fm, dict):
        return None

    name = fm.get('name', '')
    desc = fm.get('description', '')
    # description could be a list (multi-line) or string
    if isinstance(desc, list):
        desc = ' '.join(str(d) for d in desc)

    return SkillFrontmatter(
        name=str(name) if name else '',
        description=str(desc) if desc else '',
        invocation=f"/{name}" if name else '',
        triggers=_extract_triggers(str(desc)),
    )


def _extract_triggers(desc: str) -> list[str]:
    """Extract trigger keywords from description text."""
    triggers = []
    patterns = [
        r'Triggers?\s*(?:include|on)?:\s*([^.]*)',
        r'Use when\s*(?:the user\s*)?(asks?|needs?|wants?)\s*(?:to\s*)?([^.]*)',
    ]
    for pat in patterns:
        m = re.search(pat, desc, re.IGNORECASE)
        if m:
            part = m.group(1) if m.lastindex >= 1 else m.group(0)
            # Extract keywords
            words = re.findall(r'"([^"]+)"', part)
            if not words:
                words = [w.strip() for w in part.split(',') if len(w.strip()) > 3]
            triggers.extend(words)
            break
    return triggers[:5]


def _is_symlink(path: Path) -> bool:
    """Check if path is a symlink / reparse point."""
    try:
        os.readlink(str(path))
        return True
    except OSError:
        pass
    # Check for Git Bash text symlink
    if path.is_file():
        try:
            content = path.read_text(encoding='utf-8').strip()
            if content and len(content) < 512 and (
                    content.startswith('/') or content.startswith('C:') or
                    content.startswith('D:') or content.startswith('E:')):
                return True
        except OSError:
            pass
    return False


def _read_symlink_target(path: Path) -> Optional[str]:
    """Get symlink target path."""
    try:
        target = os.readlink(str(path))
        return target
    except OSError:
        pass
    # Git Bash text symlink
    try:
        content = path.read_text(encoding='utf-8').strip()
        if content and len(content) < 512:
            return content
    except OSError:
        pass
    return None


def _list_skill_files(skill_dir: Path) -> list[str]:
    """List all files in a skill directory (relative paths)."""
    if not skill_dir.is_dir():
        return []
    files = []
    for root, dirs, filenames in os.walk(str(skill_dir)):
        for f in filenames:
            full = Path(root) / f
            rel = full.relative_to(skill_dir)
            files.append(str(rel).replace('\\', '/'))
    return sorted(files)


class SkillService:
    """Manages Claude Code skills."""

    def __init__(self, config: ClaudeConfigService):
        self.config = config

    def list_all(self) -> list[Skill]:
        """Discover all skills in the skills directory."""
        skills: list[Skill] = []
        skills_dir = self.config.skills_dir

        if not skills_dir.exists():
            return skills

        entries = sorted(os.listdir(str(skills_dir)))
        for entry_name in entries:
            entry_path = skills_dir / entry_name
            skill = self._detect_skill(entry_path)
            if skill:
                skills.append(skill)

        return skills

    def _detect_skill(self, path: Path) -> Optional[Skill]:
        """Detect skill type from a filesystem entry."""
        name = path.name

        # Symlink
        if _is_symlink(path):
            target = _read_symlink_target(path)
            skill = Skill(
                name=name,
                path=path,
                type=SkillType.SYMLINK,
                symlink_target=target,
            )
            actual_target = Path(target) if target else None
            if not target or (actual_target and not actual_target.exists()):
                skill.status = SkillStatus.BROKEN
            if actual_target and actual_target.exists():
                skill_md = actual_target / "SKILL.md"
                if skill_md.exists():
                    skill.skill_md_path = skill_md
                    skill.frontmatter = _parse_frontmatter(skill_md)
                    if skill.frontmatter and skill.frontmatter.name:
                        skill.name = skill.frontmatter.name
                    skill.files = _list_skill_files(actual_target)
                else:
                    skill.status = SkillStatus.BROKEN
            return skill

        # Directory
        if path.is_dir():
            skill_md = path / "SKILL.md"
            skill_md_disabled = path / "SKILL.md.disabled"

            if skill_md.exists():
                fm = _parse_frontmatter(skill_md)
                skill = Skill(
                    name=fm.name if fm else name,
                    path=path,
                    type=SkillType.DIRECTORY,
                    skill_md_path=skill_md,
                    frontmatter=fm,
                    files=_list_skill_files(path),
                )
                return skill

            if skill_md_disabled.exists():
                fm = _parse_frontmatter(skill_md_disabled)
                skill = Skill(
                    name=fm.name if fm else name,
                    path=path,
                    type=SkillType.DIRECTORY,
                    status=SkillStatus.DISABLED,
                    skill_md_path=skill_md_disabled,
                    frontmatter=fm,
                )
                return skill

            # Directory without SKILL.md — might be a regular directory
            return None

        # Standalone .md file
        if name.endswith('.md'):
            skill_name = name[:-3]  # remove .md
            fm = _parse_frontmatter(path)
            skill = Skill(
                name=fm.name if fm else skill_name,
                path=path,
                type=SkillType.STANDALONE_MD,
                skill_md_path=path,
                frontmatter=fm,
            )
            return skill

        # Standalone .md.disabled
        if name.endswith('.md.disabled'):
            skill_name = name[:-12]  # remove .md.disabled
            fm = _parse_frontmatter(path)
            skill = Skill(
                name=fm.name if fm else skill_name,
                path=path,
                type=SkillType.STANDALONE_MD,
                status=SkillStatus.DISABLED,
                skill_md_path=path,
                frontmatter=fm,
            )
            return skill

        return None

    def toggle(self, skill_name: str) -> bool:
        """Toggle a skill between enabled/disabled by renaming its SKILL.md."""
        skills = self.list_all()
        target = None
        for s in skills:
            if s.name == skill_name:
                target = s
                break

        if not target:
            return False

        if target.status == SkillStatus.BROKEN:
            return False

        md_path = target.skill_md_path
        if not md_path or not md_path.exists():
            return False

        if target.status == SkillStatus.ACTIVE:
            # Disable: SKILL.md → SKILL.md.disabled
            new_path = Path(str(md_path) + '.disabled')
            try:
                shutil.move(str(md_path), str(new_path))
                return True
            except OSError:
                return False
        else:
            # Enable: SKILL.md.disabled → SKILL.md
            if str(md_path).endswith('.disabled'):
                new_path = Path(str(md_path)[:-9])  # remove .disabled
                try:
                    shutil.move(str(md_path), str(new_path))
                    return True
                except OSError:
                    return False

        return False

    def delete(self, skill_name: str) -> bool:
        """Delete a skill (directory, symlink, or standalone file)."""
        skills = self.list_all()
        target = None
        for s in skills:
            if s.name == skill_name:
                target = s
                break

        if not target:
            return False

        try:
            path = target.path
            if path.is_dir() and not _is_symlink(path):
                shutil.rmtree(str(path))
            else:
                path.unlink()
            return True
        except OSError:
            return False

    def get_details(self, skill_name: str) -> Optional[Skill]:
        """Get full details for a specific skill."""
        for s in self.list_all():
            if s.name == skill_name:
                return s
        return None

    def load_translations(self) -> dict[str, str]:
        """Load cached translations {skill_name: cn_description}.

        Cache stores {text_key: cn_text} for dedup; this method maps
        text keys back to skill names so the frontend can look up by name.
        """
        cache = self.config.read_json(self.config.translate_cache_path, default={})
        skill_texts = cache.get("skills", {})
        if not skill_texts:
            return {}

        name_to_cn = {}
        for skill in self.list_all():
            if skill.display_description:
                text_key = skill.display_description.strip().lower()[:200]
                if text_key in skill_texts:
                    name_to_cn[skill.name] = skill_texts[text_key]
        return name_to_cn

    def load_plugin_translations(self) -> dict[str, str]:
        """Load cached plugin translations {plugin_name: cn_description}."""
        from services.plugin_service import PluginService
        cache = self.config.read_json(self.config.translate_cache_path, default={})
        plugin_texts = cache.get("plugins", {})
        if not plugin_texts:
            return {}

        name_to_cn = {}
        ps = PluginService(self.config)
        for plugin in ps.list_all():
            if plugin.description:
                text_key = plugin.description.strip().lower()[:200]
                if text_key in plugin_texts:
                    name_to_cn[plugin.name] = plugin_texts[text_key]
        return name_to_cn

    def save_translation(self, skill_name: str, cn_text: str) -> None:
        """Save a single translation to cache (keyed by description text for dedup)."""
        # Find the skill to get its description for keying
        desc = None
        for s in self.list_all():
            if s.name == skill_name:
                desc = s.display_description
                break
        if not desc:
            return

        cache = self.config.read_json(self.config.translate_cache_path, default={})
        if "skills" not in cache:
            cache["skills"] = {}
        text_key = desc.strip().lower()[:200]
        cache["skills"][text_key] = cn_text
        self.config.write_json(self.config.translate_cache_path, cache, backup=False)

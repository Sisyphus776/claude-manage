"""Plugin service — discovers installed Claude Code plugins."""
import json
import os
from pathlib import Path
from typing import Optional

from models.models import Plugin, PluginSkill
from services.claude_config import ClaudeConfigService


class PluginService:
    """Manages Claude Code plugins."""

    def __init__(self, config: ClaudeConfigService):
        self.config = config

    def list_all(self) -> list[Plugin]:
        """Discover all installed plugins from cache and marketplaces."""
        plugins: dict[str, Plugin] = {}  # keyed by name+marketplace

        # Scan cache directory (installed versions)
        self._scan_dir(self.config.plugins_cache_dir, plugins, is_cache=True)

        # Scan marketplace directory (not yet cached)
        self._scan_dir(self.config.plugins_marketplaces_dir, plugins, is_cache=False)

        # If cache is empty, also try the plugin dirs directly
        if not plugins:
            self._scan_dir(self.config.claude_dir / "plugins", plugins, is_cache=False)

        return sorted(plugins.values(), key=lambda p: p.name)

    def _scan_dir(self, parent: Path, plugins: dict, is_cache: bool):
        """Recursively scan for plugin.json files."""
        if not parent.exists():
            return

        for root, dirs, files in os.walk(str(parent)):
            if "plugin.json" in files:
                plugin_path = Path(root)
                plugin = self._read_plugin(plugin_path, is_cache)
                if plugin:
                    key = f"{plugin.marketplace}:{plugin.name}"
                    if key not in plugins:
                        plugins[key] = plugin
                # Don't go deeper from a plugin root
                dirs.clear()
                continue

            # For cache dirs, only go one level deep after marketplace
            if is_cache and root == str(parent):
                continue

    def _read_plugin(self, plugin_dir: Path, is_cache: bool) -> Optional[Plugin]:
        """Read plugin.json and build a Plugin object."""
        pjson_path = None
        for candidate in [
            plugin_dir / ".claude-plugin" / "plugin.json",
            plugin_dir / ".codex-plugin" / "plugin.json",
            plugin_dir / "plugin.json",
        ]:
            if candidate.exists():
                pjson_path = candidate
                break

        if not pjson_path:
            return None

        try:
            data = json.loads(pjson_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            return None

        name = data.get("name", plugin_dir.name)

        # Determine marketplace
        marketplace = "unknown"
        parts = plugin_dir.parts
        # Pattern: .../cache/<marketplace>/<name>/<version>
        for i, p in enumerate(parts):
            if p in ("cache", "marketplaces") and i + 2 < len(parts):
                marketplace = parts[i + 1]
                break

        # Determine version
        version = data.get("version", "0.0.0")
        if is_cache and len(parts) >= 2:
            maybe_version = parts[-1]
            if all(c.isdigit() or c == '.' for c in maybe_version):
                version = maybe_version

        # Author handling
        author_data = data.get("author", {})
        if isinstance(author_data, dict):
            author = author_data.get("name", "")
            author_email = author_data.get("email", "")
        else:
            author = str(author_data)
            author_email = ""

        # Skills in this plugin
        skills: list[PluginSkill] = []
        skills_dir = plugin_dir / "skills"
        if skills_dir.exists() and skills_dir.is_dir():
            for entry in sorted(os.listdir(str(skills_dir))):
                skill_path = skills_dir / entry
                skill_name = entry
                desc = ""
                # Check for SKILL.md
                skill_md = skill_path / "SKILL.md"
                if skill_md.exists():
                    try:
                        text = skill_md.read_text(encoding='utf-8')
                        if text.startswith('---'):
                            end = text.find('---', 3)
                            if end > 0:
                                import yaml
                                fm = yaml.safe_load(text[3:end])
                                if isinstance(fm, dict):
                                    skill_name = fm.get("name", entry)
                                    desc = fm.get("description", "")
                                    if isinstance(desc, list):
                                        desc = ' '.join(str(d) for d in desc)
                    except (OSError, Exception):
                        pass
                skills.append(PluginSkill(
                    name=skill_name,
                    description=str(desc) if desc else "",
                    path=skill_path,
                ))

        return Plugin(
            name=name,
            version=version,
            description=data.get("description", ""),
            author=author,
            author_email=author_email,
            homepage=data.get("homepage", ""),
            repository=data.get("repository", ""),
            license=data.get("license", ""),
            marketplace=marketplace,
            install_path=plugin_dir,
            skills=skills,
        )

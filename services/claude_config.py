"""Claude config service — reads the .claude directory structure and settings."""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


class ClaudeConfigService:
    """Central service for reading/writing Claude configuration files."""

    def __init__(self, claude_dir: Optional[Path] = None):
        if claude_dir is None:
            claude_dir = Path(os.environ.get(
                "CLAUDE_CONFIG_DIR",
                os.path.expandvars(r"$USERPROFILE\.claude")))
        self.claude_dir = Path(claude_dir)

    # ── Paths ──────────────────────────────────────────────────────────

    @property
    def skills_dir(self) -> Path:
        return self.claude_dir / "skills"

    @property
    def plugins_cache_dir(self) -> Path:
        return self.claude_dir / "plugins" / "cache"

    @property
    def plugins_marketplaces_dir(self) -> Path:
        return self.claude_dir / "plugins" / "marketplaces"

    @property
    def settings_path(self) -> Path:
        return self.claude_dir / "settings.json"

    @property
    def settings_local_path(self) -> Path:
        return self.claude_dir / "settings.local.json"

    @property
    def mcp_config_path(self) -> Path:
        return self.claude_dir / ".mcp.json"

    @property
    def claude_md_path(self) -> Path:
        return self.claude_dir / "CLAUDE.md"

    @property
    def memory_projects_dir(self) -> Path:
        return self.claude_dir / "projects"

    @property
    def translate_cache_path(self) -> Path:
        return self.claude_dir / ".claude-manage-translations.json"

    @property
    def app_settings_path(self) -> Path:
        return self.claude_dir / ".claude-manage-settings.json"

    # ── JSON helpers ───────────────────────────────────────────────────

    def read_json(self, path: Path, default=None) -> dict:
        """Read a JSON file, return default on error."""
        if not path.exists():
            return default if default is not None else {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            # Corrupted file — return default
            return default if default is not None else {}

    def write_json(self, path: Path, data: dict, backup: bool = True) -> bool:
        """Write JSON to file with optional auto-backup."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if backup and path.exists():
                self._make_backup(path)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent='\t', ensure_ascii=False)
                f.write('\n')
            return True
        except OSError:
            return False

    def _make_backup(self, path: Path) -> None:
        """Create a timestamped backup of a file."""
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = path.with_suffix(f"{path.suffix}.bak-{ts}")
        shutil.copy2(str(path), str(backup_path))

    # ── Settings helpers ───────────────────────────────────────────────

    def read_settings(self, masked: bool = False) -> dict:
        """Read settings.json. If masked=True, sensitive values are hidden."""
        data = self.read_json(self.settings_path)
        if masked:
            from services.security import mask_dict
            data = mask_dict(data)
        return data

    def read_settings_local(self) -> dict:
        return self.read_json(self.settings_local_path)

    def write_settings(self, data: dict) -> bool:
        return self.write_json(self.settings_path, data)

    # ── MCP ───────────────────────────────────────────────────────────

    def read_mcp_config(self) -> dict:
        mcp = self.read_json(self.mcp_config_path, default={"mcpServers": {}})
        return mcp

    def write_mcp_config(self, data: dict) -> bool:
        return self.write_json(self.mcp_config_path, data)

    # ── Text file helpers ──────────────────────────────────────────────

    def read_text(self, path: Path) -> str:
        """Read a text file, return empty string on error."""
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding='utf-8')
        except OSError:
            return ""

    def write_text(self, path: Path, content: str, backup: bool = True) -> bool:
        """Write a text file with optional auto-backup."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if backup and path.exists():
                self._make_backup(path)
            path.write_text(content, encoding='utf-8')
            return True
        except OSError:
            return False

    # ── Extra directories for project CLAUDE.md ───────────────────────

    def list_project_dirs(self) -> list[Path]:
        """Scan settings for additionalDirectories + default extra dirs."""
        extra = []
        # Read additional directories from settings.local.json permissions
        local = self.read_settings_local()
        perms = local.get("permissions", {})
        dirs = perms.get("additionalDirectories", [])
        for d in dirs:
            p = Path(d)
            if p.exists():
                extra.append(p)
        return extra

    def find_all_claude_md(self) -> list[Path]:
        """Find all CLAUDE.md files: global + projects."""
        results = []
        if self.claude_md_path.exists():
            results.append(self.claude_md_path)
        # Also check RTK.md as additional config file
        rtk = self.claude_dir / "RTK.md"
        if rtk.exists():
            results.append(rtk)
        # Scan project dirs
        for proj_dir in self.list_project_dirs():
            cm = proj_dir / "CLAUDE.md"
            if cm.exists() and cm != self.claude_md_path:
                results.append(cm)
        return results

    # ── App settings ──────────────────────────────────────────────────

    def read_app_settings(self) -> dict:
        return self.read_json(self.app_settings_path, default={})

    def write_app_settings(self, data: dict) -> bool:
        return self.write_json(self.app_settings_path, data)

    # ── Health check ───────────────────────────────────────────────────

    def exists(self) -> bool:
        return self.claude_dir.exists()

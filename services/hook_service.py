"""Hook service — parses hooks from settings.json."""
import copy
from typing import Optional

from models.models import Hook
from services.claude_config import ClaudeConfigService


class HookService:
    """Manages Claude Code hooks from settings.json."""

    def __init__(self, config: ClaudeConfigService):
        self.config = config

    def list_all(self) -> list[Hook]:
        """Parse settings.json hooks field."""
        settings = self.config.read_settings()
        hooks_data = settings.get("hooks", {})
        hooks: list[Hook] = []

        for event_name, matchers in hooks_data.items():
            if not isinstance(matchers, list):
                continue
            for mi, matcher_group in enumerate(matchers):
                if not isinstance(matcher_group, dict):
                    continue
                matcher_str = matcher_group.get("matcher", "")
                entries = matcher_group.get("hooks", [])
                if not isinstance(entries, list):
                    continue
                for ei, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        continue
                    hook = Hook(
                        event=event_name,
                        matcher=matcher_str if matcher_str else "(default)",
                        type=entry.get("type", "command"),
                        command=entry.get("command", ""),
                        shell=entry.get("shell", ""),
                        timeout=entry.get("timeout", 60),
                        is_async=entry.get("async", False),
                        enabled=True,
                        raw_index=mi * 1000 + ei,
                    )
                    hooks.append(hook)

        return sorted(hooks, key=lambda h: (h.event, h.matcher, h.command))

    def get_raw_hooks(self) -> dict:
        """Return the hooks section of settings.json."""
        settings = self.config.read_settings()
        return settings.get("hooks", {})

    def save_hooks(self, hooks_data: dict) -> bool:
        """Replace the hooks section in settings.json."""
        settings = self.config.read_settings()
        settings["hooks"] = hooks_data
        return self.config.write_settings(settings)

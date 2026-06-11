"""Memory service — reads and manages session memory files."""
import os
import re
from pathlib import Path
from typing import Optional

from models.models import MemoryFile, ClaudeMdFile
from services.claude_config import ClaudeConfigService


class MemoryService:
    """Manages Claude memory files."""

    def __init__(self, config: ClaudeConfigService):
        self.config = config

    def list_all(self) -> list[MemoryFile]:
        """Scan all memory files under projects/<id>/memory/."""
        memories: list[MemoryFile] = []
        projects_dir = self.config.memory_projects_dir

        if not projects_dir.exists():
            return memories

        for project_entry in sorted(os.listdir(str(projects_dir))):
            project_path = projects_dir / project_entry
            if not project_path.is_dir():
                continue
            memory_dir = project_path / "memory"
            if not memory_dir.exists() or not memory_dir.is_dir():
                continue
            for file_entry in sorted(os.listdir(str(memory_dir))):
                if not file_entry.endswith('.md'):
                    continue
                file_path = memory_dir / file_entry
                mem = self._parse_memory_file(file_path)
                if mem:
                    memories.append(mem)

        return sorted(memories, key=lambda m: m.name)

    def _parse_memory_file(self, path: Path) -> Optional[MemoryFile]:
        """Parse a single memory .md file, extracting frontmatter."""
        try:
            content = path.read_text(encoding='utf-8')
        except OSError:
            return None

        name = path.stem  # filename without .md
        description = ""
        mem_type = ""

        # Extract frontmatter
        if content.startswith('---'):
            end = content.find('---', 3)
            if end > 0:
                fm_str = content[3:end].strip()
                body = content[end + 3:].strip()
                for line in fm_str.split('\n'):
                    line = line.strip()
                    if line.startswith('name:'):
                        name = line[5:].strip()
                    elif line.startswith('description:'):
                        description = line[12:].strip()
                    elif line.startswith('type:'):
                        mem_type = line[5:].strip()

        return MemoryFile(
            name=name,
            path=path,
            description=description,
            memory_type=mem_type,
            content=content,
            size=len(content.encode('utf-8')),
        )

    def get_content(self, file_name: str) -> Optional[str]:
        """Get content of a specific memory file by name."""
        for mem in self.list_all():
            if mem.name == file_name or str(mem.path) == file_name:
                return mem.content
        return None

    def delete(self, file_name: str) -> bool:
        """Delete a memory file by name."""
        for mem in self.list_all():
            if mem.name == file_name:
                try:
                    mem.path.unlink()
                    return True
                except OSError:
                    return False
        return False


class ClaudeMdService:
    """Manages CLAUDE.md files."""

    def __init__(self, config: ClaudeConfigService):
        self.config = config

    def list_all(self) -> list[ClaudeMdFile]:
        """Find all CLAUDE.md files."""
        results: list[ClaudeMdFile] = []

        paths = self.config.find_all_claude_md()
        for p in paths:
            content = ""
            size = 0
            try:
                content = p.read_text(encoding='utf-8')
                size = len(content.encode('utf-8'))
            except OSError:
                pass

            is_global = (p == self.config.claude_md_path)
            if p.name == "RTK.md":
                label = "RTK (全局)"
            elif is_global:
                label = "全局 CLAUDE.md"
            else:
                # Project CLAUDE.md
                try:
                    label = str(p.parent.name)
                except Exception:
                    label = str(p.parent)

            results.append(ClaudeMdFile(
                path=p,
                label=label,
                content=content,
                size=size,
                is_global=is_global,
            ))

        return sorted(results, key=lambda c: (not c.is_global, c.label))

    def get_content(self, path: Path) -> str:
        """Read CLAUDE.md content."""
        return self.config.read_text(path)

    def save_content(self, path: Path, content: str) -> bool:
        """Write CLAUDE.md content."""
        return self.config.write_text(path, content)

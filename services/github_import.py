"""GitHub skill import — parses URLs, downloads SKILL.md and companion files."""
import os
import re
import json
import shutil
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

import requests

# GitHub API base (no auth needed for public repos)
GITHUB_API = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"

# Common skill companion file patterns
SKILL_FILES_PATTERNS = [
    "SKILL.md",
    "README.md",
    "LICENSE",
    "*.py", "*.sh", "*.js", "*.ts",
    "requirements.txt", "package.json",
]


def parse_github_url(url: str) -> Optional[dict]:
    """
    Parse a GitHub URL into structured info.
    Returns dict with: owner, repo, ref, path, type
    Types: 'raw_md', 'repo', 'directory', 'release'
    """
    url = url.strip()

    # Raw URL: https://raw.githubusercontent.com/owner/repo/ref/path/to/SKILL.md
    raw_match = re.match(
        r'https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$',
        url
    )
    if raw_match:
        owner, repo, ref, path = raw_match.groups()
        return {
            "owner": owner, "repo": repo, "ref": ref,
            "path": path, "type": "raw_md",
            "display_name": path.split('/')[-2] if '/' in path else repo,
        }

    # Regular GitHub URL: https://github.com/owner/repo
    # Subdirectory: https://github.com/owner/repo/tree/ref/path
    # File: https://github.com/owner/repo/blob/ref/path
    gh_match = re.match(
        r'https?://github\.com/([^/]+)/([^/]+)(?:/(tree|blob)/([^/]+)/(.+))?$',
        url
    )
    if gh_match:
        owner, repo, kind, ref, path = gh_match.groups()
        result = {"owner": owner, "repo": repo, "ref": ref or "main", "path": path or ""}
        if kind == "tree" and path:
            result["type"] = "directory"
        elif kind == "blob" and path and path.endswith(".md"):
            result["type"] = "raw_md"
            # Convert blob URL to raw URL path
            result["raw_path"] = path
        else:
            result["type"] = "repo"
        result["display_name"] = repo
        return result

    # Short form: owner/repo or owner/repo/tree/branch/path
    short_match = re.match(r'^([^/]+)/([^/]+)$', url)
    if short_match:
        owner, repo = short_match.groups()
        return {"owner": owner, "repo": repo, "ref": "main", "path": "",
                "type": "repo", "display_name": repo}

    return None


def list_directory(owner: str, repo: str, path: str = "", ref: str = "main") -> list[dict]:
    """List contents of a GitHub repo directory via API."""
    api_url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    if ref and ref != "main":
        api_url += f"?ref={ref}"

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Claude-Manage/1.0",
    }
    try:
        resp = requests.get(api_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json() if isinstance(resp.json(), list) else [resp.json()]
        elif resp.status_code == 404:
            return []
        elif resp.status_code == 403:
            # Rate limited
            remaining = resp.headers.get("X-RateLimit-Remaining", "0")
            reset_time = resp.headers.get("X-RateLimit-Reset", "?")
            return []
        else:
            return []
    except requests.RequestException:
        return []


def find_skill_dirs(owner: str, repo: str, ref: str = "main") -> list[dict]:
    """
    Find all skill directories in a repo.
    Strategy: look for 'skills/' directory, or any directory containing SKILL.md.
    """
    # First try /skills/ directory
    skills_root = list_directory(owner, repo, "skills", ref)
    results = []
    for item in skills_root:
        if item.get("type") == "dir":
            # Check if this dir has SKILL.md
            sub = list_directory(owner, repo, item["path"], ref)
            has_skill_md = any(
                f.get("name") == "SKILL.md" and f.get("type") == "file"
                for f in sub
            )
            if has_skill_md:
                results.append(item)
    if results:
        return results

    # Try scanning repo root for directories with SKILL.md
    root = list_directory(owner, repo, "", ref)
    for item in root:
        if item.get("type") == "dir":
            sub = list_directory(owner, repo, item["path"], ref)
            if any(f.get("name") == "SKILL.md" for f in sub):
                results.append(item)

    return results


def download_file(download_url: str, dest: Path) -> bool:
    """Download a single file from GitHub raw content."""
    try:
        resp = requests.get(download_url, timeout=30, stream=True)
        if resp.status_code == 200:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        return False
    except requests.RequestException:
        return False


def import_skill_from_url(url: str, skills_dir: Path, progress_callback=None) -> dict:
    """
    Import a skill from a GitHub URL.

    Args:
        url: GitHub URL to import from
        skills_dir: Path to Claude skills directory
        progress_callback: Optional callback(step, message) for progress updates

    Returns:
        dict with keys: success, skill_name, message, files_downloaded
    """
    parsed = parse_github_url(url)
    if not parsed:
        return {"success": False, "message": "Could not parse URL. "
                "Supported formats:\n- https://github.com/owner/repo\n"
                "- https://github.com/owner/repo/tree/branch/skills/my-skill\n"
                "- https://raw.githubusercontent.com/owner/repo/branch/path/SKILL.md\n"
                "- owner/repo"}

    owner = parsed["owner"]
    repo = parsed["repo"]
    ref = parsed["ref"]
    path = parsed["path"]

    def progress(step, msg):
        if progress_callback:
            progress_callback(step, msg)

    # ── Case 1: Raw .md URL ───────────────────────────────────────────
    if parsed["type"] == "raw_md":
        progress("download", f"Downloading SKILL.md...")

        if "raw_path" in parsed:
            # Convert blob path to raw URL
            raw_url = f"{RAW_BASE}/{owner}/{repo}/{ref}/{parsed['raw_path']}"
            # Skill name from parent directory
            path_parts = parsed["raw_path"].split('/')
            skill_name = path_parts[-2] if len(path_parts) > 1 else repo
        else:
            raw_url = url  # Already a raw URL
            path_parts = parsed["path"].split('/')
            skill_name = path_parts[-2] if len(path_parts) > 1 else repo

        dest_dir = skills_dir / skill_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Download the SKILL.md
        ok = download_file(raw_url, dest_dir / "SKILL.md")
        if not ok:
            return {"success": False, "message": "Failed to download SKILL.md"}

        # Try to download companion files from the same directory
        dir_path = '/'.join(path_parts[:-1])  # Remove the filename
        files_downloaded = [os.path.basename(raw_url)]

        if dir_path:
            progress("download", "Downloading companion files...")
            directory = list_directory(owner, repo, dir_path, ref)
            for item in directory:
                if item.get("type") == "file" and item["name"] != os.path.basename(raw_url):
                    if item["name"].endswith(('.md', '.py', '.sh', '.txt', '.json', '.js', '.ts')):
                        if download_file(item["download_url"], dest_dir / item["name"]):
                            files_downloaded.append(item["name"])

        progress("done", f"Imported: {skill_name}")
        return {
            "success": True,
            "skill_name": skill_name,
            "message": f"Imported '{skill_name}' ({len(files_downloaded)} files)",
            "files_downloaded": files_downloaded,
        }

    # ── Case 2: Repo root (search for skills) ─────────────────────────
    if parsed["type"] == "repo":
        progress("search", f"Searching for skills in {owner}/{repo}...")
        skill_dirs = find_skill_dirs(owner, repo, ref)

        if not skill_dirs:
            return {"success": False,
                    "message": f"No skills found in {owner}/{repo}.\n"
                    "Expected: a 'skills/' directory with subdirectories containing SKILL.md, "
                    "or root-level directories with SKILL.md."}

        # If multiple, return all names for user to choose
        if len(skill_dirs) > 1:
            names = [d["name"] for d in skill_dirs]
            return {
                "success": False,
                "needs_selection": True,
                "skill_names": names,
                "skill_dirs": [(d["name"], d["path"]) for d in skill_dirs],
                "owner": owner, "repo": repo, "ref": ref,
                "message": f"Found {len(skill_dirs)} skills. Select which to import.",
            }

        # Single skill dir — import it
        target_dir = skill_dirs[0]
        return _import_skill_dir(
            owner, repo, ref, target_dir["path"],
            target_dir["name"], skills_dir, progress
        )

    # ── Case 3: Specific directory ────────────────────────────────────
    if parsed["type"] == "directory":
        skill_name = path.rstrip('/').split('/')[-1]
        progress("download", f"Downloading {skill_name}...")
        return _import_skill_dir(
            owner, repo, ref, path, skill_name, skills_dir, progress
        )

    return {"success": False, "message": "Unsupported URL type"}


def _import_skill_dir(owner: str, repo: str, ref: str,
                      dir_path: str, skill_name: str,
                      skills_dir: Path, progress) -> dict:
    """Download all files from a skill directory."""
    files_in_dir = list_directory(owner, repo, dir_path, ref)

    if not files_in_dir:
        return {"success": False, "message": f"Directory is empty or not accessible"}

    dest_dir = skills_dir / skill_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    files_downloaded = []
    for item in files_in_dir:
        if item.get("type") != "file":
            continue
        fname = item["name"]
        progress("download", f"Downloading: {fname}")
        if download_file(item["download_url"], dest_dir / fname):
            files_downloaded.append(fname)

    # Also download subdirectories (scripts/, references/, etc.)
    for item in files_in_dir:
        if item.get("type") == "dir":
            sub_path = item["path"]
            sub_name = item["name"]
            sub_files = list_directory(owner, repo, sub_path, ref)
            sub_dest = dest_dir / sub_name
            for sf in sub_files:
                if sf.get("type") == "file":
                    sf_name = sf["name"]
                    progress("download", f"Downloading: {sub_name}/{sf_name}")
                    if download_file(sf["download_url"], sub_dest / sf_name):
                        files_downloaded.append(f"{sub_name}/{sf_name}")

    progress("done", f"Imported {skill_name}")
    return {
        "success": True,
        "skill_name": skill_name,
        "message": f"Imported '{skill_name}' ({len(files_downloaded)} files)",
        "files_downloaded": files_downloaded,
    }

"""Baidu Translate API integration with local caching."""
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Optional

import requests

BAIDU_API_URL = "https://fanyi-api.baidu.com/api/trans/vip/translate"


class TranslateService:
    """Baidu Translate API wrapper with JSON file cache."""

    def __init__(self, app_id: str, secret_key: str, cache_path: Path):
        self.app_id = app_id
        self.secret_key = secret_key
        self.cache_path = cache_path
        self._cache = {}
        self._load_cache()

    # ── Cache ─────────────────────────────────────────────────────────

    def _load_cache(self):
        if self.cache_path.exists():
            try:
                data = json.loads(self.cache_path.read_text(encoding='utf-8'))
                self._cache = data
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _save_cache(self):
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent='\t'),
                encoding='utf-8'
            )
        except OSError:
            pass

    def _cached(self, text: str) -> Optional[str]:
        """Check if a translation exists in cache."""
        text_key = text.strip().lower()[:200]  # Use first 200 chars as key
        # Check all domains
        for domain in self._cache:
            domain_cache = self._cache[domain]
            if isinstance(domain_cache, dict) and text_key in domain_cache:
                return domain_cache[text_key]
        return None

    def _set_cached(self, domain: str, text: str, result: str):
        """Store translation in cache."""
        if domain not in self._cache:
            self._cache[domain] = {}
        text_key = text.strip().lower()[:200]
        self._cache[domain][text_key] = result

    # ── Translation ───────────────────────────────────────────────────

    def translate(self, text: str, source: str = "en", target: str = "zh") -> Optional[str]:
        """Translate a single text string. Returns None on failure."""
        if not text or not text.strip():
            return ""

        # Check cache first
        cached = self._cached(text)
        if cached is not None:
            return cached

        # Truncate — Baidu free tier has character limits
        text_to_send = text[:1500] if len(text) > 1500 else text

        # Build request
        salt = str(random.randint(32768, 65536))
        sign_str = self.app_id + text_to_send + salt + self.secret_key
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

        params = {
            "q": text_to_send,
            "from": source,
            "to": target,
            "appid": self.app_id,
            "salt": salt,
            "sign": sign,
        }

        try:
            resp = requests.get(BAIDU_API_URL, params=params, timeout=10)
            # CRITICAL: Baidu API response is UTF-8 but may not declare charset.
            # requests auto-detection can pick the wrong encoding (ISO-8859-1),
            # causing Chinese characters to be garbled.
            resp.encoding = 'utf-8'
            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError):
            return None

        if "trans_result" in data:
            result = data["trans_result"][0]["dst"]
            return result

        # API error — log the error code if present
        if "error_code" in data:
            import sys
            print(f"[translate] Baidu API error: {data.get('error_code')} - {data.get('error_msg', '')}", file=sys.stderr, flush=True)

        return None

    def translate_skill_descriptions(self, skills: list, progress_callback=None) -> dict[str, str]:
        """
        Translate descriptions for multiple skills.
        Returns {skill_name: cn_description}.
        """
        results = {}
        total = sum(1 for s in skills if s.display_description and s.display_description.strip())
        done = 0

        for skill in skills:
            if not skill.display_description or not skill.display_description.strip():
                continue

            # Check cache
            name = skill.name
            text = skill.display_description
            cached = self._cached(text)
            if cached:
                results[name] = cached
                # Save cache entry
                self._set_cached("skills", text, cached)
                self._save_cache()
                done += 1
                if progress_callback:
                    progress_callback(done, total, name, "cached")
                continue

            # Translate
            cn = self.translate(text)
            if cn:
                results[name] = cn
                self._set_cached("skills", text, cn)
                self._save_cache()

            done += 1
            if progress_callback:
                progress_callback(done, total, name, "translated" if cn else "failed")

            # Avoid rate limiting
            if cn:
                time.sleep(0.2)

        return results

    def translate_plugin_descriptions(self, plugins: list, progress_callback=None):
        """Translate plugin descriptions."""
        results = {}
        total = len(plugins)
        done = 0

        for plugin in plugins:
            if not plugin.description or not plugin.description.strip():
                done += 1
                continue

            # Check cache first
            cached = self._cached(plugin.description)
            if cached:
                results[plugin.name] = cached
                self._set_cached("plugins", plugin.description, cached)
                self._save_cache()
                done += 1
                if progress_callback:
                    progress_callback(done, total, plugin.name, "cached")
                continue

            cn = self.translate(plugin.description)
            if cn:
                results[plugin.name] = cn
                self._set_cached("plugins", plugin.description, cn)
                self._save_cache()

            done += 1
            if progress_callback:
                progress_callback(done, total, plugin.name, "translated" if cn else "failed")

            if cn:
                time.sleep(0.2)

        return results

    def get_cache_stats(self) -> dict:
        """Return cache statistics."""
        stats = {"domains": {}, "total_entries": 0}
        for domain, entries in self._cache.items():
            if isinstance(entries, dict):
                count = len(entries)
                stats["domains"][domain] = count
                stats["total_entries"] += count
        return stats

    def clear_cache(self):
        """Clear all cached translations."""
        self._cache = {}
        if self.cache_path.exists():
            try:
                self.cache_path.unlink()
            except OSError:
                pass

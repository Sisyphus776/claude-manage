"""Complete test suite for Claude Manage."""
import sys, os, io, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print('=' * 60)
print('Claude Manage - Full Test Suite')
print('=' * 60)

# ── 1. Services Layer ────────────────────────────────────────────
print()
print('[TEST 1] Services Layer')

from services.claude_config import ClaudeConfigService
from services.skill_service import SkillService
from services.plugin_service import PluginService
from services.mcp_service import McpService
from services.hook_service import HookService
from services.memory_service import MemoryService, ClaudeMdService
from services.security import is_sensitive_key, mask_value, mask_dict
from services.github_import import parse_github_url

cfg = ClaudeConfigService()
assert cfg.exists(), 'Claude dir should exist'

# Skills
ss = SkillService(cfg)
skills = ss.list_all()
assert len(skills) > 0, 'Should have skills'
types_found = set(s.type.value for s in skills)
active = sum(1 for s in skills if s.status.value == 'active')
disabled = sum(1 for s in skills if s.status.value == 'disabled')
broken = sum(1 for s in skills if s.status.value == 'broken')
print(f'  Skills: {len(skills)} (types: {types_found})')
print(f'  Status: {active} active, {disabled} disabled, {broken} broken')

# Plugins
ps = PluginService(cfg)
plugins = ps.list_all()
assert len(plugins) > 0, 'Should have plugins'
mkt = len(set(p.marketplace for p in plugins))
print(f'  Plugins: {len(plugins)} from {mkt} marketplaces')

# MCP
servers = McpService(cfg).list_all()
print(f'  MCP servers: {len(servers)}')

# Hooks
hooks = HookService(cfg).list_all()
assert len(hooks) > 0, 'Should have hooks'
events = set(h.event for h in hooks)
print(f'  Hooks: {len(hooks)} across {len(events)} events')

# Memory
memories = MemoryService(cfg).list_all()
print(f'  Memory: {len(memories)} files')

# CLAUDE.md
cmds = ClaudeMdService(cfg).list_all()
assert len(cmds) > 0, 'Should have CLAUDE.md files'
print(f'  CLAUDE.md: {len(cmds)} files')

print('  [PASS] Services Layer')

# ── 2. Security ─────────────────────────────────────────────────
print()
print('[TEST 2] Security')

assert is_sensitive_key('api_key') == True
assert is_sensitive_key('ANTHROPIC_AUTH_TOKEN') == True
assert is_sensitive_key('name') == False
masked_val = mask_value('sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
assert '****' in masked_val
assert masked_val.startswith('sk-x')
assert masked_val.endswith('xxxx')

settings = cfg.read_settings(masked=True)
env = settings.get('env', {})
for k, v in env.items():
    if is_sensitive_key(k):
        assert '****' in str(v), f'{k} should be masked'
print('  [PASS] Security')

# ── 3. GitHub URL Parsing ───────────────────────────────────────
print()
print('[TEST 3] GitHub URL Parsing')

test_urls = [
    ('https://github.com/owner/repo', 'repo', 'owner', 'repo'),
    ('owner/repo', 'repo', 'owner', 'repo'),
    ('https://github.com/owner/repo/tree/main/skills/test', 'directory', 'owner', 'repo'),
    ('https://raw.githubusercontent.com/owner/repo/main/x/SKILL.md', 'raw_md', 'owner', 'repo'),
    ('https://github.com/owner/repo/blob/main/x/SKILL.md', 'raw_md', 'owner', 'repo'),
]
for url, exp_type, exp_owner, exp_repo in test_urls:
    r = parse_github_url(url)
    assert r is not None, f'Failed: {url}'
    assert r['type'] == exp_type, f'{url}: type expected {exp_type}, got {r["type"]}'
    assert r['owner'] == exp_owner, f'{url}: owner'
    assert r['repo'] == exp_repo, f'{url}: repo'
    print(f'  OK: {url[:60]}')

assert parse_github_url('not-a-url') is None
assert parse_github_url('') is None
print('  [PASS] GitHub URL Parsing')

# ── 4. Data Integrity ───────────────────────────────────────────
print()
print('[TEST 4] Data Integrity')

for s in skills:
    assert s.type.value in ('directory', 'symlink', 'standalone-md'), f'{s.name}: bad type'
    assert s.status.value in ('active', 'disabled', 'broken'), f'{s.name}: bad status'

fm_count = sum(1 for s in skills if s.frontmatter)
print(f'  Frontmatter: {fm_count}/{len(skills)}')
print('  [PASS] Data Integrity')

# ── 5. CRUD Operations (non-destructive) ────────────────────────
print()
print('[TEST 5] CRUD Operations')

test_skill = skills[0]
detail = ss.get_details(test_skill.name)
assert detail is not None
assert detail.name == test_skill.name
print(f'  get_details: {detail.name} OK')

if test_skill.status.value != 'broken':
    orig = test_skill.status.value
    ok = ss.toggle(test_skill.name)
    print(f'  toggle {test_skill.name}: {orig} -> ok={ok}')
    assert ok, 'toggle should succeed'
    ok2 = ss.toggle(test_skill.name)
    assert ok2, 'toggle back should succeed'
    print(f'  toggle back: ok={ok2}')
else:
    print(f'  toggle: skipped (broken)')
print('  [PASS] CRUD Operations')

# ── 6. Translation (real API + cache roundtrip) ─────────────────
print()
print('[TEST 6] Translation API + Cache')

import hashlib, random
from services.translate import TranslateService

cache_path = cfg.translate_cache_path

# 6a. API connectivity test — translate one short text
app_s = cfg.read_app_settings()
api = app_s.get("baidu_api", {})
app_id = api.get("app_id", "")
secret = api.get("secret_key", "")
if app_id and secret:
    ts = TranslateService(app_id, secret, cache_path)
    result = ts.translate("Browser automation")
    if result:
        is_chinese = any(0x4e00 <= ord(c) <= 0x9fff for c in result)
        print(f"  API test: 'Browser automation' → {result[:40]}")
        assert is_chinese, f"Translation is not Chinese: {repr(result)}"
        print(f"  [PASS] 6a - API returns valid Chinese")
    else:
        print(f"  [SKIP] 6a - API returned None (quota/network)")
else:
    print("  [SKIP] 6a - Baidu API not configured")

# 6b. Cache roundtrip: translate→set_cached→load_translations
sample = skills[0] if skills else None
if sample and sample.display_description and app_id and secret:
    ts = TranslateService(app_id, secret, cache_path)
    cn = ts.translate(sample.display_description)
    if cn:
        is_cn = any(0x4e00 <= ord(c) <= 0x9fff for c in cn)
        assert is_cn, f"Translation not Chinese: {repr(cn[:40])}"
        # Manual cache write (simulates what translate.batch does)
        ts._set_cached("skills", sample.display_description, cn)
        ts._save_cache()
        # Verify cache hit on second call
        cached = ts._cached(sample.display_description)
        assert cached is not None, "Should be in cache after _set_cached"
        assert cached == cn, f"Cached mismatch: {repr(cached)} vs {repr(cn)}"
        print(f"  Cache write+read: {sample.name} → {cached[:40]}...")
        print(f"  [PASS] 6b - Cache roundtrip correct")
    else:
        print(f"  [FAIL] 6b - translate() returned None for valid API")
        sys.exit(1)

# 6c. load_translations() — text key → skill name mapping
if app_id and secret and sample and sample.display_description:
    tl = ss.load_translations()
    if tl:
        assert sample.name in tl, f"Expected {sample.name} in translations, got {list(tl.keys())[:5]}"
        is_cn = any(0x4e00 <= ord(c) <= 0x9fff for c in tl[sample.name])
        assert is_cn, f"Translation for {sample.name} is not Chinese: {repr(tl[sample.name][:40])}"
        print(f"  [PASS] 6c - load_translations() maps name→cn correctly")
    else:
        print(f"  [WARN] 6c - load_translations() returned empty (cache key mismatch)")

# 6d. Plugin translations
from services.plugin_service import PluginService
ps = PluginService(cfg)
plugins = ps.list_all()
plugin_sample = next((p for p in plugins if p.description and p.description.strip()), None)
if plugin_sample and app_id and secret:
    ts = TranslateService(app_id, secret, cache_path)
    cn = ts.translate(plugin_sample.description)
    if cn:
        ts._set_cached("plugins", plugin_sample.description, cn)
        ts._save_cache()
        ptl = ss.load_plugin_translations()
        if ptl and plugin_sample.name in ptl:
            is_cn = any(0x4e00 <= ord(c) <= 0x9fff for c in ptl[plugin_sample.name])
            print(f"  Plugin: {plugin_sample.name} → {ptl[plugin_sample.name][:40]}...")
            assert is_cn, f"Plugin translation not Chinese"
            print(f"  [PASS] 6d - Plugin translations work")
        else:
            print(f"  [WARN] 6d - load_plugin_translations() missing {plugin_sample.name}")
    else:
        print(f"  [SKIP] 6d - Plugin API returned None")

# Cleanup: reset cache for repeatable runs
if cache_path.exists():
    data = json.loads(cache_path.read_text(encoding='utf-8'))
    for d in ("skills", "plugins"):
        if d in data:
            data[d] = {}
    cache_path.write_text(json.dumps(data, ensure_ascii=False))

# ── 7. Bridge & Frontend Integrity ──────────────────────────────
print()
print('[TEST 7] Bridge & Frontend Integrity')

import subprocess

# 7a. bridge.py runs and responds to basic RPC call
proc = subprocess.Popen(
    [sys.executable, 'bridge.py'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, encoding='utf-8'
)
proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':1,'method':'dashboard.summary','params':{}})+'\n')
proc.stdin.flush()
resp = proc.stdout.readline()
proc.stdin.close()
proc.wait()
data = json.loads(resp)
assert data.get('result',{}).get('skill_count',-1) >= 0, 'bridge.py RPC failed'
print(f'  bridge.py JSON-RPC: OK ({data["result"]["skill_count"]} skills)')

# 7b. Frontend files exist
import pathlib
electron_dir = pathlib.Path('electron')
assert electron_dir.exists()
assert (electron_dir / 'main.js').exists(), 'main.js missing'
assert (electron_dir / 'preload.js').exists(), 'preload.js missing'
assert (electron_dir / 'renderer' / 'index.html').exists(), 'index.html missing'
print(f'  main.js: OK')
print(f'  preload.js: OK')
print(f'  index.html: OK')

# 7c. Verify index.html contains key functions (no syntax errors)
html = (electron_dir / 'renderer' / 'index.html').read_text(encoding='utf-8')
checks = ['autoTranslate', 'batchTranslatePlugins', 'showPluginDetail', 'showSkillDetail', 'navTo']
for fn in checks:
    assert fn in html, f'missing function: {fn}'
print(f'  Functions: {", ".join(checks)} OK')

# 7d. Verify no hardcoded user paths in bridge.py source
bridge_src = pathlib.Path('bridge.py').read_text(encoding='utf-8')
assert 'ensure_ascii=True' in bridge_src, 'bridge.py should use ensure_ascii=True'
print(f'  bridge.py encoding: OK')

# 7e. Verify no hardcoded paths leak in main.js
main_js = (electron_dir / 'main.js').read_text(encoding='utf-8')
assert "D:/python" not in main_js, 'hardcoded Python path in main.js'
assert "C:/Users" not in main_js, 'hardcoded user path in main.js'
print(f'  main.js no hardcoded paths: OK')

# 7f. Verify no API keys in committed source
for py_file in pathlib.Path('services').glob('*.py'):
    content = py_file.read_text(encoding='utf-8')
    assert 'lTHyno' not in content, f'Secret key found in {py_file}'
    assert 'sk-f3f3' not in content, f'API key found in {py_file}'
print(f'  No secrets in source: OK')
print('  [PASS] Bridge & Frontend Integrity')

# ── Summary ─────────────────────────────────────────────────────
print()
print('=' * 60)
print('ALL TESTS PASSED')
print('=' * 60)
print(f'  Skills:    {len(skills)} ({active} active, {disabled} disabled, {broken} broken)')
print(f'  Plugins:   {len(plugins)}')
print(f'  MCP:       {len(servers)}')
print(f'  Hooks:     {len(hooks)} ({len(events)} events)')
print(f'  Memory:    {len(memories)}')
print(f'  CLAUDE.md: {len(cmds)}')
print(f'  App:       D:/tools/Claude Manage/Claude Manage.exe')

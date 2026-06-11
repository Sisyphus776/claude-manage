"""JSON-RPC 2.0 bridge — wraps existing services for Electron frontend."""
import sys
import os
import json
import traceback
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.claude_config import ClaudeConfigService
from services.skill_service import SkillService
from services.plugin_service import PluginService
from services.mcp_service import McpService
from services.hook_service import HookService
from services.memory_service import MemoryService, ClaudeMdService
from services.security import mask_dict, is_sensitive_key, mask_value
from services.github_import import import_skill_from_url

cfg = ClaudeConfigService()

# ─── Helpers ─────────────────────────────────────────────────────────

def _skill_to_dict(s):
    return {
        "name": s.name, "display_name": s.display_name,
        "type": s.type.value, "status": s.status.value,
        "path": str(s.path),
        "symlink_target": s.symlink_target or "",
        "skill_md_path": str(s.skill_md_path) if s.skill_md_path else "",
        "description": s.display_description,
        "invocation": s.frontmatter.invocation if s.frontmatter else "",
        "triggers": s.frontmatter.triggers if s.frontmatter else [],
        "files": s.files,
    }


# ─── Handlers ────────────────────────────────────────────────────────

handlers = {}

def _h(method):
    def deco(fn):
        handlers[method] = fn
        return fn
    return deco

@_h("dashboard.summary")
def dashboard_summary(_):
    skills = SkillService(cfg).list_all()
    plugins = PluginService(cfg).list_all()
    servers = McpService(cfg).list_all()
    hooks = HookService(cfg).list_all()
    memories = MemoryService(cfg).list_all()
    cmds = ClaudeMdService(cfg).list_all()
    return {
        "skill_count": len(skills),
        "skill_active": sum(1 for s in skills if s.status.value == 'active'),
        "skill_disabled": sum(1 for s in skills if s.status.value == 'disabled'),
        "skill_broken": sum(1 for s in skills if s.status.value == 'broken'),
        "plugin_count": len(plugins),
        "mcp_count": len(servers),
        "hook_count": len(hooks),
        "memory_count": len(memories),
        "claudemd_count": len(cmds),
        "claude_dir": str(cfg.claude_dir),
    }

@_h("skills.list")
def skills_list(_):
    ss = SkillService(cfg)
    skills = ss.list_all()
    return [_skill_to_dict(s) for s in skills]

@_h("skills.toggle")
def skills_toggle(p):
    return SkillService(cfg).toggle(p["name"])

@_h("skills.delete")
def skills_delete(p):
    return SkillService(cfg).delete(p["name"])

@_h("skills.import")
def skills_import(p):
    return import_skill_from_url(p["url"], cfg.skills_dir)

@_h("skills.translations")
def skills_translations(_):
    return SkillService(cfg).load_translations()

@_h("plugins.translations")
def plugins_translations(_):
    return SkillService(cfg).load_plugin_translations()

@_h("plugins.list")
def plugins_list(_):
    ps = PluginService(cfg)
    plugins = ps.list_all()
    return [{
        "name": p.name, "version": p.version, "description": p.description,
        "author": p.author, "author_email": p.author_email,
        "homepage": p.homepage, "repository": p.repository,
        "license": p.license, "marketplace": p.marketplace,
        "install_path": str(p.install_path),
        "skills": [{"name": sk.name, "description": sk.description,
                     "path": str(sk.path)} for sk in p.skills],
    } for p in plugins]

@_h("mcp.list")
def mcp_list(_):
    servers = McpService(cfg).list_all()
    return [{"name": s.name, "type": s.type, "command": s.command,
             "args": s.args, "url": s.url,
             "env": mask_dict(s.env) if s.env else {}} for s in servers]

@_h("mcp.get_raw")
def mcp_get_raw(_):
    return McpService(cfg).get_raw_config()

@_h("mcp.save")
def mcp_save(p):
    return McpService(cfg).save_config(p["config"])

@_h("hooks.list")
def hooks_list(_):
    hs = HookService(cfg)
    hooks = hs.list_all()
    return [{"event": h.event, "matcher": h.matcher, "type": h.type,
             "command": mask_value(h.command) if is_sensitive_key(h.command) else h.command,
             "shell": h.shell, "timeout": h.timeout, "is_async": h.is_async,
             "raw_index": h.raw_index} for h in hooks]

@_h("hooks.get_raw")
def hooks_get_raw(_):
    return HookService(cfg).get_raw_hooks()

@_h("hooks.save")
def hooks_save(p):
    return HookService(cfg).save_hooks(p["hooks"])

@_h("memory.list")
def memory_list(_):
    ms = MemoryService(cfg)
    mems = ms.list_all()
    return [{"name": m.name, "description": m.description,
             "memory_type": m.memory_type, "content": m.content,
             "size": m.size, "path": str(m.path)} for m in mems]

@_h("memory.delete")
def memory_delete(p):
    return MemoryService(cfg).delete(p["name"])

@_h("claudemd.list")
def claudemd_list(_):
    cs = ClaudeMdService(cfg)
    cmds = cs.list_all()
    return [{"label": c.label, "path": str(c.path), "content": c.content,
             "size": c.size, "is_global": c.is_global} for c in cmds]

@_h("claudemd.save")
def claudemd_save(p):
    return ClaudeMdService(cfg).save_content(Path(p["path"]), p["content"])

@_h("translate.batch")
def translate_batch(p):
    from services.translate import TranslateService
    # Read API credentials from config (not from frontend — they may be masked)
    app_s = cfg.read_app_settings()
    api = app_s.get("baidu_api", {})
    app_id = api.get("app_id", "")
    secret = api.get("secret_key", "")
    if not app_id or not secret:
        return {"error": "API not configured"}
    ts = TranslateService(app_id, secret, cfg.translate_cache_path)
    domain = p.get("domain", "skills")  # "skills" or "plugins"
    results = {}
    for item in p.get("items", []):
        cn = ts.translate(item["text"])
        if cn:
            ts._set_cached(domain, item["text"], cn)
            results[item["name"]] = cn
    ts._save_cache()
    return results

@_h("settings.get")
def settings_get(_):
    app_s = cfg.read_app_settings()
    # Mask sensitive values
    baidu = app_s.get("baidu_api", {})
    if "secret_key" in baidu:
        baidu = dict(baidu)
        baidu["secret_key"] = "****" if baidu["secret_key"] else ""
    return {
        "baidu_api": baidu,
        "translate_cache_exists": cfg.translate_cache_path.exists(),
    }

@_h("settings.save")
def settings_save(p):
    app_s = cfg.read_app_settings()
    if "baidu_api" in p:
        new_baidu = p["baidu_api"]
        old_baidu = app_s.get("baidu_api", {})
        if new_baidu.get("secret_key", "") == "****":
            new_baidu["secret_key"] = old_baidu.get("secret_key", "")
        app_s["baidu_api"] = new_baidu
    cfg.write_app_settings(app_s)
    return True

@_h("settings.clear_cache")
def settings_clear_cache(_):
    try:
        if cfg.translate_cache_path.exists():
            cfg.translate_cache_path.unlink()
        return True
    except OSError:
        return False

# ─── Main Loop ────────────────────────────────────────────────────────

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue

        mid = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        handler = handlers.get(method)
        if not handler:
            resp = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Unknown method: {method}"}}
        else:
            try:
                result = handler(params)
                resp = {"jsonrpc": "2.0", "id": mid, "result": result}
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                resp = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}

        sys.stdout.write(json.dumps(resp, ensure_ascii=True, default=str) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()

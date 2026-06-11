# PyInstaller spec for bridge.exe
a = Analysis(
    ['../bridge.py'],
    pathex=['D:/claude-manage'],
    binaries=[],
    datas=[],
    hiddenimports=['json','pathlib','os','sys','traceback','yaml','requests',
        'services','services.claude_config','services.skill_service',
        'services.plugin_service','services.mcp_service','services.hook_service',
        'services.memory_service','services.github_import','services.translate',
        'services.security','models','models.models'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
    name='bridge', debug=False, strip=False, upx=True, console=False, runtime_tmpdir=None,
)

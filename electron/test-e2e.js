/**
 * End-to-end product test: simulates every user action through
 * the real bridge.exe JSON-RPC pipeline.
 *
 * Usage: node test-e2e.js
 * Requires: bridge.exe built and deployed
 */
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const BRIDGE = 'D:/tools/Claude Manage/resources/bridge.exe';
let passed = 0, failed = 0;
const failures = [];

function assert(cond, msg) {
  if (cond) { passed++; }
  else { failed++; failures.push(msg); console.error(`  FAIL: ${msg}`); }
}

// Global RPC state
let rpcId = 0;
let rpcBuffer = '';
const pending = new Map();

function startBridge() {
  const proc = spawn(BRIDGE, [], { stdio: ['pipe', 'pipe', 'pipe'] });
  proc.stderr.on('data', (d) => console.error('STDERR:', d.toString().trim()));

  // Centralized response handler with proper line buffering
  proc.stdout.on('data', (d) => {
    rpcBuffer += d.toString();
    const lines = rpcBuffer.split('\n');
    rpcBuffer = lines.pop() || '';
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const resp = JSON.parse(line);
        if (resp.id !== undefined && pending.has(resp.id)) {
          const { resolve } = pending.get(resp.id);
          pending.delete(resp.id);
          resolve(resp);
        }
      } catch(e) { /* skip non-JSON */ }
    }
  });

  proc.on('exit', (code) => {
    if (code !== 0 && code !== null) console.log('Bridge exited unexpectedly:', code);
  });

  return proc;
}

function rpc(bridge, method, params = {}) {
  return new Promise((resolve) => {
    const id = ++rpcId;
    pending.set(id, { resolve });
    const req = JSON.stringify({ jsonrpc: '2.0', id, method, params });
    bridge.stdin.write(req + '\n');
  });
}

async function main() {
  console.log('='.repeat(60));
  console.log('Claude Manage — Product E2E Test Suite');
  console.log('='.repeat(60));

  const bridge = startBridge();

  // Give it a moment to start
  await new Promise(r => setTimeout(r, 500));

  // ─── 1. Dashboard ─────────────────────────────────────────
  console.log('\n[1] Dashboard');
  let r = await rpc(bridge, 'dashboard.summary');
  const dash = r.result;
  assert(dash.skill_count > 0, `Dashboard: skill_count=${dash.skill_count} should be > 0`);
  assert(dash.plugin_count > 0, `Dashboard: plugin_count=${dash.plugin_count} should be > 0`);
  assert(dash.mcp_count >= 0, `Dashboard: mcp_count=${dash.mcp_count} should be >= 0`);
  assert(dash.hook_count >= 0, `Dashboard: hook_count=${dash.hook_count} should be >= 0`);
  assert(dash.memory_count >= 0, `Dashboard: memory_count=${dash.memory_count} should be >= 0`);
  assert(dash.claudemd_count >= 0, `Dashboard: claudemd_count=${dash.claudemd_count} should be >= 0`);
  console.log(`  skills=${dash.skill_count} plugins=${dash.plugin_count} mcp=${dash.mcp_count} hooks=${dash.hook_count} memory=${dash.memory_count} claudemd=${dash.claudemd_count}`);

  // ─── 2. Skills: list, detail, translations ────────────────
  console.log('\n[2] Skills');
  r = await rpc(bridge, 'skills.list');
  const skills = r.result;
  assert(Array.isArray(skills), 'Skills.list should return array');
  assert(skills.length > 0, 'Skills.list should have at least 1 skill');

  const firstSkill = skills[0];
  assert(firstSkill.name, 'Skill should have name');
  assert(['active','disabled','broken'].includes(firstSkill.status), `Skill status should be valid: ${firstSkill.status}`);
  console.log(`  ${skills.length} skills, first: "${firstSkill.name}" (${firstSkill.status})`);

  // Translations
  r = await rpc(bridge, 'skills.translations');
  assert(typeof r.result === 'object', 'skills.translations should return object');
  console.log(`  translations: ${Object.keys(r.result||{}).length} cached`);

  // ─── 3. Skills CRUD (non-destructive) ─────────────────────
  console.log('\n[3] Skills CRUD');

  // Find a skill we can toggle
  const toggleTarget = skills.find(s => s.status === 'active');
  if (toggleTarget) {
    r = await rpc(bridge, 'skills.toggle', { name: toggleTarget.name });
    assert(r.result === true, `Toggle ${toggleTarget.name} should return true`);
    console.log(`  toggle ${toggleTarget.name}: OK`);

    // Toggle back
    r = await rpc(bridge, 'skills.toggle', { name: toggleTarget.name });
    assert(r.result === true, `Toggle back should return true`);
    console.log(`  toggle back: OK`);
  } else {
    console.log(`  toggle: SKIP (no active skill)`);
  }

  // ─── 4. Plugins ───────────────────────────────────────────
  console.log('\n[4] Plugins');
  r = await rpc(bridge, 'plugins.list');
  const plugins = r.result;
  assert(Array.isArray(plugins), 'Plugins.list should return array');
  assert(plugins.length > 0, 'Plugins.list should have at least 1 plugin');
  assert(plugins[0].name, 'Plugin should have name');
  assert(plugins[0].marketplace, 'Plugin should have marketplace');
  console.log(`  ${plugins.length} plugins from ${new Set(plugins.map(p=>p.marketplace)).size} marketplaces`);

  // Plugin translations
  r = await rpc(bridge, 'plugins.translations');
  assert(typeof r.result === 'object', 'plugins.translations should return object');
  console.log(`  translations: ${Object.keys(r.result||{}).length} cached`);

  // ─── 5. MCP ───────────────────────────────────────────────
  console.log('\n[5] MCP');
  r = await rpc(bridge, 'mcp.list');
  const mcps = r.result;
  assert(Array.isArray(mcps), 'MCP.list should return array');
  assert(mcps.length >= 0, `MCP.list count=${mcps.length}`);

  // Get raw config
  r = await rpc(bridge, 'mcp.get_raw');
  const rawMcp = r.result;
  assert(rawMcp && typeof rawMcp === 'object', 'mcp.get_raw should return object');
  const hasMcpServers = rawMcp.mcpServers || (typeof rawMcp === 'object');
  assert(hasMcpServers, 'Raw MCP config should be readable');
  console.log(`  ${mcps.length} servers, raw config OK`);

  // Save config (non-destructive: save the same config back)
  r = await rpc(bridge, 'mcp.save', { config: rawMcp });
  assert(r.result === true, 'mcp.save should return true');
  console.log(`  save config: OK`);

  // ─── 6. Hooks ─────────────────────────────────────────────
  console.log('\n[6] Hooks');
  r = await rpc(bridge, 'hooks.list');
  const hooks = r.result;
  assert(Array.isArray(hooks), 'Hooks.list should return array');
  assert(hooks.length >= 0, `Hooks.list count=${hooks.length}`);
  if (hooks.length > 0) {
    assert(hooks[0].event, 'Hook should have event field');
    const events = new Set(hooks.map(h => h.event));
    console.log(`  ${hooks.length} hooks across ${events.size} events`);
  }

  // ─── 7. CLAUDE.md ────────────────────────────────────────
  console.log('\n[7] CLAUDE.md');
  r = await rpc(bridge, 'claudemd.list');
  const cmds = r.result;
  assert(Array.isArray(cmds), 'claudemd.list should return array');
  assert(cmds.length >= 0, `claudemd.list count=${cmds.length}`);

  if (cmds.length > 0) {
    assert(cmds[0].label, 'CLAUDE.md entry should have label');
    assert(cmds[0].path, 'CLAUDE.md entry should have path');
    assert(cmds[0].content !== undefined, 'CLAUDE.md entry should have content');
    console.log(`  ${cmds.length} files: ${cmds.map(c=>c.label).join(', ')}`);

    // Save to a temp file (DON'T touch real files)
    const testPath = 'D:/tools/test-claudemd-e2e.md';
    const testContent = '# E2E Test Content\nThis file is safe to delete.';
    r = await rpc(bridge, 'claudemd.save', { path: testPath, content: testContent });
    assert(r.result === true, `claudemd.save should return true (got: ${JSON.stringify(r.result)})`);
    console.log(`  save test file: OK`);

    // Verify (Python write_text on Windows may convert \n → \r\n)
    const savedRaw = fs.readFileSync(testPath, 'utf-8');
    const saved = savedRaw.replace(/\r\n/g, '\n');
    assert(saved === testContent, `Content mismatch: expected ${testContent.length} chars, got ${saved.length} chars. Expected: "${testContent.slice(0,40)}" Got: "${saved.slice(0,40)}"`);
    console.log(`  verify content: OK`);

    // Cleanup
    fs.unlinkSync(testPath);
    console.log(`  cleanup: OK`);
  }

  // ─── 8. Memory ────────────────────────────────────────────
  console.log('\n[8] Memory');
  r = await rpc(bridge, 'memory.list');
  const mems = r.result;
  assert(Array.isArray(mems), 'memory.list should return array');
  assert(mems.length >= 0, `memory.list count=${mems.length}`);

  if (mems.length > 0) {
    assert(mems[0].name, 'Memory entry should have name');
    assert(mems[0].description !== undefined, 'Memory entry should have description');
    assert(mems[0].content !== undefined, 'Memory entry should have content');
    console.log(`  ${mems.length} memory files`);

    // Test delete on a NON-EXISTENT name (safe)
    r = await rpc(bridge, 'memory.delete', { name: '__TEST_NONEXISTENT__' });
    // Should return false (not found)
    assert(r.result === false, `Delete non-existent should return false (got: ${r.result})`);
    console.log(`  delete non-existent: correct (false)`);
  }

  // ─── 9. Settings ──────────────────────────────────────────
  console.log('\n[9] Settings');
  r = await rpc(bridge, 'settings.get');
  const settings = r.result;
  assert(settings && typeof settings === 'object', 'settings.get should return object');
  assert(settings.baidu_api !== undefined, 'settings should have baidu_api');
  assert(settings.translate_cache_exists !== undefined, 'settings should have cache status');
  console.log(`  settings OK, cache_exists=${settings.translate_cache_exists}`);

  // Save settings (non-destructive: save the same values back)
  r = await rpc(bridge, 'settings.save', { baidu_api: settings.baidu_api });
  assert(r.result === true, 'settings.save should return true');
  console.log(`  save settings: OK`);

  // ─── 10. Translation ──────────────────────────────────────
  console.log('\n[10] Translation');
  // Test translate.batch with skills domain
  r = await rpc(bridge, 'translate.batch', {
    domain: 'skills',
    items: [{ name: 'e2e-test', text: 'Hello world' }]
  });
  const tlResult = r.result || {};
  assert(!tlResult.error, `translate.batch skills should not error: ${tlResult.error}`);
  console.log(`  translate.batch skills: ${Object.keys(tlResult).length} results`);

  // Test translate.batch with plugins domain
  r = await rpc(bridge, 'translate.batch', {
    domain: 'plugins',
    items: [{ name: 'e2e-test', text: 'Browser automation' }]
  });
  const ptlResult = r.result || {};
  assert(!ptlResult.error, `translate.batch plugins should not error: ${ptlResult.error}`);
  console.log(`  translate.batch plugins: ${Object.keys(ptlResult).length} results`);

  // ─── 11. GitHub Import URL Parsing ────────────────────────
  console.log('\n[11] GitHub Import (URL parse only, no network)');
  // Just verify the import handler exists
  r = await rpc(bridge, 'skills.import', { url: 'invalid-url' });
  // Should return an error object, not crash
  assert(r.result !== undefined || r.error !== undefined, 'import should handle invalid URL gracefully');
  console.log(`  import error handling: OK`);

  // ─── Summary ──────────────────────────────────────────────
  console.log('\n' + '='.repeat(60));
  console.log(`RESULTS: ${passed} PASSED, ${failed} FAILED`);
  if (failures.length > 0) {
    console.log('\nFAILURES:');
    failures.forEach(f => console.log(`  - ${f}`));
  }
  console.log('='.repeat(60));

  // Cleanup cache from e2e tests
  try {
    const cachePath = 'C:/Users/31904/.claude/.claude-manage-translations.json';
    if (fs.existsSync(cachePath)) {
      const cache = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
      // Remove e2e test entries
      for (const d of ['skills', 'plugins']) {
        if (cache[d]) {
          for (const k of Object.keys(cache[d])) {
            if (k.startsWith('hello world') || k === 'browser automation') {
              delete cache[d][k];
            }
          }
        }
      }
      fs.writeFileSync(cachePath, JSON.stringify(cache));
    }
  } catch(e) { /* ignore */ }

  bridge.kill();
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });

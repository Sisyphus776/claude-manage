const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let mainWindow = null;
let pythonProcess = null;
let requestId = 0;
const pending = new Map();

// ── Python Backend ────────────────────────────────────────────────────

function createPythonProcess(cmd, args) {
  const proc = spawn(cmd, args, { stdio: ['pipe', 'pipe', 'pipe'] });

  let buffer = '';
  proc.stdout.on('data', (data) => {
    buffer += data.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg = JSON.parse(line);
        if (msg.id !== undefined && pending.has(msg.id)) {
          const { resolve } = pending.get(msg.id);
          pending.delete(msg.id);
          resolve(msg.error ? { error: msg.error } : { result: msg.result });
        } else if (msg.result || msg.error) {
          // Response for already resolved request (ignore)
        }
      } catch (e) { /* ignore */ }
    }
  });

  proc.stderr.on('data', (data) => {
    console.error('Python stderr:', data.toString());
  });

  proc.on('exit', (code) => {
    console.log('Python exited with code', code);
    if (code !== 0 && code !== null) {
      pythonProcess = null;
    }
  });

  return proc;
}

function startPythonBackend() {
  const isPackaged = app.isPackaged;

  if (isPackaged) {
    const exePath = path.join(process.resourcesPath, 'bridge.exe');
    console.log('Starting packaged bridge:', exePath, 'exists:', fs.existsSync(exePath));
    if (!fs.existsSync(exePath)) {
      console.error('bridge.exe not found!');
      return null;
    }
    return createPythonProcess(exePath, []);
  } else {
    // Dev mode: auto-detect Python from env or PATH
    const pythonExe = process.env.CM_PYTHON || 'python';
    const scriptPath = path.join(__dirname, '..', 'bridge.py');
    console.log('Starting dev bridge:', pythonExe, scriptPath);
    return createPythonProcess(pythonExe, [scriptPath]);
  }
}

// ── IPC Handler ───────────────────────────────────────────────────────

ipcMain.handle('rpc-call', async (_event, method, params) => {
  return new Promise((resolve) => {
    if (!pythonProcess || !pythonProcess.stdin.writable) {
      resolve({ error: { code: -1, message: 'Backend not running' } });
      return;
    }
    const id = ++requestId;
    pending.set(id, { resolve });
    const req = JSON.stringify({ jsonrpc: '2.0', id, method, params: params || {} });
    try {
      pythonProcess.stdin.write(req + '\n');
    } catch (e) {
      pending.delete(id);
      resolve({ error: { code: -1, message: 'Write error: ' + e.message } });
    }
  });
});

ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.on('window-close', () => mainWindow?.close());

// ── Window ────────────────────────────────────────────────────────────

function createWindow() {
  const iconPath = path.join(__dirname, 'icon.png');
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 750,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    icon: iconPath,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.webContents.on('did-fail-load', (event, code, desc, url) => {
    console.error('Page load failed:', code, desc, url);
  });

  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }
}

// ── App Lifecycle ─────────────────────────────────────────────────────

app.whenReady().then(() => {
  pythonProcess = startPythonBackend();
  createWindow();

  app.on('before-quit', () => {
    if (pythonProcess) {
      pythonProcess.kill();
      pythonProcess = null;
    }
  });
});

app.on('window-all-closed', () => app.quit());

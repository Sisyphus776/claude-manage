const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ccm', {
  // JSON-RPC call to Python backend
  rpc: (method, params) => ipcRenderer.invoke('rpc-call', method, params || {}),

  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
});

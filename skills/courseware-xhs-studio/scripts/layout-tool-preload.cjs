const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('xhsDesktop', {
  files: {
    readImageDataUrl: (file) => ipcRenderer.invoke('layout:read-image', file)
  }
});

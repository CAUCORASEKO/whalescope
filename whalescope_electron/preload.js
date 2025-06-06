const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    loadData: (args) => ipcRenderer.invoke('load-data', args)
});

console.log('[Preload] preload.js loaded');
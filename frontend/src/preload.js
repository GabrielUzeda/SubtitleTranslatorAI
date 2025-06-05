const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Script operations
  getScriptInfo: () => ipcRenderer.invoke('get-script-info'),
  executeScript: (options) => ipcRenderer.invoke('execute-script', options),
  killScript: () => ipcRenderer.invoke('kill-script'),
  
  // File/Directory selection
  selectFile: (options) => ipcRenderer.invoke('select-file', options),
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
  
  // Prerequisites check
  checkPrerequisites: () => ipcRenderer.invoke('check-prerequisites'),
  
  // Settings/Store
  getStoredValue: (key) => ipcRenderer.invoke('store-get', key),
  setStoredValue: (key, value) => ipcRenderer.invoke('store-set', key, value),
  
  // System operations
  showItemInFolder: (path) => ipcRenderer.invoke('show-item-in-folder', path),
  
  // Event listeners
  onScriptOutput: (callback) => {
    ipcRenderer.on('script-output', (event, data) => callback(data));
  },
  
  removeScriptOutputListener: () => {
    ipcRenderer.removeAllListeners('script-output');
  }
}); 
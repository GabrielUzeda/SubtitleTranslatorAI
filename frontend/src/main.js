const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const Store = require('electron-store');
const ScriptParser = require('./script-parser');
const os = require('os');

// Initialize store for user preferences
const store = new Store();

// Keep a global reference of the window object
let mainWindow;

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    show: false,
    // Hide the menu bar
    autoHideMenuBar: true,
    // Alternative: completely remove menu bar
    menuBarVisible: false
  });

  // Completely remove the menu bar for a cleaner look
  mainWindow.setMenuBarVisibility(false);

  // Load the app
  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  // Show window when ready to prevent visual flash
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Open DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

// App event listeners
app.whenReady().then(createWindow);

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', function () {
  if (mainWindow === null) createWindow();
});

// Get backend path
function getBackendPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend');
  } else {
    return path.join(__dirname, '..', '..', 'backend');
  }
}

// Get main.sh path
function getMainScriptPath() {
  const backendPath = getBackendPath();
  return path.join(backendPath, 'main.sh');
}

// Ensure main.sh has execute permissions
function ensureExecutePermissions() {
  const scriptPath = getMainScriptPath();
  try {
    // Don't try to set permissions if app is packaged (AppImage is read-only)
    if (app.isPackaged) {
      console.log('App is packaged, skipping permission changes');
      return true;
    }
    
    if (process.platform !== 'win32') {
      fs.chmodSync(scriptPath, '755');
    }
    return true;
  } catch (error) {
    console.error('Error setting execute permissions:', error);
    return false;
  }
}

// Parse script arguments using enhanced parser
function parseScriptArguments() {
  const scriptPath = getMainScriptPath();
  try {
    const content = fs.readFileSync(scriptPath, 'utf8');
    const parser = new ScriptParser(content);
    
    // Get arguments using enhanced parsing
    const args = parser.parseArguments();
    
    // Get additional metadata
    const metadata = parser.getScriptMetadata();
    const modes = parser.getOperationModes();
    
    // Enhance arguments with specific knowledge about main.sh
    const enhancedArgs = args.map(arg => {
      // Add better descriptions for known flags
      switch (arg.flag) {
        case '-a':
        case '--all':
          return {
            ...arg,
            description: 'Process all available subtitles',
            longDescription: 'Extract and translate all subtitle tracks found in the MKV file'
          };
        case '-s':
        case '--select':
          return {
            ...arg,
            description: 'Select best subtitle by language priority',
            longDescription: 'Automatically select the best subtitle track based on language preferences'
          };
        case '-h':
        case '--help':
          return {
            ...arg,
            description: 'Show help information',
            hidden: true // Don't show in UI as it's not useful for GUI
          };
        default:
          return arg;
      }
    });

    // Filter out hidden arguments
    const visibleArgs = enhancedArgs.filter(arg => !arg.hidden);
    
    console.log('Parsed arguments:', visibleArgs);
    console.log('Script metadata:', metadata);
    console.log('Operation modes:', modes);
    
    return {
      arguments: visibleArgs,
      metadata,
      modes
    };
  } catch (error) {
    console.error('Error parsing script arguments:', error);
    return {
      arguments: [
        {
          flag: 'input',
          description: 'MKV file to process',
          type: 'file',
          required: true,
          accept: '.mkv'
        },
        {
          flag: '-s',
          description: 'Select best subtitle (default)',
          type: 'boolean'
        },
        {
          flag: '-a',
          description: 'Process all subtitles',
          type: 'boolean'
        }
      ],
      metadata: {
        description: 'Subtitle translation tool',
        requirements: ['Docker', 'Docker Compose', 'Bash']
      },
      modes: []
    };
  }
}

// IPC handlers
ipcMain.handle('get-script-info', async () => {
  ensureExecutePermissions();
  const parseResult = parseScriptArguments();
  
  return {
    scriptPath: getMainScriptPath(),
    backendPath: getBackendPath(),
    ...parseResult
  };
});

ipcMain.handle('select-file', async (event, options = {}) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: options.filters || [
      { name: 'All Files', extensions: ['*'] }
    ]
  });
  
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('select-directory', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('execute-script', async (event, options) => {
  return new Promise((resolve, reject) => {
    const { args, workingDir } = options;
    
    let command, commandArgs, actualWorkingDir;
    
    console.log('=== DEBUGGING EXECUTE-SCRIPT ===');
    console.log('Debug - App packaged:', app.isPackaged);
    console.log('Debug - Options received:', options);
    console.log('Debug - Platform:', process.platform);
    
    // Always use the wrapper script approach for consistency
    const wrapperPath = app.isPackaged 
      ? path.join(__dirname, 'wrapper.sh')  // Inside asar: src/wrapper.sh
      : path.join(__dirname, 'wrapper.sh');
    
    console.log('Debug - Wrapper path:', wrapperPath);
    console.log('Debug - Wrapper exists:', fs.existsSync(wrapperPath));
    
    // For packaged apps, extract wrapper to a temporary location
    if (app.isPackaged) {
      try {
        const tempDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'subtitletranslatorai-wrapper-'));
        const tempWrapperPath = path.join(tempDir, 'wrapper.sh');
        
        // Read and extract wrapper
        const wrapperContent = fs.readFileSync(wrapperPath, 'utf8');
        fs.writeFileSync(tempWrapperPath, wrapperContent);
        fs.chmodSync(tempWrapperPath, '755');
        
        console.log('Debug - Wrapper extracted to:', tempWrapperPath);
        
        command = 'bash';
        commandArgs = [tempWrapperPath, ...args];
        actualWorkingDir = workingDir || process.cwd();
        
        // Store temp dir for cleanup
        event.sender.tempWrapperDir = tempDir;
      } catch (extractError) {
        console.error('Debug - Failed to extract wrapper:', extractError);
        return reject(new Error(`Failed to extract wrapper script: ${extractError.message}`));
      }
    } else {
      // For development, use wrapper directly
      command = 'bash';
      commandArgs = [wrapperPath, ...args];
      actualWorkingDir = workingDir || process.cwd();
    }
    
    // Validate command and arguments
    console.log('Debug - Final command:', command);
    console.log('Debug - Final args:', commandArgs);
    console.log('Debug - Final working dir:', actualWorkingDir);
    
    // Check if bash is available
    try {
      require('child_process').execSync('which bash', { stdio: 'ignore' });
      console.log('Debug - Bash is available');
    } catch (error) {
      return reject(new Error('Bash is not available on this system'));
    }
    
    // Validate wrapper script
    const wrapperToExecute = commandArgs[0];
    if (!fs.existsSync(wrapperToExecute)) {
      return reject(new Error(`Wrapper script does not exist: ${wrapperToExecute}`));
    }
    
    // Validate working directory
    if (!fs.existsSync(actualWorkingDir)) {
      return reject(new Error(`Working directory does not exist: ${actualWorkingDir}`));
    }
    
    console.log('=== STARTING SPAWN ===');
    console.log('Executing:', command, commandArgs);
    console.log('Working directory:', actualWorkingDir);
    
    // Prepare environment - preserve all host environment for maximum compatibility
    const env = {
      ...process.env,
      // Ensure Docker access
      DOCKER_HOST: process.env.DOCKER_HOST || 'unix:///var/run/docker.sock',
      // Preserve AppImage environment variables
      APPDIR: process.env.APPDIR,
      APPIMAGE: process.env.APPIMAGE,
      // Ensure paths are preserved
      PATH: process.env.PATH,
      HOME: process.env.HOME,
      USER: process.env.USER,
      // Docker configuration
      DOCKER_BUILDKIT: '1',
      COMPOSE_DOCKER_CLI_BUILD: '1'
    };
    
    try {
      const child = spawn(command, commandArgs, {
        cwd: actualWorkingDir,
        env: env,
        shell: false,
        stdio: ['pipe', 'pipe', 'pipe'],
        detached: false
      });
      
      console.log('Debug - Spawn successful, PID:', child.pid);
      
      let stdout = '';
      let stderr = '';
      
      child.stdout.on('data', (data) => {
        const output = data.toString();
        stdout += output;
        
        // Safely send output to renderer with error handling
        try {
          if (event.sender && !event.sender.isDestroyed()) {
            event.sender.send('script-output', { type: 'stdout', data: output });
          }
        } catch (error) {
          // Ignore EPIPE and connection errors when renderer is closed
          if (error.code !== 'EPIPE' && error.code !== 'ECONNRESET') {
            console.error('Error sending stdout to renderer:', error.message);
          }
        }
      });
      
      child.stderr.on('data', (data) => {
        const output = data.toString();
        stderr += output;
        
        // Safely send output to renderer with error handling
        try {
          if (event.sender && !event.sender.isDestroyed()) {
            event.sender.send('script-output', { type: 'stderr', data: output });
          }
        } catch (error) {
          // Ignore EPIPE and connection errors when renderer is closed
          if (error.code !== 'EPIPE' && error.code !== 'ECONNRESET') {
            console.error('Error sending stderr to renderer:', error.message);
          }
        }
      });
      
      child.on('close', (code) => {
        console.log('Debug - Process closed with code:', code);
        
        // Clean up temporary wrapper directory
        if (event.sender.tempWrapperDir) {
          try {
            fs.rmSync(event.sender.tempWrapperDir, { recursive: true, force: true });
            console.log('Cleaned up temp wrapper directory:', event.sender.tempWrapperDir);
            delete event.sender.tempWrapperDir;
          } catch (error) {
            console.error('Error cleaning up temp wrapper directory:', error);
          }
        }
        
        resolve({
          exitCode: code,
          stdout,
          stderr
        });
      });
      
      child.on('error', (error) => {
        console.error('Spawn error:', error);
        
        // Clean up on error
        if (event.sender.tempWrapperDir) {
          try {
            fs.rmSync(event.sender.tempWrapperDir, { recursive: true, force: true });
            delete event.sender.tempWrapperDir;
          } catch (cleanupError) {
            console.error('Error cleaning up temp wrapper directory:', cleanupError);
          }
        }
        
        reject(error);
      });
      
      // Store child process reference for potential termination
      event.sender.childProcess = child;
    } catch (spawnError) {
      console.error('Failed to spawn process:', spawnError);
      reject(spawnError);
    }
  });
});

ipcMain.handle('kill-script', async (event) => {
  if (event.sender.childProcess) {
    event.sender.childProcess.kill();
    event.sender.childProcess = null;
    return true;
  }
  return false;
});

ipcMain.handle('check-prerequisites', async () => {
  const checks = {
    docker: false,
    dockerCompose: false,
    bash: false
  };
  
  // Check Docker
  try {
    const docker = spawn('docker', ['--version'], { shell: true });
    await new Promise((resolve, reject) => {
      docker.on('close', (code) => {
        checks.docker = code === 0;
        resolve();
      });
      docker.on('error', reject);
    });
  } catch (error) {
    console.log('Docker not found:', error.message);
  }
  
  // Check Docker Compose
  try {
    const compose = spawn('docker', ['compose', '--version'], { shell: true });
    await new Promise((resolve, reject) => {
      compose.on('close', (code) => {
        checks.dockerCompose = code === 0;
        resolve();
      });
      compose.on('error', reject);
    });
  } catch (error) {
    console.log('Docker Compose not found:', error.message);
  }
  
  // Check Bash (mainly for Windows)
  if (process.platform === 'win32') {
    try {
      const bash = spawn('bash', ['--version'], { shell: true });
      await new Promise((resolve, reject) => {
        bash.on('close', (code) => {
          checks.bash = code === 0;
          resolve();
        });
        bash.on('error', reject);
      });
    } catch (error) {
      console.log('Bash not found:', error.message);
    }
  } else {
    checks.bash = true; // Unix systems have bash by default
  }
  
  return checks;
});

// Store management
ipcMain.handle('store-get', async (event, key) => {
  return store.get(key);
});

ipcMain.handle('store-set', async (event, key, value) => {
  store.set(key, value);
});

ipcMain.handle('show-item-in-folder', async (event, path) => {
  shell.showItemInFolder(path);
});

// Handle app ready
app.on('ready', () => {
  ensureExecutePermissions();
});

// Add global error handlers to prevent crashes
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  
  // Ignore EPIPE errors which are common when IPC channels close
  if (error.code === 'EPIPE' || error.code === 'ECONNRESET') {
    console.log('Ignoring EPIPE/ECONNRESET error - likely due to closed IPC channel');
    return;
  }
  
  // For other errors, log and continue (don't crash)
  console.error('Application error, but continuing execution...');
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
  // Don't crash on unhandled rejections
}); 
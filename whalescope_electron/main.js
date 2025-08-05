const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      enableRemoteModule: false,
      nodeIntegration: false,
    },
  });

  win.loadFile('index.html');
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Detectar modo dev o producción
const isDev = !app.isPackaged;

// Función para resolver rutas de Python y scripts
function resolvePythonPaths() {
  const isWin = process.platform === 'win32';
  const isMac = process.platform === 'darwin';

  // Ruta a Python embebido en producción, o venv local en dev
  const pythonPath = isDev
    ? (isWin
        ? path.join(__dirname, '..', 'venv', 'Scripts', 'python.exe')
        : path.join(__dirname, '..', 'venv', 'bin', 'python3'))
    : (isWin
        ? path.join(process.resourcesPath, 'python_embed', 'python.exe')
        : path.join(process.resourcesPath, 'python_embed', 'bin', isMac && process.arch === 'x64' ? 'python3.11-intel64' : 'python3.11'));

  // Ruta al script whalescope.py
  const scriptPath = isDev
    ? path.join(__dirname, '..', 'whalescope.py')
    : path.join(process.resourcesPath, 'whalescope.py');

  return { pythonPath, scriptPath };
}


// IPC para llamar Python desde renderer y devolver datos
ipcMain.handle('load-data', async (event, { section, startDate, endDate }) => {
  console.log(`[Main] Solicitud: ${section} desde ${startDate} hasta ${endDate}`);

  const { pythonPath, scriptPath } = resolvePythonPaths();
  const command = `"${pythonPath}" "${scriptPath}" ${section} --start-date=${startDate} --end-date=${endDate}`;
  console.log(`[Main] Ejecutando: ${command}`);

  try {
    const { stdout, stderr } = await execPromise(command, {
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      cwd: path.dirname(scriptPath),
    });

    if (stderr) {
      console.error(`[Main] stderr Python: ${stderr}`);
    }

    const data = JSON.parse(stdout);
    return data;
  } catch (error) {
    const msg = `Error ejecutando script Python (${section}): ${error.message}`;
    console.error(`[Main] ${msg}`);
    console.error(`[Main] Error details: ${error.stderr || error.message}`);
    return { error: msg, errorDetails: error.stderr || error.message };
  }
});
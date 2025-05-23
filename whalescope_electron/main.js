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
      nodeIntegration: false
    }
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

ipcMain.handle('load-data', async (event, { section, startDate, endDate }) => {
  console.log(`[Main] Received load-data request for ${section} from ${startDate} to ${endDate}`);
  try {
    const pythonPath = path.join(__dirname, '..', 'venv', 'bin', 'python3');
    const scriptPath = path.join(__dirname, '..', 'whalescope.py');
    const command = `${pythonPath} "${scriptPath}" ${section} --start-date=${startDate} --end-date=${endDate}`;
    console.log(`[Main] Executing: ${command}`);
    
    const { stdout, stderr } = await execPromise(command, { env: { ...process.env, PYTHONUNBUFFERED: '1' } });
    if (stderr) {
      console.error(`[Main] Stderr: ${stderr}`);
    }
    console.log(`[Main] Stdout: ${stdout}`);
    
    const data = JSON.parse(stdout);
    console.log(`[Main] Parsed data:`, JSON.stringify(data, null, 2));
    return data;
  } catch (error) {
    console.error(`[Main] Error: ${error.message}`);
    console.error(`[Main] Full error:`, error);
    return { error: error.message };
  }
});
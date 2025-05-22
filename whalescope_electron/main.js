const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { exec } = require('child_process');
const fs = require('fs');
const util = require('util');

const execPromise = util.promisify(exec);

console.log('[Main] main.js loaded');

function createWindow() {
    console.log('[Main] Creating window');
    const mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            enableRemoteModule: false,
            nodeIntegration: false
        }
    });

    console.log('[Main] Loading index.html');
    mainWindow.loadFile('index.html').then(() => {
        console.log('[Main] Window loaded: index.html');
    }).catch(err => {
        console.error('[Main] Error loading index.html:', err.message);
    });

    return mainWindow;
}

app.whenReady().then(() => {
    console.log('[Main] App ready');
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    console.log('[Main] All windows closed');
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

ipcMain.handle('load-data', async (event, args) => {
    console.log('[Main] Received load-data request:', args);
    try {
        const { section, startDate, endDate } = args;
        if (!section) {
            throw new Error('Section not specified');
        }
        console.log(`[Main] Executing script for section: ${section}`, { startDate, endDate });

        const pythonCommand = path.join(__dirname, '..', 'venv', 'bin', 'python');
        let scriptPath;
        if (section === 'blackrock') {
            scriptPath = path.join(__dirname, '..', 'blackrock.py');
        } else {
            scriptPath = path.join(__dirname, '..', 'whalescope.py');
        }

        if (!fs.existsSync(pythonCommand)) {
            console.error(`[Main] Python command not found: ${pythonCommand}`);
            return { error: `Python command not found: ${pythonCommand}` };
        }

        if (!fs.existsSync(scriptPath)) {
            console.error(`[Main] Script not found: ${scriptPath}`);
            return { error: `Script not found: ${scriptPath}` };
        }

        let command = `${pythonCommand} ${scriptPath} ${section}`;
        if (startDate && endDate) {
            command += ` --start-date=${startDate} --end-date=${endDate}`;
        }
        console.log('[Main] Executing command:', command);

        const { stdout, stderr } = await execPromise(command);
        if (stderr) {
            console.error(`[Main] Stderr from ${section}: ${stderr}`);
            return { error: stderr };
        }
        console.log(`[Main] Raw stdout from ${section}:`, stdout);

        let data;
        try {
            data = JSON.parse(stdout);
            console.log(`[Main] Parsed data from ${section}:`, JSON.stringify(data, null, 2));
        } catch (err) {
            console.error(`[Main] Error parsing JSON from ${section}:`, err.message);
            return { error: `Invalid JSON output: ${err.message}` };
        }

        return data;
    } catch (err) {
        console.error('[Main] Error in load-data handler:', err.message);
        return { error: err.message };
    }
});
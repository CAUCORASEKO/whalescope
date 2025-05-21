const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { execSync } = require('child_process');

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
    console.log('[Main] Received load-data request for section:', args.section);
    try {
        const { section, startDate, endDate } = args;
        console.log(`[Main] Executing whalescope.py for mode: ${section}`, { startDate, endDate });

        const pythonCommand = path.join(__dirname, '..', 'venv', 'bin', 'python');
        const scriptPath = path.join(__dirname, '..', 'whalescope.py');
        const command = `${pythonCommand} ${scriptPath} ${section} --start-date=${startDate} --end-date=${endDate}`;
        console.log('[Main] Executing command:', command);

        const stdout = execSync(command, { encoding: 'utf8' });
        console.log(`[Main] Raw stdout from whalescope.py (${section}):`, stdout);

        let data;
        try {
            data = JSON.parse(stdout);
            console.log(`[Main] Parsed data from whalescope.py (${section}):`, JSON.stringify(data, null, 2));
        } catch (err) {
            console.error('[Main] Error parsing JSON from whalescope.py:', err.message);
            return { error: `Invalid JSON output: ${err.message}` };
        }

        return data;
    } catch (err) {
        console.error('[Main] Error executing whalescope.py:', err.message);
        return { error: err.message };
    }
});
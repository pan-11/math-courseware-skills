// Loads the configured local template unchanged; never starts the desktop app.
const { app, BrowserWindow, ipcMain } = require('electron');
const fs = require('node:fs');
const path = require('node:path');

const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const runtime = path.join(job.output_dir, 'runtime');
for (const dir of ['profile', 'crashes', 'logs']) {
  fs.mkdirSync(path.join(runtime, dir), { recursive: true });
}
app.setPath('userData', path.join(runtime, 'profile'));
app.setPath('sessionData', path.join(runtime, 'profile'));
app.setPath('crashDumps', path.join(runtime, 'crashes'));
app.setAppLogsPath(path.join(runtime, 'logs'));
app.disableHardwareAcceleration();

const inputs = new Map(job.images.map((item) => [path.resolve(item.path), item.path]));
ipcMain.handle('layout:read-image', async (_event, file) => {
  if (typeof file !== 'string' || !inputs.has(path.resolve(file))) {
    return { ok: false, error: 'Image is not in this job input list' };
  }
  try {
    const original = inputs.get(path.resolve(file));
    const mime = path.extname(original).toLowerCase() === '.png' ? 'image/png' : 'image/jpeg';
    return { ok: true, dataUrl: `data:${mime};base64,${fs.readFileSync(original).toString('base64')}` };
  } catch (error) {
    return { ok: false, error: error.message };
  }
});

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'layout-tool-preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      backgroundThrottling: false
    }
  });
  try {
    win.webContents.session.webRequest.onBeforeRequest((request, callback) => {
      callback({ cancel: /^https?:/i.test(request.url) });
    });
    await win.loadFile(job.template_file);
    const payload = JSON.stringify({ images: job.images, config: job.config });
    const outputs = await win.webContents.executeJavaScript(
      `(async () => {
        if (!window.xhsLayoutAutomation?.render) throw new Error('Local template has no automation renderer');
        return window.xhsLayoutAutomation.render(${payload});
      })()`
    );
    if (!Array.isArray(outputs) || outputs.length !== job.outputs.length) {
      throw new Error('Local template returned an unexpected output count');
    }
    for (let index = 0; index < outputs.length; index++) {
      const match = /^data:image\/jpeg;base64,([A-Za-z0-9+/=]+)$/.exec(outputs[index].dataUrl || '');
      if (!match) throw new Error('Local template did not return a JPEG image');
      const name = job.outputs[index].file;
      if (path.basename(name) !== name) throw new Error('Invalid output filename');
      fs.writeFileSync(path.join(job.output_dir, name), Buffer.from(match[1], 'base64'), { flag: 'wx' });
    }
    fs.writeFileSync(path.join(runtime, 'renderer-result.json'), JSON.stringify({
      files: job.outputs.map((item) => item.file)
    }, null, 2), { flag: 'wx' });
    win.destroy();
    app.exit(0);
  } catch (error) {
    console.error(error.stack || String(error));
    win.destroy();
    app.exit(1);
  }
}).catch((error) => {
  console.error(error.stack || String(error));
  app.exit(1);
});

import express from 'express';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import http from 'http';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;
const PYTHON_PORT = 8899;

// Start Python Cintamani Server as background process
console.log(`[Cintamani Supervisor] Spawning Python FastAPI Server on port ${PYTHON_PORT}...`);
const pythonProcess = spawn('python3', ['-u', 'run.py'], {
  env: {
    ...process.env,
    PORT: String(PYTHON_PORT),
  },
  stdio: 'inherit',
});

pythonProcess.on('error', (err) => {
  console.error('[Cintamani Supervisor] Failed to start Python server:', err);
});

// Proxy all /api/* requests to Python backend
app.use('/api', (req, res) => {
  const targetUrl = `http://127.0.0.1:${PYTHON_PORT}${req.originalUrl}`;
  const options: http.RequestOptions = {
    method: req.method,
    headers: {
      ...req.headers,
      host: `127.0.0.1:${PYTHON_PORT}`,
    },
  };

  const proxyReq = http.request(targetUrl, options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode || 200, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  proxyReq.on('error', (err) => {
    if (!res.headersSent) {
      res.status(502).json({
        error: 'Backend Python Cintamani server is initializing or unavailable.',
        details: err.message,
      });
    }
  });

  req.pipe(proxyReq, { end: true });
});

// Serve web_ui static assets
const webUiDir = path.join(__dirname, 'web_ui');
app.use('/css', express.static(path.join(webUiDir, 'css')));
app.use('/js', express.static(path.join(webUiDir, 'js')));

// Serve index.html
app.get('*', (req, res) => {
  res.sendFile(path.join(webUiDir, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[Cintamani Gateway] Web Dashboard running on http://0.0.0.0:${PORT}`);
});

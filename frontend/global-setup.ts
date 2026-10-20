import { FullConfig } from '@playwright/test';
import { spawn, ChildProcess } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

let backendProcess: ChildProcess | null = null;

async function waitForBackend(url: string, timeout = 60000): Promise<void> {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        console.log('E2E backend is ready');
        return;
      }
    } catch {
      // Server not ready yet
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw new Error(`E2E backend did not become ready within ${timeout}ms`);
}

export default async function globalSetup(config: FullConfig) {
  console.log('Starting E2E backend...');

  const backendScript = join(__dirname, '..', 'backend', 'scripts', 'start_e2e_backend.py');

  // Use the project's .venv Python interpreter
  const pythonExecutable = join(__dirname, '..', '.venv', 'bin', 'python');

  backendProcess = spawn(pythonExecutable, [backendScript], {
    stdio: ['ignore', 'pipe', 'pipe'],
    cwd: join(__dirname, '..'),
    env: {
      ...process.env,
      PYTHONPATH: join(__dirname, '..', 'backend'),
    },
  });

  backendProcess.stdout?.on('data', (data) => {
    console.log(`[E2E Backend] ${data.toString().trim()}`);
  });

  backendProcess.stderr?.on('data', (data) => {
    console.error(`[E2E Backend Error] ${data.toString().trim()}`);
  });

  // Wait for backend to be ready
  await waitForBackend('http://localhost:8001/api/v1/health');

  // Store the process for teardown
  (globalThis as any).__e2eBackendProcess = backendProcess;

  console.log('E2E backend started successfully');
}
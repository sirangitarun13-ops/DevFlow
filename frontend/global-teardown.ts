import { FullConfig } from '@playwright/test';

export default async function globalTeardown(config: FullConfig) {
  console.log('Stopping E2E backend...');

  const backendProcess = (globalThis as any).__e2eBackendProcess;

  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill('SIGTERM');

    // Wait for process to exit
    await new Promise<void>((resolve) => {
      if (backendProcess.killed) {
        resolve();
        return;
      }
      backendProcess.on('exit', () => resolve());
      setTimeout(() => {
        if (!backendProcess.killed) {
          backendProcess.kill('SIGKILL');
        }
        resolve();
      }, 5000);
    });

    console.log('E2E backend stopped');
  }
}
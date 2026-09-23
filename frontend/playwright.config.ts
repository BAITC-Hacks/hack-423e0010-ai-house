import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir:'./tests', fullyParallel:false, workers:1, timeout:30000,
  reporter:'list',
  use:{baseURL:'http://127.0.0.1:8000',channel:'chrome',headless:true,viewport:{width:1440,height:1100},screenshot:'only-on-failure',trace:'retain-on-failure'},
  webServer:{command:process.platform==='win32'?'.\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000':'.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000',cwd:'..',url:'http://127.0.0.1:8000/api/health',reuseExistingServer:!process.env.CI,timeout:30000},
});


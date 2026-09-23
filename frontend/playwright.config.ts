import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir:'./tests', fullyParallel:false, workers:1, timeout:30000,
  reporter:'list',
  use:{baseURL:'http://127.0.0.1:8765',channel:'chrome',headless:true,viewport:{width:1440,height:1100},screenshot:'only-on-failure',trace:'retain-on-failure'},
  webServer:{command:process.platform==='win32'?'.\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765':'.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765',cwd:'..',url:'http://127.0.0.1:8765/api/health',reuseExistingServer:false,timeout:30000,env:{OPENAI_API_KEY:'',EMBEDDING_PROVIDER:'local',DATABASE_URL:'sqlite:///./data/e2e.db'}},
});


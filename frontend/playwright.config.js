export default {
  testDir: './e2e',
  timeout: 120000,
  workers: 1,
  retries: 0,
  use: {
    baseURL: 'http://localhost:3000',
    headless: true,
    viewport: { width: 1920, height: 900 },
  },
};

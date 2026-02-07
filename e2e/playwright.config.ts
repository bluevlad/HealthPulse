import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  timeout: 30000,
  expect: { timeout: 5000 },

  reporter: [
    ['list'],
    ['html', { outputFolder: './playwright-report', open: 'never' }],
    ['json', { outputFile: './test-results.json' }],
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://study.unmong.com:4030',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    viewport: { width: 1280, height: 720 },
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-chrome', use: { ...devices['Pixel 5'] } },
  ],

  outputDir: './test-results',
});

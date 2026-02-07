import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://study.unmong.com:4030';

test.describe('HealthPulse 메인 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('메인 페이지가 정상적으로 로드되어야 함', async ({ page }) => {
    await expect(page).toHaveTitle(/HealthPulse/);
    await expect(page.getByRole('heading', { name: 'HealthPulse' })).toBeVisible();
    await expect(page.getByText('디지털 헬스케어 뉴스레터')).toBeVisible();
  });

  test('기능 소개 섹션이 표시되어야 함', async ({ page }) => {
    await expect(page.getByText('매일 선별된 뉴스')).toBeVisible();
    await expect(page.getByText('AI 기반 요약')).toBeVisible();
  });

  test('구독하기 버튼이 표시되고 클릭 가능해야 함', async ({ page }) => {
    const subscribeButton = page.getByRole('link', { name: '뉴스레터 구독하기' });
    await expect(subscribeButton).toBeVisible();
    await subscribeButton.click();
    await expect(page).toHaveURL(/\/subscribe/);
  });
});

test.describe('HealthPulse 구독 페이지', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/subscribe');
  });

  test('구독 폼이 정상적으로 표시되어야 함', async ({ page }) => {
    await expect(page).toHaveTitle(/구독 신청/);
    await expect(page.getByLabel('이메일 주소 *')).toBeVisible();
    await expect(page.getByLabel('이름 *')).toBeVisible();
  });

  test('구독 신청 버튼이 표시되어야 함', async ({ page }) => {
    const submitButton = page.getByRole('button', { name: '구독 신청' });
    await expect(submitButton).toBeVisible();
  });

  test('홈으로 돌아가기 링크가 작동해야 함', async ({ page }) => {
    const homeLink = page.getByRole('link', { name: /홈으로 돌아가기/ });
    await expect(homeLink).toBeVisible();
    await homeLink.click();
    await expect(page).toHaveURL('/');
  });
});

test.describe('HealthPulse 관리자 대시보드', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/admin');
  });

  test('관리자 대시보드가 정상적으로 로드되어야 함', async ({ page }) => {
    await expect(page).toHaveTitle(/관리자 대시보드/);
    await expect(page.getByText('Admin Dashboard')).toBeVisible();
  });

  test('사이드바 네비게이션이 표시되어야 함', async ({ page }) => {
    await expect(page.getByRole('link', { name: /Dashboard/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Subscribers/ })).toBeVisible();
  });

  test('통계 카드가 표시되어야 함', async ({ page }) => {
    await expect(page.getByText('Active Subscribers')).toBeVisible();
    await expect(page.getByText('Articles Collected')).toBeVisible();
  });
});

test.describe('HealthPulse 반응형 디자인', () => {
  test('모바일 뷰포트에서 정상 표시', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'HealthPulse' })).toBeVisible();
  });

  test('태블릿 뷰포트에서 정상 표시', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/admin');
    await expect(page.getByText('Admin Dashboard')).toBeVisible();
  });
});

test.describe('HealthPulse 성능', () => {
  test('페이지 로드 시간이 적절해야 함', async ({ page }) => {
    const startTime = Date.now();
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const loadTime = Date.now() - startTime;
    expect(loadTime).toBeLessThan(10000);
  });
});

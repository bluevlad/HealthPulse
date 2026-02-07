import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://study.unmong.com:4030';

test.describe('Health Check API', () => {
  test('GET /api/health - 서버 상태 확인', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/health`);
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('status', 'healthy');
  });
});

test.describe('Subscriber Count API', () => {
  test('GET /api/subscribers/count - 구독자 수 조회', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/subscribers/count`);
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('count');
    expect(typeof data.count).toBe('number');
  });
});

test.describe('Admin Stats API', () => {
  test('GET /api/admin/stats - 관리자 통계 조회', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/admin/stats`);
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('date');
    expect(data).toHaveProperty('article_count');
    expect(data).toHaveProperty('subscriber_count');
  });
});

test.describe('Subscribe API', () => {
  test('POST /subscribe - 유효한 구독 신청', async ({ request }) => {
    const formData = new URLSearchParams();
    formData.append('email', `test_${Date.now()}@example.com`);
    formData.append('name', '테스트 사용자');

    const response = await request.post(`${BASE_URL}/subscribe`, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: formData.toString(),
    });

    expect([200, 302]).toContain(response.status());
  });

  test('POST /subscribe - 필수 필드 누락 시 에러', async ({ request }) => {
    const formData = new URLSearchParams();
    formData.append('email', '');

    const response = await request.post(`${BASE_URL}/subscribe`, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: formData.toString(),
    });

    expect(response.status()).toBe(422);
  });
});

test.describe('Admin Pages', () => {
  test('GET /admin - 관리자 대시보드', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/admin`);
    expect(response.status()).toBe(200);
    const text = await response.text();
    expect(text).toContain('Daily Dashboard');
  });

  test('GET /admin/subscribers - 구독자 목록', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/admin/subscribers`);
    expect(response.status()).toBe(200);
    const text = await response.text();
    expect(text).toContain('Subscriber Management');
  });

  test('GET /admin/send-history - 발송 이력', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/admin/send-history`);
    expect(response.status()).toBe(200);
    const text = await response.text();
    expect(text).toContain('Send History');
  });

  test('GET /admin/articles - 수집 기사', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/admin/articles`);
    expect(response.status()).toBe(200);
    const text = await response.text();
    expect(text).toContain('Collected Articles');
  });
});

test.describe('OpenAPI Spec', () => {
  test('GET /openapi.json', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/openapi.json`);
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('openapi', '3.1.0');
    expect(data.info).toHaveProperty('title', 'HealthPulse');
  });

  test('GET /docs - Swagger UI', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/docs`);
    expect(response.status()).toBe(200);
    const text = await response.text();
    expect(text).toContain('swagger-ui');
  });
});

test.describe('에러 처리', () => {
  test('GET /nonexistent - 404 응답', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/nonexistent-page`);
    expect(response.status()).toBe(404);
  });

  test('POST / - 405 응답', async ({ request }) => {
    const response = await request.post(`${BASE_URL}/`);
    expect(response.status()).toBe(405);
  });
});

test.describe('API 성능', () => {
  test('Health API 응답 시간', async ({ request }) => {
    const startTime = Date.now();
    const response = await request.get(`${BASE_URL}/api/health`);
    const responseTime = Date.now() - startTime;
    expect(response.status()).toBe(200);
    expect(responseTime).toBeLessThan(2000);
  });
});

// Read-only smoke journeys for the Databook frontend.
// No data is created or modified — GET navigation only.
const { test, expect } = require('@playwright/test');

const PROD_HOST = 'databook.nyc';

// Cloudflare rate-limits rapid automated bursts from a single IP with a 429
// (real users are unaffected). Back off and retry so a transient 429 doesn't
// fail the smoke; also space each navigation slightly to stay under the limit.
async function safeGoto(page, path) {
    let resp;
    for (let attempt = 0; attempt < 4; attempt++) {
        resp = await page.goto(path, { waitUntil: 'domcontentloaded' });
        if (!resp || resp.status() !== 429) return resp;
        await page.waitForTimeout(8000 * (attempt + 1)); // 8s, 16s, 24s
    }
    return resp;
}

test.describe('Databook smoke', () => {
    test.beforeEach(async ({ page }) => {
        await page.waitForTimeout(1500); // pace requests to avoid CF 429
    });

    test('homepage loads', async ({ page }) => {
        const response = await safeGoto(page, '/');
        expect(response.status()).toBeLessThan(400);
        await expect(page.locator('body')).toBeVisible();
        expect(await page.title()).not.toEqual('');
    });

    test('organizations page hydrates stat counters', async ({ page }) => {
        // /organizations redirects to the agencies list, whose stat tiles are
        // populated from the API after load; a broken API leaves the counter
        // blank (a &nbsp; placeholder) or 0. #agencies_no is the live hook.
        await safeGoto(page, '/organizations');
        const counter = page.locator('#agencies_no');
        await expect(counter).toBeVisible({ timeout: 30_000 });
        await expect(counter).toHaveText(/[1-9]/, { timeout: 30_000 });
    });

    test('agencies list renders org links', async ({ page }) => {
        await safeGoto(page, '/organizations/agencies');
        await expect(
            page.locator('a[href*="/organization/"]:visible').first()
        ).toBeVisible({ timeout: 30_000 });
    });

    test('districts page loads', async ({ page }) => {
        const response = await safeGoto(page, '/districts');
        expect(response.status()).toBeLessThan(400);
        await expect(page.locator('body')).toBeVisible();
    });

    test('no AJAX calls cross environments', async ({ page, baseURL }) => {
        // Regression guard for the staging-API-URL-on-production bug
        // (commit d1dce6c): a page served from one environment must not
        // call the other environment's API.
        const isProd = new URL(baseURL).host === PROD_HOST;
        const wrongHost = isProd ? 'staging.databook.nyc' : `api.${PROD_HOST}`;
        const crossCalls = [];
        page.on('request', (req) => {
            if (new URL(req.url()).host.includes(wrongHost)) {
                crossCalls.push(req.url());
            }
        });
        await safeGoto(page, '/');
        await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
        expect(crossCalls).toEqual([]);
    });
});

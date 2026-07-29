// E2E smoke tests for the Databook frontend.
//
// Target is controlled by BASE_URL (defaults to production — staging retired):
//   npm run test:e2e                                  (prod, read-only)
//   BASE_URL=http://localhost:8580 npm run test:e2e   (local stack)
//
// ignoreHTTPSErrors tolerates origin cert quirks so a cert issue fails the
// cert monitor, not every E2E test.
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
    testDir: './e2e',
    timeout: 90_000,
    retries: 2,
    // Run serially with a single worker: prod is behind Cloudflare, and a
    // parallel burst from the CI IP trips its rate limit (429). One worker +
    // the per-test pacing/backoff in the spec keeps requests under the limit.
    fullyParallel: false,
    workers: 1,
    use: {
        baseURL: process.env.BASE_URL || 'https://databook.nyc',
        ignoreHTTPSErrors: true,
        screenshot: 'only-on-failure',
    },
    reporter: process.env.CI ? 'github' : 'list',
});

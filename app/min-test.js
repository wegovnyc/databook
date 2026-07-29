const { chromium } = require('playwright');
const url = 'https://staging.databook.nyc/';
(async () => {
    console.log(`Launching Browser`);
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();
    console.log(`Navigating to ${url}`);
    try {
        const response = await page.goto(url, { waitUntil: 'commit', timeout: 15000 });
        console.log(`Got Response: Status ${response.status()}`);
        await page.waitForTimeout(3000); // Give it a sec to run JS
        const hasTables = await page.evaluate(() => document.querySelectorAll('table').length > 0);
        console.log(`Has tables: ${hasTables}`);
    } catch (e) {
        console.log(`Error navigating: ${e.message}`);
    }
    await browser.close();
})();

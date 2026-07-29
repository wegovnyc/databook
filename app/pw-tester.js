const { chromium } = require('playwright');
(async () => {
    const browser = await chromium.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-web-security']
    });
    const context = await browser.newContext();
    const page = await context.newPage();
    const url = 'https://staging.databook.nyc/o/170010040-department-of-education';
    try {
        const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
        console.log(`URL: ${url}`);
        console.log(`Final URL: ${response.url()}`);
        console.log(`Status: ${response.status()}`);
    } catch (e) {
        console.log(e.message);
    }
    await browser.close();
})();

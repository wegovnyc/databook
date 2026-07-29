const { chromium } = require('playwright');
(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();
    const url = 'https://staging.databook.nyc/o/170010040-department-of-education';
    console.log(`Navigating to ${url}`);
    const response = await page.goto(url, { waitUntil: 'domcontentloaded' });
    console.log(`Status: ${response.status()}`);
    console.log(`URL: ${response.url()}`);
    await browser.close();
})();

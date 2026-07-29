const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    try {
        await page.goto('https://staging.databook.nyc/organizations/directory', { waitUntil: 'networkidle' });
        await page.waitForTimeout(5000);
        const html = await page.content();
        fs.writeFileSync('/tmp/orgs_page.html', html);
        console.log("DOM saved to /tmp/orgs_page.html");
    } catch (e) {
        console.error("Error evaluating directory:", e);
    }
    await browser.close();
})();

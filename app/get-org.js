const { chromium } = require('playwright');
(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.goto('https://staging.databook.nyc/organizations/directory', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000); // let vue and databables mount a bit
    const links = await page.$$eval('a[href^="/o/"]', els => els.map(e => e.getAttribute('href')));
    console.log("Found links: ", links.slice(0, 3));
    if (links.length > 0) {
        console.log('Use this ID: ' + links[0]);
    }
    await browser.close();
})();

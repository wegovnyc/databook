const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    try {
        await page.goto('https://staging.databook.nyc/organizations/all', { waitUntil: 'domcontentloaded' });
        await page.waitForTimeout(4000);
        const links = await page.$$eval('a', anchors => anchors.map(a => a.href).filter(href => href.includes('/o/')));
        if (links.length > 0) {
            console.log("FOUND VALID LINK:", links[0]);
            fs.writeFileSync('/tmp/valid_org.txt', links[0]);
        } else {
            console.log("No organization links found.");
        }
    } catch (e) {
        console.error("Error:", e);
    }
    await browser.close();
})();

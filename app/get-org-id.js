const { chromium } = require('playwright');
(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.goto('https://staging.databook.nyc/organizations/directory');

    // Wait for React/Vue/DataTables to mount and fetch
    await page.waitForTimeout(4000);

    // Try to find any link matching the organization profile pattern
    const links = await page.$$eval('a[href^="/o/"]', anchors => anchors.map(a => a.getAttribute('href')));

    if (links.length > 0) {
        console.log("SUCCESS: Found organization URL -", links[0]);
    } else {
        console.log("FAIL: No organization URLs found on the directory page.");
        console.log("HTML Sample:", await page.evaluate(() => document.body.innerHTML.substring(0, 500)));
    }

    await browser.close();
})();

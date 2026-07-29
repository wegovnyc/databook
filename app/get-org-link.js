const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    try {
        await page.goto('https://staging.databook.nyc/organizations/directory', { waitUntil: 'commit' });
        // Let the Vue app and DataTables initialize and fetch the /api/orgs JSON payload
        await page.waitForTimeout(6000);

        // Extract the content of the very first row in the organization datatable
        const validLink = await page.evaluate(() => {
            const tableLinks = document.querySelectorAll('table tbody tr td a[href^="/o/"]');
            if (tableLinks.length > 0) {
                return tableLinks[0].getAttribute('href');
            }
            return null;
        });

        if (validLink) {
            console.log("Found Active Profile:", validLink);
            fs.writeFileSync('/tmp/valid_org.txt', validLink);
        } else {
            console.log("No links appeared within 6 seconds.");
        }
    } catch (e) {
        console.error("Error evaluating directory:", e);
    }
    await browser.close();
})();

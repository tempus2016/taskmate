// Render a local HTML file through John's browserless (CDP) and screenshot it.
// Usage: node shot.js <input.html> <output.png> [width] [height]
const { chromium } = require('playwright');
const fs = require('fs');
const CDP = process.env.CDP || 'http://192.168.0.154:3002';
(async () => {
  try {
    const [, , input, output, width, height] = process.argv;
    const html = fs.readFileSync(input, 'utf8');
    const browser = await chromium.connectOverCDP(CDP);
    const ctx = await browser.newContext({
      viewport: { width: Number(width) || 1320, height: Number(height) || 760 },
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    await page.setContent(html, { waitUntil: 'networkidle' });
    await page.waitForTimeout(900);
    await page.screenshot({ path: output, fullPage: true });
    await ctx.close();
    await browser.close();
    console.log('shot ->', output);
  } catch (e) {
    console.error('ERR:', e && e.message);
    process.exit(1);
  }
})();

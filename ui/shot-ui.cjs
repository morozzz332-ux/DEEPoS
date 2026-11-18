// Screenshot each UI frame at 640x480 (2x for crispness) using headed Edge via playwright-core.
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');

(async () => {
  const html = 'file:///' + path.resolve(__dirname, 'mockup.html').replace(/\\/g, '/');
  const outDir = path.resolve(__dirname, 'shots');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true,
  });
  const ctx = await browser.newContext({ viewport: { width: 660, height: 500 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(html, { waitUntil: 'load' });
  await page.waitForTimeout(300);

  const frames = await page.$$('.frame');
  const names = ['01-continue', '02-systems', '03-games', '04-settings', '05-modules', '06-files', '07-info'];
  for (let i = 0; i < frames.length; i++) {
    const file = path.join(outDir, (names[i] || ('frame' + i)) + '.png');
    await frames[i].screenshot({ path: file });
    console.log('saved', file);
  }
  await browser.close();
})();

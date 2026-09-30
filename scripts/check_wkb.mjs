import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true,
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();

  // Listen for console messages
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log(`[browser error] ${msg.text()}`);
    }
  });

  console.log('Navigating to models page...');
  await page.goto('https://wkb.gyjxwh.com/platform/settings?section=models', {
    waitUntil: 'networkidle',
    timeout: 30000,
  });
  await page.waitForTimeout(3000);

  // Take screenshot
  await page.screenshot({ path: 'C:/Users/admin/screenshot-wkb.png', fullPage: true });

  // Get page text content
  const text = await page.evaluate(() => document.body.innerText);
  console.log('=== PAGE TEXT ===');
  console.log(text.substring(0, 5000));

  // Check for any model-related content
  const html = await page.content();
  const modelMatches = html.match(/[A-Za-z0-9_-]+(?:embedding|rerank|v[0-9])[A-Za-z0-9_-]*/gi);
  if (modelMatches) {
    console.log('\n=== POSSIBLE MODEL NAMES ===');
    [...new Set(modelMatches)].forEach(m => console.log(`  ${m}`));
  }

  await browser.close();
  console.log('\nDone!');
})();
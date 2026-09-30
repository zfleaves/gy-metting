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
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      errors.push(`[${msg.type()}] ${msg.text()}`);
    }
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));

  // Go to login page
  console.log('Navigating to login...');
  await page.goto('http://localhost:8000/login', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1000);

  // Get page content to understand the login form
  const loginHtml = await page.content();
  console.log('Login page HTML snippet:', loginHtml.substring(0, 2000));

  // Try to find and fill login form
  const inputs = await page.$$('input');
  console.log(`Found ${inputs.length} inputs on login page`);

  // Take screenshot of login page
  await page.screenshot({ path: 'C:/Users/admin/screenshot-login-pw.png' });

  // Try to login by filling inputs
  if (inputs.length >= 2) {
    await inputs[0].fill('admin');
    await inputs[1].fill('admin123');

    // Find and click submit button
    const buttons = await page.$$('button');
    console.log(`Found ${buttons.length} buttons`);

    for (const btn of buttons) {
      const text = await btn.textContent();
      console.log(`Button: "${text}"`);
    }

    // Click the login/submit button
    if (buttons.length > 0) {
      // Try last button (usually submit)
      await buttons[buttons.length - 1].click();
      await page.waitForTimeout(3000);
    }
  }

  // Navigate to LLM sources
  console.log('\nNavigating to LLM sources...');
  await page.goto('http://localhost:8000/llm-sources', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(2000);

  // Take screenshot
  await page.screenshot({ path: 'C:/Users/admin/screenshot-llm-pw.png' });

  // Get page text content
  const text = await page.evaluate(() => document.body.innerText);
  console.log('\n=== PAGE TEXT ===');
  console.log(text.substring(0, 3000));

  // Check HTML for key elements
  const html = await page.content();
  console.log('\n=== HTML SNIPPET (el-table area) ===');
  const tableMatch = html.match(/<div[^>]*class="[^"]*el-table[^"]*"[^>]*>[\s\S]{0,500}/);
  if (tableMatch) console.log(tableMatch[0].substring(0, 500));

  console.log('\n=== CONSOLE ERRORS ===');
  errors.forEach(e => console.log(e));
  if (!errors.length) console.log('(none)');

  await browser.close();
  console.log('\nDone!');
})();
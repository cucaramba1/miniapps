import { chromium } from '/Users/cucaramba/Claude Code/miniapps/tests/node_modules/playwright-core/index.mjs';
const ctx = await chromium.launchPersistentContext('/Users/cucaramba/.playwright-profiles/trendsee', {
  channel: 'chrome',
  headless: false,
  viewport: { width: 1440, height: 900 },
  args: ['--window-position=80,80'],
});
const page = ctx.pages()[0] || await ctx.newPage();
await page.goto('https://trendsee.io/');
console.log('opened');
await new Promise(() => {});

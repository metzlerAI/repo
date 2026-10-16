// Снимает картинки для каждой собранной фирмы: tg.png, full-mobile.png, full-desktop.png.
// Запуск: node shoot.js [id ...]   (без аргументов снимает все папки в ../out)
const path = require('path');
const fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const OUT = path.resolve(__dirname, '..', 'out');
const ids = process.argv.slice(2).length ? process.argv.slice(2)
  : fs.readdirSync(OUT).filter(d => fs.existsSync(path.join(OUT, d, 'index.html')));

async function open(browser, file, viewport, scale) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: scale, locale: 'ru-RU' });
  const page = await ctx.newPage();
  await page.goto('file://' + file, { waitUntil: 'networkidle' });
  await page.evaluate(() => { document.documentElement.classList.add('shot'); return document.fonts.ready; });
  await page.waitForTimeout(300);
  return { ctx, page };
}

(async () => {
  const browser = await chromium.launch();
  for (const id of ids) {
    const dir = path.join(OUT, id);
    const file = path.join(dir, 'index.html');

    let { ctx, page } = await open(browser, file, { width: 390, height: 844 }, 2);
    await page.screenshot({ path: path.join(dir, 'tg.png') });
    await page.screenshot({ path: path.join(dir, 'full-mobile.png'), fullPage: true });
    await ctx.close();

    ({ ctx, page } = await open(browser, file, { width: 1440, height: 900 }, 1));
    await page.screenshot({ path: path.join(dir, 'full-desktop.png'), fullPage: true });
    await ctx.close();
    console.log(id, 'ok');
  }
  await browser.close();
})();

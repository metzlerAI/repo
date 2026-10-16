// Снимает картинки для каждой собранной фирмы:
//   tg.png            первый экран на телефоне (390 px), для первого сообщения
//   full-mobile.png   весь лендинг на телефоне
//   full-desktop.png  весь лендинг на компьютере (1440 px)
//   desktop-01.png …  тот же лендинг на компьютере, нарезанный на экраны по границам блоков, для созвона
// Запуск: node shoot.js [id ...]   (без аргументов снимает все папки в ../out)
const path = require('path');
const fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const OUT = path.resolve(__dirname, '..', 'out');
const MAX_PART = 1150; // самая высокая часть нарезки, px
const MIN_PART = 420;  // части ниже этого приклеиваются к предыдущей
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

// Режет страницу на части: по возможности по границам блоков .sec, высокий блок делится на равные куски.
function cuts(bounds, total) {
  const points = [0];
  for (const b of bounds) {
    const last = points[points.length - 1];
    const end = b.top + b.height;
    if (end - last <= MAX_PART) continue;
    if (b.top > last) points.push(b.top);
    const from = points[points.length - 1];
    const n = Math.ceil((end - from) / MAX_PART);
    for (let i = 1; i < n; i++) points.push(Math.round(from + (end - from) * i / n));
  }
  if (total - points[points.length - 1] > 0) points.push(total);
  // узкий обрезок (вступление, подвал) приклеиваем к предыдущей части
  for (let i = points.length - 1; i >= 2; i--) {
    if (points[i] - points[i - 1] < MIN_PART) points.splice(i - 1, 1);
  }
  return points;
}

(async () => {
  const browser = await chromium.launch();
  for (const id of ids) {
    const dir = path.join(OUT, id);
    const file = path.join(dir, 'index.html');
    for (const f of fs.readdirSync(dir).filter(f => /^desktop-\d+\.png$/.test(f))) fs.unlinkSync(path.join(dir, f));

    let { ctx, page } = await open(browser, file, { width: 390, height: 844 }, 2);
    await page.screenshot({ path: path.join(dir, 'tg.png') });
    await page.screenshot({ path: path.join(dir, 'full-mobile.png'), fullPage: true });
    await ctx.close();

    ({ ctx, page } = await open(browser, file, { width: 1440, height: 900 }, 1));
    await page.screenshot({ path: path.join(dir, 'full-desktop.png'), fullPage: true });
    const { bounds, total } = await page.evaluate(() => ({
      bounds: [...document.querySelectorAll('.sec')].map(e => ({ top: e.offsetTop, height: e.offsetHeight })),
      total: document.documentElement.scrollHeight,
    }));
    const pts = cuts(bounds, total);
    for (let i = 0; i < pts.length - 1; i++) {
      await page.screenshot({
        path: path.join(dir, `desktop-${String(i + 1).padStart(2, '0')}.png`),
        fullPage: true,
        clip: { x: 0, y: pts[i], width: 1440, height: pts[i + 1] - pts[i] },
      });
    }
    await ctx.close();
    console.log(id, 'ok, частей десктопа:', pts.length - 1);
  }
  await browser.close();
})();

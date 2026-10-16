// Снимает короткое видео-демо макета для Telegram: out/<id>/demo.mp4
//   компьютер 1440x900, 30 кадров/с, без звука, около 17 секунд.
//   Сцены: первый экран, «Работы», квиз (курсор отвечает на 2 вопроса), цены, отзывы, контакты.
// Видео собирается покадрово (scrollTo + скриншот на каждый кадр), потом ffmpeg в H.264.
// Запуск: node video.js [id ...]   (без аргументов снимает все папки в ../out)
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const OUT = path.resolve(__dirname, '..', 'out');
const W = 1440, H = 900, FPS = 30;
const MAX_BYTES = 8 * 1024 * 1024;
// попытки сжатия по очереди, пока файл не станет меньше 8 МБ
const ENCODES = [
  { w: 1440, h: 900, crf: 20 },
  { w: 1440, h: 900, crf: 24 },
  { w: 1280, h: 800, crf: 24 },
  { w: 1280, h: 800, crf: 28 },
];
const ids = process.argv.slice(2).length ? process.argv.slice(2)
  : fs.readdirSync(OUT).filter(d => fs.existsSync(path.join(OUT, d, 'index.html')));

const ease = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2); // easeInOutCubic
const frames = sec => Math.max(1, Math.round(sec * FPS));

// Курсор: стрелка поверх страницы, клики сквозь неё проходят к настоящим кнопкам.
const CURSOR = `
  const c = document.createElement('div');
  c.id = 'demo-cursor';
  c.innerHTML = '<svg width="28" height="28" viewBox="0 0 28 28"><path d="M4 2.5 L4 22 L9.2 17.2 L12.6 25 L16.2 23.4 L12.9 15.8 L20 15.8 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, { position: 'fixed', left: '0', top: '0', zIndex: 2147483647, pointerEvents: 'none',
    width: '28px', height: '28px', margin: '-3px 0 0 -4px', transformOrigin: '4px 3px',
    filter: 'drop-shadow(0 2px 3px rgba(0,0,0,.35))' });
  document.body.appendChild(c);
`;

async function shootDemo(browser, id) {
  const dir = path.join(OUT, id);
  const framesDir = path.join(dir, '.frames');
  fs.rmSync(framesDir, { recursive: true, force: true });
  fs.mkdirSync(framesDir);

  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, locale: 'ru-RU' });
  const page = await ctx.newPage();
  await page.goto('file://' + path.join(dir, 'index.html'), { waitUntil: 'networkidle' });
  // нижняя панель скрыта, все картинки грузятся сразу, чтобы при прокрутке не было пустых мест
  await page.evaluate(async () => {
    document.documentElement.classList.add('shot');
    document.documentElement.style.scrollBehavior = 'auto';
    const imgs = [...document.images];
    imgs.forEach(i => { i.loading = 'eager'; i.decoding = 'sync'; });
    await Promise.all(imgs.map(i => (i.complete ? null : new Promise(r => { i.onload = i.onerror = r; }))));
    await Promise.all(imgs.map(i => i.decode().catch(() => {})));
    await document.fonts.ready;
  });
  await page.waitForLoadState('networkidle');
  const fontOk = await page.evaluate(() => document.fonts.check('16px Geologica'));
  if (!fontOk) console.warn(id, 'внимание: шрифт Geologica не загрузился, видео будет с запасным шрифтом');
  await page.evaluate(CURSOR);

  // точки прокрутки по блокам страницы
  const pos = await page.evaluate(() => {
    const top = s => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().top + scrollY : null; };
    const max = document.documentElement.scrollHeight - innerHeight;
    const quiz = document.querySelector('.quiz').getBoundingClientRect();
    return {
      max,
      works: top('#works'),
      quiz: Math.round(quiz.top + scrollY - (innerHeight - quiz.height) / 2),
      prices: top('#prices'),
      revs: top('.revs'),
      contacts: top('#contacts'),
    };
  });
  const clamp = y => Math.max(0, Math.min(pos.max, Math.round(y ?? 0)));

  let n = 0, scrollY = 0, cur = { x: 1180, y: 640 }, press = 0;
  async function frame() {
    await page.evaluate(([y, x, cy, p]) => {
      window.scrollTo(0, y);
      const c = document.getElementById('demo-cursor');
      c.style.left = x + 'px'; c.style.top = cy + 'px';
      c.style.transform = `scale(${1 - 0.18 * p})`;
    }, [scrollY, cur.x, cur.y, press]);
    await page.screenshot({ path: path.join(framesDir, `f${String(n++).padStart(5, '0')}.png`) });
  }
  async function hold(sec) { for (let i = 0; i < frames(sec); i++) await frame(); }
  async function scrollTo(target, sec) {
    const from = scrollY, to = clamp(target), k = frames(sec);
    for (let i = 1; i <= k; i++) { scrollY = Math.round(from + (to - from) * ease(i / k)); await frame(); }
  }
  async function moveTo(x, y, sec) {
    const from = { ...cur }, k = frames(sec);
    for (let i = 1; i <= k; i++) {
      const t = ease(i / k);
      cur = { x: from.x + (x - from.x) * t, y: from.y + (y - from.y) * t };
      await page.mouse.move(cur.x, cur.y);
      await frame();
    }
  }
  async function click() {
    for (const p of [0.5, 1]) { press = p; await frame(); }
    await page.mouse.click(cur.x, cur.y); // настоящий клик, квиз переключается сам
    for (const p of [0.6, 0.2, 0]) { press = p; await frame(); }
  }
  // центр элемента в окне; на текущей прокрутке
  async function center(selector, index = 0) {
    await page.evaluate(y => window.scrollTo(0, y), scrollY);
    const box = await page.locator(selector).nth(index).boundingBox();
    if (!box) throw new Error(`${id}: не найден ${selector}`);
    return { x: Math.round(box.x + box.width * 0.55), y: Math.round(box.y + box.height * 0.55) };
  }

  // 1. первый экран
  await hold(2);
  // 2. «Работы»: прокрутка и пауза на сетке
  await scrollTo(pos.works, 1.4);
  await hold(1.4);
  // 3. квиз
  await scrollTo(pos.quiz, 2.2); // «Работы» длинные, проезжаем их медленнее
  await hold(0.3);
  const q0 = await page.locator('.q-title').first().textContent();
  for (const pick of [2, 1]) { // шаг 1: третий вариант, шаг 2: второй вариант
    const opt = await center('.q-opt', pick);
    await moveTo(opt.x, opt.y, 0.7);
    await click();
    await hold(0.25);
    const next = await center('.q-next');
    await moveTo(next.x, next.y, 0.6);
    await click();
    await hold(0.5);
  }
  const q2 = await page.locator('.q-title').first().textContent();
  if (q0 === q2) console.warn(id, 'внимание: квиз не переключился');
  // курсор уходит в сторону, чтобы не закрывать текст
  await moveTo(W - 50, H - 50, 0.5);
  // 4. цены, отзывы, контакты
  // блока может не быть (у части фирм отзывы скрыты), тогда он пропускается
  for (const y of [pos.prices, pos.revs].filter(y => y != null)) {
    await scrollTo(y, 1.1);
    await hold(0.5);
  }
  await scrollTo(pos.contacts ?? pos.max, 1.1);
  await hold(2);

  await ctx.close();

  // сборка mp4
  const file = path.join(dir, 'demo.mp4');
  let size = 0, used;
  for (const e of ENCODES) {
    used = e;
    const vf = e.w === W ? [] : ['-vf', `scale=${e.w}:${e.h}:flags=lanczos`];
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(framesDir, 'f%05d.png'),
      ...vf, '-c:v', 'libx264', '-preset', 'slow', '-crf', String(e.crf), '-pix_fmt', 'yuv420p',
      '-movflags', '+faststart', '-an', file]);
    size = fs.statSync(file).size;
    if (size <= MAX_BYTES) break;
  }
  fs.rmSync(framesDir, { recursive: true, force: true });
  const mb = (size / 1024 / 1024).toFixed(1);
  if (size > MAX_BYTES) console.warn(id, `внимание: ${mb} МБ, больше 8 МБ даже после сжатия`);
  console.log(id, `ok: demo.mp4, ${(n / FPS).toFixed(1)} с, ${used.w}x${used.h}, crf ${used.crf}, ${mb} МБ`);
}

(async () => {
  const browser = await chromium.launch();
  for (const id of ids) await shootDemo(browser, id);
  await browser.close();
})();

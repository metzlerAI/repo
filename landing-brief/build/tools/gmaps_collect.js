// Тянет из Google Maps данные фирмы: название, рубрики, рейтинг, адрес, телефон, сайт, часы,
// координаты, фото и отзывы (с ответами владельца). Формат близок к gis_collect.js.
// Без входа в аккаунт Google показывает «limited view»: около 9 фото и 3 отзыва на фирму.
// Запуск: PLAYWRIGHT_MODULE=... node tools/gmaps_collect.js <companies.json> <out_dir> [id ...]
// companies.json: [{"id": "...", "query": "Name Town", "phone": "07..."}]
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const [listFile, outDir, ...only] = process.argv.slice(2);
const firms = JSON.parse(fs.readFileSync(listFile, 'utf8')).filter(f => !only.length || only.includes(f.id));
fs.mkdirSync(outDir, { recursive: true });

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const g = (x, ...idx) => { try { for (const i of idx) x = x[i]; return x ?? null; } catch { return null; } };
const digits = s => (s || '').replace(/\D/g, '').replace(/^44/, '0');
const parse = t => JSON.parse(t.slice(t.indexOf('\n') + 1));

// Поиск места через внутренний запрос карт (тот же, что делает страница поиска).
async function lookup(f) {
  const pb = '!4m12!1m3!1d4000!2d-2.2!3d53.48!2m3!1f0!2f0!3f0!3m2!1i1400!2i1000!4f13.1!7i20!10b1!12m25!1m5!18b1!30b1!31m1!1b1!34e1!2m4!5m1!6e2!20e3!39b1!6m22!49b1!63m0!66b1!74i150000!85b1!91b1!114b1!149b1!206b1!209b1!212b1!213b1!223b1!232b1!233b1!234b1!244b1!246b1!250b1!253b1!10b1!12b1!13b1!14b1!16b1!17m1!3e1!20m3!5e2!6b1!14b1!46m1!1b0!96b1!99b1';
  const url = 'https://www.google.com/search?tbm=map&authuser=0&hl=en&gl=uk&q=' + encodeURIComponent(f.query) + '&pb=' + pb;
  const d = parse(await (await fetch(url, { headers: { 'User-Agent': UA } })).text());
  const places = (g(d, 0, 1) || []).map(x => x[14]).filter(Boolean);
  const p = places.find(x => f.phone && digits(g(x, 178, 0, 0)) === digits(f.phone)) || places[0];
  if (!p) return null;
  return {
    name: g(p, 11), fid: g(p, 10), category: g(p, 13), website: g(p, 7, 0),
    rating: { value: g(p, 4, 7), count: g(p, 4, 8) }, phone: g(p, 178, 0, 0),
    phone_match: !!f.phone && digits(g(p, 178, 0, 0)) === digits(f.phone),
    address: g(p, 39) || (g(p, 2) || []).join(', '),
    point: { lat: g(p, 9, 2), lon: g(p, 9, 3) },
    hours: (g(p, 203, 0) || []).map(x => x[0] + ' ' + (g(x, 3) || []).map(y => y[0]).join(', ')),
  };
}

function photosFrom(place) {
  const out = new Map();
  const walk = x => {
    if (!Array.isArray(x)) return;
    const u = g(x, 6, 0);
    if (typeof u === 'string' && /googleusercontent\.com\/(grass-cs|p|gps-cs)/.test(u)) {
      const key = u.split('=')[0];
      if (!out.has(key)) out.set(key, { url: key + '=w1600', w: g(x, 6, 2, 0), h: g(x, 6, 2, 1), source: 'google' });
    }
    x.forEach(walk);
  };
  walk(place);
  return [...out.values()];
}

async function collect(page, f) {
  const info = await lookup(f);
  if (!info) throw new Error('не найдено в Google Maps');
  const url = 'https://www.google.com/maps/place/' + encodeURIComponent(info.name) + '/data=!4m2!3m1!1s' + info.fid + '?hl=en';
  let place = null;
  const onResp = async r => { if (r.url().includes('/maps/preview/place')) { try { place = parse(await r.text()); } catch {} } };
  page.on('response', onResp);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 40000 });
  await page.waitForSelector('h1', { timeout: 20000 });
  await sleep(4000);
  const add_website = await page.evaluate(() => /Add website/.test(document.body.innerText));
  await page.evaluate(() => document.querySelector('button[role=tab][aria-label^="Reviews"]')?.click());
  await sleep(4000);
  await page.evaluate(() => document.querySelectorAll('button.w8nwRe').forEach(b => b.click()));
  await sleep(800);
  const reviews = await page.evaluate(() => [...document.querySelectorAll('div.jftiEf')].map(r => ({
    rating: +((r.querySelector('span.kvMYJc')?.getAttribute('aria-label') || '').match(/\d/) || [0])[0],
    date: r.querySelector('span.rsqaWe')?.innerText || '',
    name: r.querySelector('.d4r55')?.innerText || '',
    text: r.querySelector('.MyEned .wiI7pd, .wiI7pd')?.innerText || '',
    owner_reply: r.querySelector('.CDe7pd .wiI7pd')?.innerText || '',
  })));
  page.off('response', onResp);
  const photos = place ? photosFrom(g(place, 6)) : [];
  return { id: f.id, ...info, fid: undefined, panel_says_add_website: add_website, maps_url: url,
    counts: { google: photos.length }, photos, reviews };
}

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'en-GB', viewport: { width: 1400, height: 1000 }, userAgent: UA });
  const page = await ctx.newPage();
  for (const f of firms) {
    try {
      const d = await collect(page, f);
      fs.writeFileSync(path.join(outDir, f.id + '.json'), JSON.stringify(d, null, 1));
      console.log([f.id, d.name, d.rating.value + ' (' + d.rating.count + ')', 'phone ' + (d.phone_match ? 'ok' : 'НЕ СОВПАЛ ' + d.phone),
        'site ' + (d.website || (d.panel_says_add_website ? 'нет (Add website)' : 'нет')), 'photos ' + d.photos.length, 'reviews ' + d.reviews.length].join(' | '));
    } catch (e) { console.log(f.id, 'ERR', e.message.slice(0, 160)); }
  }
  await b.close();
})();

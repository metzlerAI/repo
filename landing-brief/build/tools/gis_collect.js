// Собирает из 2ГИС всё, что нужно для макета фирмы, и сохраняет в data/drafts/<id>.json:
//   фото (с пометкой: от владельца, из Instagram, от посетителей), отзывы, часы работы, координаты, название и рубрики.
// Ключи API не зашиты: скрипт открывает карточку фирмы в браузере и берёт адреса запросов, которые делает сама страница.
// Запуск: node tools/gis_collect.js [id ...]   (без аргументов собирает все фирмы из companies.json)
const path = require('path');
const fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const ROOT = path.resolve(__dirname, '..', '..');
const DRAFTS = path.resolve(__dirname, '..', 'data', 'drafts');
const companies = JSON.parse(fs.readFileSync(path.join(ROOT, 'companies.json'), 'utf8'));
const want = process.argv.slice(2);
const DAYS = { Mon: 'пн', Tue: 'вт', Wed: 'ср', Thu: 'чт', Fri: 'пт', Sat: 'сб', Sun: 'вс' };

function hoursText(schedule) {
  if (!schedule) return null;
  const order = Object.keys(DAYS);
  const slot = d => (schedule[d] && schedule[d].working_hours || []).map(h => `${h.from}-${h.to}`).join(', ') || 'выходной';
  const slots = order.map(slot);
  if (slots.every(s => s === slots[0])) return slots[0] === '00:00-24:00' ? 'Круглосуточно' : `Ежедневно ${slots[0]}`;
  const parts = [];
  for (let i = 0; i < 7;) {
    let j = i;
    while (j + 1 < 7 && slots[j + 1] === slots[i]) j++;
    parts.push(`${DAYS[order[i]]}${j > i ? '-' + DAYS[order[j]] : ''} ${slots[i]}`);
    i = j + 1;
  }
  return parts.join(', ');
}

(async () => {
  fs.mkdirSync(DRAFTS, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 1000 }, locale: 'ru-RU',
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36',
  });
  for (const c of companies.filter(c => !want.length || want.includes(c.id))) {
    const page = await ctx.newPage();
    const seen = [];
    page.on('request', r => seen.push(r.url()));
    try {
      await page.goto(c.card + '/tab/photos', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForTimeout(5000);
      const html = await page.content();
      await page.goto(c.card + '/tab/reviews', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForTimeout(5000);

      const fid = c.card.match(/firm\/(\d+)/)[1];
      const photoKey = (seen.find(u => u.includes('api.photo.2gis.com')) || '').match(/key=([^&]+)/);
      const revKey = (seen.find(u => u.includes('public-api.reviews.2gis.com')) || '').match(/key=([^&]+)/);
      const point = html.match(/"point":\{"lat":([\d.]+),"lon":([\d.]+)\}/);
      const sched = html.match(/"schedule":(\{"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)".*?\}\]\}\})/);
      const name = html.match(/"name_ex":(\{[^}]*\})/);

      // Запросы к API делаем из контекста страницы 2ГИС: так их пропускают как обычные запросы сайта
      const data = await page.evaluate(async ({ fid, photoKey, revKey }) => {
        const out = { photos: [], reviews: [] };
        if (photoKey) {
          let token = null;
          for (let i = 0; i < 20; i++) {
            const q = new URLSearchParams({ key: photoKey, page_size: '50', locale: 'ru_RU', preview_size: '656x340' });
            if (token) q.set('page_token', token);
            const j = await (await fetch(`https://api.photo.2gis.com/3.0/objects/${fid}/albums/all/media?${q}`)).json();
            for (const m of j.items || []) {
              if (m.media_type !== 'photo') continue;
              out.photos.push({ url: m.photo.url, w: m.photo.width, h: m.photo.height, source: m.copyright.code, date: (m.creation_time || '').slice(0, 10) });
            }
            token = j.next_page_token;
            if (!token) break;
          }
        }
        if (revKey) {
          const q = new URLSearchParams({ limit: '50', offset: '0', is_advertiser: 'false', fields: 'meta.total_count', sort_by: 'date_edited', key: revKey, locale: 'ru_RU' });
          const j = await (await fetch(`https://public-api.reviews.2gis.com/3.0/branches/${fid}/reviews?${q}`)).json();
          out.reviews = (j.reviews || []).map(r => ({ rating: r.rating, date: (r.date_created || '').slice(0, 10), name: (r.user || {}).name, text: r.text }));
        }
        return out;
      }, { fid, photoKey: photoKey && photoKey[1], revKey: revKey && revKey[1] });

      const draft = {
        id: c.id,
        name_ex: name ? JSON.parse(name[1]) : null,
        point: point ? { lat: +point[1], lon: +point[2] } : null,
        hours: sched ? hoursText(JSON.parse(sched[1])) : null,
        counts: data.photos.reduce((a, p) => (a[p.source] = (a[p.source] || 0) + 1, a), {}),
        photos: data.photos,
        reviews: data.reviews,
      };
      fs.writeFileSync(path.join(DRAFTS, `${c.id}.json`), JSON.stringify(draft, null, 1));
      console.log(`${c.id}: фото ${JSON.stringify(draft.counts)}, отзывов ${draft.reviews.length}, часы: ${draft.hours}`);
    } catch (e) {
      console.log(`${c.id}: ОШИБКА ${e.message.split('\n')[0]}`);
    }
    await page.close();
  }
  await browser.close();
})();

// этап 2: карточки (контакты, часы) для кандидатов с rv>=5 и rt>=4.5, затем отзывы и фото для прошедших
const L = require('./lib'); const F = 'cards.json';
const KEYS = L.J('keys.json');
const OK = x => /Мебель на заказ/.test(x.r) && /Корпусная мебель|Мебель для кухни|Шкаф|Гардероб/i.test(x.r) && !/Стройматериалы|Матрасы|Остекление|Стекло и зеркала|отделочные материалы|Ремонт помещений|Окна|Входные двери|гипермаркет/i.test(x.r) && !/Лемана|Мегастрой|гипермаркет|Торговый комплекс|Ангстрем|Hoff|Леруа|IKEA|Шатура|Мария|Лазурит|Стильные кухни|Первая мебельная/i.test(x.n);
const SOC = /(t\.me|vk\.com|vk\.ru|max\.ru|taplink|instagram|dzen\.ru|rutube|jivo|wa\.me|whatsapp|avito|ok\.ru|youtube|clck\.ru|tiktok|mssg\.me|pinterest)/i;
const CITY = { novosibirsk:'Новосибирск', ekaterinburg:'Екатеринбург', kazan:'Казань', n_novgorod:'Нижний Новгород', chelyabinsk:'Челябинск', krasnoyarsk:'Красноярск', samara:'Самара', ufa:'Уфа', rostov:'Ростов-на-Дону', omsk:'Омск', voronezh:'Воронеж', perm:'Пермь', volgograd:'Волгоград', saratov:'Саратов', tyumen:'Тюмень', izhevsk:'Ижевск', barnaul:'Барнаул', ulyanovsk:'Ульяновск', irkutsk:'Иркутск', khabarovsk:'Хабаровск', yaroslavl:'Ярославль', vladivostok:'Владивосток', makhachkala:'Махачкала', tomsk:'Томск', orenburg:'Оренбург', kemerovo:'Кемерово' };
(async () => {
  const db = L.J('search.json'), cards = L.J(F, {});
  const cand = {};
  for (const [k, v] of Object.entries(db)) { const slug = k.split('|')[0];
    for (const [id, x] of Object.entries(v.firms)) if (x.rv >= 5 && x.rt >= 4.5 && x.city === CITY[slug] && OK(x) && !cands(id)) cand[id] = { slug, q: k.split('|')[1], ...x }; }
  function cands(id) { return cand[id] }
  const todo = Object.keys(cand).filter(id => !cards[id]);
  console.log('кандидатов', Object.keys(cand).length, 'новых', todo.length);
  const { b, p } = await L.open('https://2gis.ru/novosibirsk');
  for (let i = 0; i < todo.length; i += 8) {
    const batch = todo.slice(i, i + 8).map(id => ({ id, slug: cand[id].slug }));
    const res = await p.evaluate(async ({ batch, KEYS, SOCs }) => {
      const SOC = new RegExp(SOCs, 'i');
      return Promise.all(batch.map(async ({ id, slug }) => {
        try {
          const st = P(await fetch('/' + slug + '/firm/' + id).then(r => r.text()));
          const d = st.data.entity.profile[id].data;
          const cs = [].concat(...(d.contact_groups || []).map(g => g.contacts || []));
          const by = t => cs.filter(c => c.type === t).map(c => String(c.url || c.text || c.value || ''));
          const site = by('website'); const real = site.filter(s => !SOC.test(s));
          const out = { site: site.join(' '), s: !site.length ? 'нет' : real.length ? 'есть' : 'соц', tg: by('telegram')[0] || '', wa: by('whatsapp')[0] || '', ph: (cs.find(c => c.type === 'phone') || {}).text || '', sched: d.schedule || null };
          if (out.s === 'есть' || !(out.tg || out.wa)) return [id, out];
          const q = new URLSearchParams({ limit: '50', offset: '0', is_advertiser: 'false', fields: 'meta.total_count', sort_by: 'date_edited', key: KEYS.rev, locale: 'ru_RU' });
          const j = await (await fetch('https://public-api.reviews.2gis.com/3.0/branches/' + id + '/reviews?' + q)).json();
          out.reviews = (j.reviews || []).map(r => ({ rating: r.rating, date: (r.date_created || '').slice(0, 10), name: (r.user || {}).name, text: r.text }));
          const pq = new URLSearchParams({ key: KEYS.photo, page_size: '50', locale: 'ru_RU', preview_size: '656x340' });
          const pj = await (await fetch('https://api.photo.2gis.com/3.0/objects/' + id + '/albums/all/media?' + pq)).json();
          out.photos = (pj.items || []).filter(m => m.media_type === 'photo').map(m => ({ url: m.photo.url, src: (m.copyright || {}).code, date: (m.creation_time || '').slice(0, 10) }));
          return [id, out];
        } catch (e) { return [id, { err: String(e).slice(0, 80) }] }
      }));
    }, { batch, KEYS, SOCs: SOC.source });
    for (const [id, o] of res) cards[id] = Object.assign({}, cand[id], o);
    L.S(F, cards);
    if (i % 80 === 0) console.log(i + batch.length, '/', todo.length);
  }
  const v = Object.values(cards);
  console.log('ошибок', v.filter(x => x.err).length, 'без сайта+мессенджер', v.filter(x => x.reviews).length);
  await b.close();
})();

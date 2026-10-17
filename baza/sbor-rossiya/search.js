const L = require('./lib'); const F = 'search.json';
const cities = process.argv[2].split(',');
const qs = ['кухни на заказ', 'шкафы на заказ', 'корпусная мебель на заказ'];
(async () => {
  const db = L.J(F, {}); const { b, p } = await L.open('https://2gis.ru/novosibirsk');
  for (const c of cities) for (const q of qs) {
    const key = c + '|' + q; if (db[key]) continue;
    const r = await p.evaluate(async ({ c, q }) => {
      const out = { total: 0, firms: {} };
      for (let pg = 1; pg <= 5; pg++) {
        let st = null;
        for (let t = 0; t < 3 && !st; t++) { try { st = P(await fetch('/' + c + '/search/' + encodeURIComponent(q) + (pg > 1 ? '/page/' + pg : '')).then(r => r.text())) } catch (e) { } }
        if (!st) { out.err = 'pg' + pg; break }
        const pr = st.data.entity.profile; if (pg === 1) out.total = (Object.values(st.data.search.profile)[0] || { data: {} }).data.total;
        let n = 0;
        for (const id of Object.keys(pr)) { const d = pr[id].data; if (!d || d.type !== 'branch') continue; n++;
          const rv = d.reviews || {}; const ph = (d.external_content || []).filter(x => x.type === 'photo_album').reduce((a, x) => a + x.count, 0);
          out.firms[id] = { n: d.name, r: (d.rubrics || []).map(x => x.name).join(', '), rv: rv.general_review_count || 0, rt: rv.general_rating || 0, ph, city: ((d.adm_div || []).find(a => a.type === 'city') || {}).name || '', adr: d.address_name || '', pg }; }
        if (!n) break;
      }
      return out;
    }, { c, q });
    db[key] = r; L.S(F, db);
    console.log(key, 'total=' + r.total, 'got=' + Object.keys(r.firms).length, r.err || '');
  }
  await b.close();
})();

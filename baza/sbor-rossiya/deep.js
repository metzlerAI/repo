// полный разбор карточек фирм A: все контакты и все домены, которые встречаются в данных карточки
const L = require('./lib');
const A = L.J('a_ids.json');
(async () => {
  const { b, p } = await L.open('https://2gis.ru/novosibirsk');
  const out = await p.evaluate(async (A) => Promise.all(A.map(async ({ id, slug }) => {
    const st = P(await fetch('/' + slug + '/firm/' + id).then(r => r.text()));
    const d = st.data.entity.profile[id].data;
    const cs = [].concat(...(d.contact_groups || []).map(g => g.contacts || [])).map(c => c.type + ':' + (c.url || c.value || c.text));
    const all = JSON.stringify(d);
    const doms = [...new Set((all.match(/[a-z0-9][a-z0-9.-]*\.(ru|рф|com|net|org|su|pro|online|site|store|shop|info|biz|me|cc)\b/gi) || []).map(s => s.toLowerCase()))]
      .filter(s => !/2gis|photo\.|t\.me|wa\.me|vk\.(com|ru)|max\.ru|taplink|instagram|youtube|ok\.ru|avito|dzen|rutube|whatsapp|clck|yandex|mail\.ru|gmail|bk\.ru|list\.ru|inbox\.ru|rambler|icloud/.test(s));
    return { id, cs, doms };
  })), A);
  L.S('deep.json', out); await b.close();
})();

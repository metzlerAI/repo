const L = require('./lib');
(async () => {
  const id = Object.keys(L.J('search.json')['novosibirsk|кухни на заказ'].firms)[0];
  const { b, p, seen } = await L.open('https://2gis.ru/novosibirsk/firm/' + id + '/tab/reviews');
  await p.goto('https://2gis.ru/novosibirsk/firm/' + id + '/tab/photos', { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(4000);
  const rk = (seen.find(u => u.includes('public-api.reviews.2gis.com')) || '').match(/key=([^&]+)/);
  const pk = (seen.find(u => u.includes('api.photo.2gis.com')) || '').match(/key=([^&]+)/);
  L.S('keys.json', { rev: rk && rk[1], photo: pk && pk[1] });
  console.log(!!rk, !!pk);
  await b.close();
})();

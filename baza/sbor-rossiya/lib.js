const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '/opt/node-tools/node_modules/playwright');
const fs = require('fs');
exports.J = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')) } catch (e) { return d } };
exports.S = (f, v) => fs.writeFileSync(f, JSON.stringify(v));
exports.open = async (url) => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'ru-RU', userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36' });
  const p = await ctx.newPage(); const seen = [];
  p.on('request', r => seen.push(r.url()));
  await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 }); await p.waitForTimeout(3000);
  await p.evaluate(() => { window.P = function (h) { var k = "var initialState = JSON.parse('"; var a = h.indexOf(k); if (a < 0) return null; a += k.length; var b = h.indexOf("');", a); return JSON.parse((0, eval)("'" + h.slice(a, b) + "'")) }; });
  return { b, p, seen };
};

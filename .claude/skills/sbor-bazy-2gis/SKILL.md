---
name: "sbor-bazy-2gis"
description: "Сбор базы малого бизнеса из 2ГИС по запросу и городу с минимумом токенов: контакты, отзывы, есть ли сайт с обязательной перепроверкой (подбор домена, веб-поиск, сверка телефона), приоритеты A/B/C, итог в CSV. Использовать, когда нужна база фирм для рассылки."
---

# Сбор базы из 2ГИС (экономный режим)

Вся обработка идёт внутри браузера на 2gis.ru. В чат приходят только короткие статусы, сводка и финальные строки. Проверено 15.10.2026 на Краснодаре.
Правило из базы знаний: сбор базы не главное занятие (Пантелеев, 39). Собрал, отдал, дальше рассылка.

## Экономия токенов: жёсткие правила
- Никаких скриншотов, read_page, get_page_text, find. Только navigate/preview_start и javascript_tool.
- Код ниже вставляется ОДИН раз за сессию: он сохраняется в localStorage на 2gis.ru. После любого перехода по страницам хватает одной строки: `(0,eval)(localStorage.getItem('__g_code'))`.
- Перед вставкой проверить: `!!localStorage.getItem('__g_code')`. Если true, код заново не вставлять.
- Данные не выводить нигде, кроме `G.summary()` и одного финального `G.rows()`.
- Долгие шаги сами останавливаются на 36 с и пишут «запусти снова»: просто повторить тот же вызов.
- Качество сайтов автоматически не проверять: фильтром его не определить, только глазами и только по просьбе.

## Вопросы пользователю (один раунд кнопками, если не сказано)
Запрос(ы), город (slug: krasnodar, moscow, spb...), что нужно (без сайта / все), сколько фирм (по умолчанию около 100 профильных).

## Шаги
1. `preview_start` на `https://2gis.ru/<город>/search/<запрос>`.
2. Вставить код (раздел «Код») одним вызовом javascript_tool в такой обёртке:
   `localStorage.setItem('__g_code', String.raw\`<КОД>\`); (0,eval)(localStorage.getItem('__g_code')); G.reset()`
   (G.reset только для новой базы; для добора к старой не вызывать.)
3. Первые страницы: `await G.top('<город>','<запрос>',5)` → `total=N 1:+12 ...`. Сервер отдаёт максимум 5 страниц.
4. Хвост (там мелкие фирмы и фирмы без сайта). Быть на странице поиска этого запроса, затем `await G.deep('<запрос>',[10,20,30,...])`. Страницы строго по возрастанию, максимум total/12. Для следующего запроса сначала navigate на его страницу поиска, потом строка-загрузчик.
5. Карточки: `await G.cards('<город>')`, повторять, пока не «готово».
6. Сводка: `G.summary(o)`, где `o = {home:'^<Город> городской|<пригородные районы>', exclRub:'<непрофильные рубрики>', exclName:'<сети>'}`. В сводке есть топ-рубрики: по ним составить exclRub и вызвать summary ещё раз. Для Краснодара home: `'^Краснодар городской|Динской|Тахтамукай'` (хвост поиска наполовину из других городов края). Пример exclRub для ремонта и мебели: `'Агентства недвижимости|Стройматериалы|гипермаркет|Матрасы|двери|бытовой техники|Домашний текстиль|Грузчики|Светотехника'`.
7. Строки: `G.rows(o)` (только без сайта) или `G.rows(Object.assign({all:true},o))`. Формат, он же строка заголовков CSV (скрипт проверки ищет колонки по этим именам): `приоритет;зона;город;название;рубрика;отзывов;рейтинг;сайт;url;telegram;whatsapp;vk;телефон;адрес;запрос стр;id;почта;телефоны;ники`. В «сайт» значения нет/соц/есть. «почта», «телефоны» (все номера цифрами через пробел) и «ники» (ссылки на соцсети) нужны только для проверки сайта. Если база собрана старым кодом и этих колонок нет, перед проверкой ещё раз прогнать `await G.cards` после `localStorage.removeItem('__g_data')`. Ссылка на карточку: `https://2gis.ru/<город>/firm/<id>`.
   Приоритет: A = отзывы ≥1 и есть Telegram или WhatsApp; B = мессенджер без отзывов; C = только телефон или VK.
8. Сохранить: если подключена папка проекта, одним device_bash записать CSV в `<папка проекта>/базы/2ГИС-<запрос>-<дата>.csv` (сначала BOM `printf '\xEF\xBB\xBF'`, потом строка заголовков, потом строки через heredoc с кавычками `<<'EOF'`). Excel открывает такой CSV с разделителем `;` напрямую. xlsx делать только по просьбе. Без папки: тот же CSV в рабочую директорию и SendUserFile.
9. Закрыть вкладку.
10. Проверка сайта, обязательна для всех фирм итогового CSV (кроме «сайт=есть»). Зачем: 2ГИС часто не показывает сайт. Факт по выборке 17.10.2026 (мебель, 38 фирм A по России): у 6 из 38 сайт был, хотя 2ГИС его не показывал. Ещё у 8 сайт был раньше, но домен удалён или на нём заглушка. Скрипт `scripts/proverka_saita.py` из папки скилла, нужны только python3 и curl. Запуск одним device_bash (в Claude Code через Bash):
   - `python3 <скилл>/scripts/proverka_saita.py check <csv>`: проверяет короткие ссылки clck.ru из карточки (куда ведут), почту на своём домене и подбирает домены по никам VK, Telegram, Taplink, OK и почты (.ru .com .online .pro .site). «Есть сайт» ставит только при совпадении телефона или почты из карточки. Около 4 секунд на фирму, в чат пишет одну строку итога и только найденные сайты.
   - `python3 ... todo <csv>`: оставшиеся фирмы, по строке на каждую. По каждой один WebSearch (mode standard) с запросом `"<название без рубрики>" <город> <телефон в виде 999-123-45-67>` и blocked_domains `["2gis.ru","vk.com","avito.ru","zoon.ru","flamp.ru","ok.ru","t.me","spravker.ru","orgpage.ru","rusprofile.ru","list-org.com","yell.ru"]`. Текст поиска в чат не пересказывать, из него взять только домен, похожий на сайт этой фирмы.
   - Каждый такой домен проверить: `python3 ... url <csv> <id> <ссылка>`. Ответы: «есть сайт» (совпал телефон или почта), «удалён» (DNS говорит, что домена нет, значит сайт был и умер), «заглушка» (домен куплен, сайта нет), «под вопросом» (название фирмы на сайте есть, телефон другой: открыть и решить глазами, итог записать через `set`), «чужой» (ничего не пишется).
   - Не верить поиску на слово: он отдаёт устаревшие страницы. Случай из практики: поиск показал city-mebel.com с телефоном фирмы, а домен уже был удалён. Итог ставит только скрипт.
   - Сайты-сетки вида bigmebel-<город>.ru и kukhni-<город>.ru встречаются во многих городах. Одна такая сетка оказалась сайтом фирмы Paderin, но чаще это чужие сайты-агрегаторы. Решать по `url`.
   - Визитка на orgs.biz, Taplink и страница в соцсетях считаются как «нет сайта», это записать через `set`.
   - `python3 ... final <csv>`: пустым ставит «сайт не найден», фирмы с сайтом выносит в `<csv>-есть-сайт.csv`. Если после этого фирм меньше, чем просили, добрать из хвоста и проверить так же.
   - Токены: веб-поиск стоит около 2 тыс. токенов на фирму (оценка). Его делать только по фирмам итогового списка, не по всей выдаче.

## Отчёт
Первой строкой жирным: сколько фирм нужного типа и хватает ли на 100 касаний. Отдельной строкой итог проверки сайта: сколько убрано с сайтом, у скольких сайт умер, сколько под вопросом. Дальше 3-5 строк цифр с пометкой «факт по выборке», где файл, один следующий шаг. Без длинных тире.

## Код (копия лежит в `С ЧИСТОГО ЛИСТА/инструменты/2gis-sbor.js`)
В коде нет обратных кавычек, поэтому он безопасно кладётся в String.raw.
```js
window.G=(function(){
var J=function(k,d){try{var v=JSON.parse(localStorage.getItem(k));return v==null?d:v}catch(e){return d}};
var S=function(k,v){localStorage.setItem(k,JSON.stringify(v))};
var P=function(h){var k="var initialState = JSON.parse('";var a=h.indexOf(k)+k.length;var b=h.indexOf("');",a);return JSON.parse((0,eval)("'"+h.slice(a,b)+"'"))};
var W=function(ms){return new Promise(function(r){setTimeout(r,ms)})};
var SOC=/(t\.me|vk\.com|max\.ru|taplink|instagram|dzen\.ru|rutube|jivo\.chat|wa\.me|avito|ok\.ru|youtube|clck\.ru)/i;
var C=function(s){return String(s==null?'':s).replace(/[;\n\t]/g,',')};
function add(list,q,p,seg){var m=J('__g_ids',{}),n=0;list.forEach(function(id){if(!m[id]){m[id]={q:q,p:p,g:seg};n++}});S('__g_ids',m);return n}
async function top(city,q,pages){pages=pages||5;var out=[];for(var p=1;p<=pages;p++){var st=P(await fetch('/'+city+'/search/'+encodeURIComponent(q)+(p>1?'/page/'+p:'')).then(function(r){return r.text()}));var pr=st.data.entity.profile;var l=Object.keys(pr).filter(function(id){return pr[id].data&&pr[id].data.type==='branch'});if(p===1)out.push('total='+Object.values(st.data.search.profile)[0].data.total);out.push(p+':+'+add(l,q,p,'top'))}return out.join(' ')}
async function deep(q,targets){var t0=Date.now(),out=[],done=J('__g_dd',[]);var cur=function(){var m=location.pathname.match(/page\/(\d+)/);return m?+m[1]:1};
for(var i=0;i<targets.length;i++){var t=targets[i];if(done.indexOf(q+'|'+t)>=0)continue;var g=0;
while(cur()<t&&g++<60){if(Date.now()-t0>36000)return 'PAUSED на стр.'+cur()+', запусти снова. '+out.join(' ');
var ls=[].slice.call(document.querySelectorAll('a[href*="/page/"]')).map(function(a){return{a:a,p:+a.getAttribute('href').match(/page\/(\d+)/)[1]}}).filter(function(x){return x.p<=t&&x.p>cur()});
if(!ls.length)break;ls.sort(function(x,y){return y.p-x.p});ls[0].a.click();await W(1800)}
done.push(q+'|'+t);S('__g_dd',done);if(cur()!==t){out.push(t+':нет');continue}
var l=[].slice.call(document.querySelectorAll('a[href*="/firm/"]')).map(function(a){return a.getAttribute('href').match(/firm\/(\d+)/)[1]});
out.push(t+':+'+add(Array.from(new Set(l)),q,t,'tail'))}return 'OK '+out.join(' ')}
async function cards(city){var t0=Date.now(),m=J('__g_ids',{}),d=J('__g_data',{});var todo=Object.keys(m).filter(function(id){return !d[id]});
var one=async function(id){try{var st=P(await fetch('/'+city+'/firm/'+id).then(function(r){return r.text()}));var p=st.data.entity.profile[id].data;var cs=[].concat.apply([],(p.contact_groups||[]).map(function(g){return g.contacts||[]}));
var by=function(t){return cs.filter(function(c){return c.type===t}).map(function(c){return String(c.url||c.text||c.value||'').split('?')[0]})};
var ad=p.adm_div||[];var f=function(t){return (ad.filter(function(a){return a.type===t})[0]||{}).name||''};var site=by('website');var real=site.filter(function(s){return !SOC.test(s)});var rv=p.reviews||{};var ph=cs.filter(function(c){return c.type==='phone'})[0];
d[id]={n:p.name,r:((p.rubrics||[])[0]||{}).name||'',rv:rv.general_review_count||0,rt:rv.general_rating||'',s:!site.length?'нет':(real.length?'есть':'соц'),site:real[0]||'',tg:by('telegram')[0]||'',wa:by('whatsapp')[0]||'',vk:by('vkontakte')[0]||'',ph:ph?ph.text:'',city:f('city')||f('settlement'),area:f('district_area'),adr:p.address_name||'',em:by('email').join(' '),phs:cs.filter(function(c){return c.type==='phone'}).map(function(c){return String(c.value||c.text||'').replace(/[^0-9]/g,'')}).join(' '),hd:cs.filter(function(c){return /website|vkontakte|odnoklassniki|youtube|instagram|telegram|max/.test(c.type)}).map(function(c){return String(c.url||c.value||c.text||'').split('?')[0]}).join(' ')}}catch(e){d[id]={err:1}}};
for(var i=0;i<todo.length&&Date.now()-t0<36000;i+=10)await Promise.all(todo.slice(i,i+10).map(one));S('__g_data',d);
var left=Object.keys(m).filter(function(id){return !d[id]}).length;return 'карточек '+Object.keys(d).length+'/'+Object.keys(m).length+(left?', осталось '+left+', запусти снова':', готово')}
function rich(o){o=o||{};var m=J('__g_ids',{}),d=J('__g_data',{});var xr=o.exclRub?new RegExp(o.exclRub,'i'):null,xn=o.exclName?new RegExp(o.exclName,'i'):null,hm=o.home?new RegExp(o.home,'i'):null;
return Object.keys(m).filter(function(id){return d[id]&&!d[id].err}).map(function(id){var x=Object.assign({id:id},m[id],d[id]);x.ok=!(xr&&xr.test(x.r))&&!(xn&&xn.test(x.n));x.home=hm?hm.test(x.area+' '+x.city):true;x.pr=(x.tg||x.wa)?(x.rv>=1?'A':'B'):'C';return x}).filter(function(x){return x.ok})}
function summary(o){var L=rich(o);var st=function(a){var n=a.length,k=a.filter(function(x){return x.s!=='есть'}).length;return n+' фирм, без сайта '+k+' ('+(n?Math.round(100*k/n):0)+'%)'};var r={профильных:L.length};
['top','tail'].forEach(function(g){[true,false].forEach(function(h){r[g+(h?'_дом':'_край')]=st(L.filter(function(x){return x.g===g&&x.home===h}))})});
var ns=L.filter(function(x){return x.s!=='есть'});r['без сайта A/B/C (дом|край)']=['A','B','C'].map(function(p){return p+' '+ns.filter(function(x){return x.pr===p&&x.home}).length+'|'+ns.filter(function(x){return x.pr===p&&!x.home}).length}).join(', ');
var rubs={};L.forEach(function(x){rubs[x.r]=(rubs[x.r]||0)+1});r.рубрики=Object.keys(rubs).sort(function(a,b){return rubs[b]-rubs[a]}).slice(0,25).map(function(k){return k+' '+rubs[k]}).join('; ');return r}
function rows(o){o=o||{};var L=rich(o).filter(function(x){return o.all||x.s!=='есть'});
L.sort(function(a,b){return (a.home===b.home?0:(a.home?-1:1))||a.pr.localeCompare(b.pr)||b.rv-a.rv});
return L.map(function(x){return [x.pr,x.home?'дом':'край',x.city,x.n,x.r,x.rv,x.rt,x.s,x.site,x.tg.replace(/https?:\/\/t\.me\//,'@'),x.wa.replace(/https?:\/\/wa\.me\//,''),x.vk.replace(/https?:\/\/vk\.com\//,'vk/'),x.ph,x.adr,x.q+' '+x.p,x.id,x.em||'',x.phs||'',x.hd||''].map(C).join(';')}).join('\n')}
function reset(){['__g_ids','__g_data','__g_dd'].forEach(function(k){localStorage.removeItem(k)});return 'сброшено'}
return {top:top,deep:deep,cards:cards,summary:summary,rows:rows,reset:reset}})();'G готов'
```
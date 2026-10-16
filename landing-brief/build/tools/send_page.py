"""Страница рассылки пачки: по карточке на фирму с текстом, кнопками и альбомом скринов.

Запуск: python3 tools/send_page.py
Берёт companies.json и out/<id>/desktop-NN.png (их делает shoot.js).
Кладёт в landing-brief/send/: пачка-1.html, скрины/<id>/01.jpg… и пачка-1.zip со всем этим.
Тексты сообщений и пометки по фирмам лежат ниже, в FIRMS.
"""
import html
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import quote

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
SEND = ROOT / "send"
SHOTS = SEND / "скрины"

FULL = ("Здравствуйте! Увидел «{acc}» в 2ГИС: у вас {rating} и {reviews}, но нет сайта{extra}. "
        "Набросал, как мог бы выглядеть ваш сайт, скрины прикрепил.")
SHORT = "Здравствуйте! Увидел «{acc}» в 2ГИС, а сайта у вас нет. Набросал, как мог бы выглядеть ваш сайт, скрины прикрепил."
MIDDLE = "Кто ищет {what}, открывает пару {who} на картах и звонит тому, у кого видно {seen} и цены."
TAIL = ("Я Ярослав, делаю сайты для местного бизнеса. Откуда к вам сейчас чаще приходят клиенты? "
        "Если интересно, покажу макет целиком за 15 минут.")

# порядок карточек = порядок отправки
FIRMS = [
    dict(id="simmetriya", what="кухню"),
    dict(id="lerom", what="кухню", who="мебельных салонов",
         first="Здравствуйте! Увидел вашу «Фабрику мебели» на 1 Мая в 2ГИС: у вас 4,9 и 154 отзыва. "
               "Набросал, как мог бы выглядеть сайт именно вашего салона, скрины прикрепил.",
         flags=["без «нет сайта»: у бренда Лером сайт есть"]),
    dict(id="stepmebel", what="кухню", extra=", только Telegram-канал"),
    dict(id="insi", what="детскую мебель", tg_by_phone=True,
         flags=["фото похожи на каталог, это осознанное исключение"]),
    dict(id="interer-yug", what="диван или шкаф",
         flags=["Telegram на втором номере, +7 918 692-85-92"]),
    dict(id="leo", what="мебель на заказ", tg_by_phone=True),
    dict(id="stultop", what="обеденный стол", who="магазинов", seen="столы"),
    dict(id="pyatyy-element", what="кухню или шкаф", tg_by_phone=True),
    dict(id="vivat", what="кухню", short=True, flags=["в макете нет фото работ, только заглушки"]),
    dict(id="ars-mebel", what="диван", who="мебельных салонов", seen="модели", short=True,
         flags=["тот же адрес, что у «Стиля»: если это одна фирма, пиши только одной"]),
    dict(id="mebelnaya-tema", what="кухню", short=True, tg_by_phone=True),
    dict(id="stil", what="диван", who="мебельных салонов", seen="модели", short=True,
         flags=["сначала открой mebelstyleshop.ru: этот адрес на их вывеске. Если там их сайт, не пиши",
                "в макете нет фото работ, только заглушки"]),
]


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def message(f, c):
    if f.get("first"):
        first = f["first"]
    elif f.get("short"):
        first = SHORT.format(acc=c["acc"])
    else:
        r = c["rating"]
        rating = "пятёрка" if r == 5 else f"{r:.1f}".replace(".", ",")
        n = c["reviews"]
        first = FULL.format(acc=c["acc"], rating=rating, reviews=f'{n} {plural(n, "отзыв", "отзыва", "отзывов")}',
                            extra=f.get("extra", ""))
    middle = MIDDLE.format(what=f["what"], who=f.get("who", "мебельщиков"), seen=f.get("seen", "работы"))
    return "\n".join([first, middle, TAIL])


def album(cid):
    """Копирует desktop-NN.png в скрины/<id>/NN.jpg: Telegram всё равно пережимает, а архив выходит в разы легче."""
    src = sorted(OUT.glob(f"{cid}/desktop-*.png"))
    dst = SHOTS / cid
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob("*.jpg"):
        old.unlink()
    names = []
    for i, p in enumerate(src, 1):
        name = f"{i:02d}.jpg"
        Image.open(p).convert("RGB").save(dst / name, quality=88)
        names.append(f"скрины/{cid}/{name}")
    return names


def card(n, f, c):
    cid = f["id"]
    text = message(f, c)
    imgs = album(cid)
    phone_raw = re.sub(r"\D", "", c["wa"])
    if c.get("tg"):
        tg, how = c["tg"], "Telegram"
    elif f.get("tg_by_phone"):
        tg, how = f"https://t.me/+{phone_raw}", "Telegram по номеру WhatsApp"
        f.setdefault("flags", []).append("в 2ГИС Telegram не указан: если чат не откроется, пиши в WhatsApp")
    else:
        tg, how = None, "WhatsApp"
    wa = f'{c["wa"]}?text={quote(text)}'
    flags = "".join(f'<span class="fl">{html.escape(x)}</span>' for x in f.get("flags", []))
    thumbs = "".join(f'<a href="{p}" target="_blank"><img src="{p}" alt="{i}"></a>' for i, p in enumerate(imgs, 1))
    buttons = (f'<a class="b1" href="{tg}" target="_blank">1. Открыть чат ({how})</a>' if tg else
               f'<a class="b1" href="{wa}" target="_blank">1. Открыть чат (WhatsApp)</a>')
    if tg:
        buttons += f'<a href="{wa}" target="_blank">или WhatsApp</a>'
    js_text = html.escape(json.dumps(text, ensure_ascii=False))
    return f"""<div class="card" id="{cid}"><div class="top"><label><input type="checkbox" data-id="{cid}"> {n}. <b>{html.escape(c["name"])}</b></label>
<span>{how} · {html.escape(c["phone"])} · <a href="{c["card"]}" target="_blank">2ГИС</a></span></div>{flags}
<div class="body"><a class="cover" href="{imgs[0]}" target="_blank"><img src="{imgs[0]}" alt=""></a><div class="r"><pre>{html.escape(text)}</pre>
<div class="bt">{buttons}<button onclick="cp(this,{js_text})">2. Копировать текст</button></div>
<div class="strip">{thumbs}</div>
<small>3. Альбом: открой папку <b>скрины/{cid}</b>, выдели все {len(imgs)} файлов и перетащи в чат одним движением, Telegram соберёт их в альбом по порядку.</small></div></div></div>"""


PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Пачка 1</title><style>
:root{color-scheme:light}
body{font:15px/1.5 -apple-system,Inter,sans-serif;background:#f4f4f2;color:#1b1b1b;max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px} .rule{background:#fff;border-radius:12px;padding:14px 18px;margin:14px 0 22px} .rule p{margin:8px 0}
.card{background:#fff;border-radius:14px;padding:16px 18px;margin-bottom:16px} .card.done{opacity:.45}
.top{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap} .top b{font-size:17px}
.fl{display:inline-block;background:#fff4d6;border-radius:6px;padding:2px 8px;font-size:12px;margin:6px 6px 0 0}
.body{display:flex;gap:18px;margin-top:12px} .cover img{display:block;width:240px;height:150px;object-fit:cover;object-position:top;border-radius:10px;border:1px solid #ddd}
.r{flex:1;min-width:0} pre{white-space:pre-wrap;font:inherit;background:#f7f7f5;border-radius:10px;padding:12px;margin:0}
.bt{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 8px} .bt a,.bt button{border:0;border-radius:8px;padding:9px 14px;font:600 14px/1.2 inherit;font-family:inherit;cursor:pointer;background:#e9e9e4;color:#111;text-decoration:none}
.bt .b1{background:#2b5cff;color:#fff}
.strip{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px} .strip img{display:block;width:84px;height:56px;object-fit:cover;object-position:top;border-radius:6px;border:1px solid #ddd}
small{opacity:.7;display:block}
@media(max-width:640px){.body{flex-direction:column} .cover img{width:100%;height:200px}}
</style></head><body><h1>Пачка 1: 12 сообщений</h1>
<div class="rule"><b>Правила:</b> с рабочего Telegram, не больше 10-15 новых в день. Порядок: открыть чат, вставить текст, перетащить альбом из папки скрины, отправить, поставить галочку.
<p><b>Если ответили «да»:</b> «Отлично! Давайте созвонимся на 10-15 минут: покажу макет с экрана и расскажу, как он может приводить заявки. Вам удобнее сегодня или завтра?»</p>
<p><b>Пинг</b> тем, кто прочитал и молчит, через день-два: «Здравствуйте! Успели глянуть макет? Могу доделать его на ваших фото и показать за 15 минут.»</p>
<p><b>Если спросят цену:</b> «Простой сайт от 9 до 15 тысяч, зависит от количества страниц. Точно скажу за 15 минут созвона: покажу макет целиком и спрошу, что важно именно вам.»</p>
<p><b>Если ответили «нет»,</b> больше не писать. Перед отправкой вбей телефон фирмы в Яндекс: «сайта нет» значит «я не нашёл».</p></div>
{cards}
<script>
function cp(b,t){navigator.clipboard.writeText(t).then(()=>{b.textContent='Скопировано ✓'},()=>{b.textContent='Не вышло, выдели текст вручную'})}
document.querySelectorAll('input[type=checkbox]').forEach(c=>{const k='sent-'+c.dataset.id;try{c.checked=localStorage.getItem(k)==='1'}catch(e){}
const s=()=>c.closest('.card').classList.toggle('done',c.checked);s();c.onchange=()=>{try{localStorage.setItem(k,c.checked?'1':'0')}catch(e){}s()}});
</script></body></html>
"""


def main():
    companies = {c["id"]: c for c in json.loads((ROOT / "companies.json").read_text(encoding="utf-8"))}
    SHOTS.mkdir(parents=True, exist_ok=True)
    cards = "\n".join(card(i, f, companies[f["id"]]) for i, f in enumerate(FIRMS, 1))
    page = SEND / "пачка-1.html"
    page.write_text(PAGE.replace("{cards}", cards), encoding="utf-8")
    with zipfile.ZipFile(SEND / "пачка-1.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(page, page.name)
        for p in sorted(SHOTS.rglob("*.jpg")):
            z.write(p, p.relative_to(SEND).as_posix())
    print(page, "и", SEND / "пачка-1.zip")


if __name__ == "__main__":
    main()

"""Страница рассылки пачки: по карточке на фирму с текстом, кнопками и альбомом скринов.

Запуск: python3 tools/send_page.py [пачка]   (пачки: 1 — Краснодар, rossiya — фирмы из baza-rossiya.xlsx; по умолчанию 1)
Берёт companies.json и out/<id>/desktop-NN.png (их делает shoot.js).
Кладёт в landing-brief/send/: пачка-<пачка>.html, видео/<id>.mp4 (если есть out/<id>/demo.mp4), скрины/<id>/01.jpg…
и пачка-<пачка>.zip со всем этим. Видео, которого ещё нет, страница помечает жёлтым.
Тексты сообщений и пометки по фирмам лежат ниже, в PACKS.
"""
import html
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
SEND = ROOT / "send"
SHOTS = SEND / "скрины"
VIDEOS = SEND / "видео"

# Текст идёт подписью к видео-демо (out/<id>/demo.mp4). Основа из BRIEF.md: вариант A при рейтинге 4,6 и выше, B для остальных.
HELLO = "Здравствуйте! Я Ярослав, делаю сайты для местного бизнеса в Краснодаре. "
VIDEO = "на видео видно, как он работает. Тексты, фото и цвета поменяю под вас. Интересно обсудить?"
A = HELLO + "Увидел «{acc}» в 2ГИС: {rating}, {reviews}, а сайта нет{extra}. Собрал черновик сайта на ваших фото, " + VIDEO
B = HELLO + "Посмотрел «{acc}» в 2ГИС и собрал черновик сайта на ваших фото, " + VIDEO
B_NO_WORKS = HELLO + "Посмотрел «{acc}» в 2ГИС и набросал, как мог бы выглядеть ваш сайт с расчётом стоимости, " + VIDEO  # фото работ нет

# Россия: город в первой фразе не пишем, у фирм с умершим сайтом своя фраза (решения Ярослава 17.10.2026)
HELLO_RU = "Здравствуйте! Я Ярослав, делаю сайты для местного бизнеса. "
DEAD = HELLO_RU + "Увидел «{acc}» в 2ГИС: {rating} и {reviews}. Заметил, что сайт больше не открывается. Собрал черновик нового сайта на ваших фото, " + VIDEO

# порядок карточек = порядок отправки
FIRMS_RU = [
    dict(id="tochka-mebeli", hello=HELLO_RU, dead=True, flags=["тот же адрес, что у «Мастерской дизайна»", "часть фото: рендеры и каталог из Instagram"]),
    dict(id="siti-mebel", hello=HELLO_RU, dead=True, flags=["фото похожи на рендеры"]),
    dict(id="koncept-56", hello=HELLO_RU, extra=", только Taplink"),
    dict(id="diamant", hello=HELLO_RU),
    dict(id="masterskaya-dizayna", hello=HELLO_RU, flags=["тот же адрес, что у «Точки мебели»: если это одна фирма, пиши только одной"]),
    dict(id="mebelm", hello=HELLO_RU, extra=", только Telegram-канал"),
    dict(id="sandera", hello=HELLO_RU),
    dict(id="mebelissimo", hello=HELLO_RU, tg_by_phone=True),
    dict(id="kukhni-teyge", hello=HELLO_RU),
    dict(id="reroom", hello=HELLO_RU),
    dict(id="studiya-72", hello=HELLO_RU),
    dict(id="prestizh", hello=HELLO_RU, flags=["рейтинг 4,5: вариант B, на сайте рейтинг и отзывы скрыты"]),
    dict(id="marle", hello=HELLO_RU, extra=", только Telegram-канал"),
    dict(id="indom", hello=HELLO_RU, extra=", только Taplink", tg_by_phone=True,
         flags=["Telegram в 2ГИС ведёт в группу, лучше писать в WhatsApp"]),
    dict(id="tekstura", hello=HELLO_RU),
]

FIRMS = [
    dict(id="simmetriya"),
    dict(id="lerom",
         text=HELLO + "Увидел вашу «Фабрику мебели» на 1 Мая в 2ГИС: 4,9 и 154 отзыва. "
                      "Собрал черновик сайта вашего салона на ваших фото, " + VIDEO,
         flags=["без «нет сайта»: у бренда Лером сайт есть"]),
    dict(id="stepmebel", extra=", только Telegram-канал"),
    dict(id="insi", tg_by_phone=True, flags=["фото похожи на каталог, это осознанное исключение"]),
    dict(id="interer-yug", flags=["Telegram на втором номере, +7 918 692-85-92"]),
    dict(id="leo", tg_by_phone=True),
    dict(id="stultop"),
    dict(id="pyatyy-element", tg_by_phone=True),
    dict(id="vivat", no_works=True, flags=["в макете нет фото работ, только заглушки"]),
    dict(id="ars-mebel", flags=["тот же адрес, что у «Стиля»: если это одна фирма, пиши только одной"]),
    dict(id="mebelnaya-tema", tg_by_phone=True),
    dict(id="stil", no_works=True,
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
    if f.get("text"):
        return f["text"]
    hello = f.get("hello", HELLO)
    r = c.get("rating")
    if r is None or r < 4.6:
        return (B_NO_WORKS if f.get("no_works") else B).replace(HELLO, hello).format(acc=c["acc"])
    n = c["reviews"]
    rating = "пятёрка" if r == 5 else f"{r:.1f}".replace(".", ",")
    reviews = f'{n} {plural(n, "отзыв", "отзыва", "отзывов")}'
    if f.get("dead"):
        return DEAD.format(acc=c["acc"], rating=rating, reviews=reviews)
    return A.replace(HELLO, hello).format(acc=c["acc"], rating=rating, reviews=reviews, extra=f.get("extra", ""))


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


def video(cid):
    src = OUT / cid / "demo.mp4"
    if not src.exists():
        return None
    VIDEOS.mkdir(parents=True, exist_ok=True)
    (VIDEOS / f"{cid}.mp4").write_bytes(src.read_bytes())
    return f"видео/{cid}.mp4"


def card(n, f, c):
    cid = f["id"]
    text = message(f, c)
    imgs = album(cid)
    vid = video(cid)
    if not vid:
        f.setdefault("flags", []).insert(0, "видео ещё не готово: текст про видео, без него не отправляй")
    phone_raw = re.sub(r"\D", "", c.get("wa") or c["phone"])
    if c.get("tg") and not f.get("tg_by_phone"):
        tg, how = c["tg"], "Telegram"
    elif f.get("tg_by_phone"):
        tg, how = f"https://t.me/+{phone_raw}", "Telegram по номеру WhatsApp"
        f.setdefault("flags", []).append("Telegram не из 2ГИС, а по номеру WhatsApp: если чат не откроется, пиши в WhatsApp")
    else:
        tg, how = None, "WhatsApp"
    wa = f'{c["wa"]}?text={quote(text)}' if c.get("wa") else None
    flags = "".join(f'<span class="fl">{html.escape(x)}</span>' for x in f.get("flags", []))
    thumbs = "".join(f'<a href="{p}" target="_blank"><img src="{p}" alt="{i}"></a>' for i, p in enumerate(imgs, 1))
    buttons = (f'<a class="b1" href="{tg}" target="_blank">1. Открыть чат ({how})</a>' if tg else
               f'<a class="b1" href="{wa}" target="_blank">1. Открыть чат (WhatsApp)</a>')
    if tg and wa:
        buttons += f'<a href="{wa}" target="_blank">или WhatsApp</a>'
    js_text = html.escape(json.dumps(text, ensure_ascii=False))
    if vid:
        cover = f'<video class="cover" src="{vid}" controls muted preload="metadata"></video>'
        step3 = f"3. Перетащи в чат файл <b>{vid}</b>, в поле «Подпись» вставь текст и отправь."
    else:
        cover = f'<a class="cover" href="{imgs[0]}" target="_blank"><img src="{imgs[0]}" alt=""></a>'
        step3 = f"3. Видео <b>out/{cid}/demo.mp4</b> ещё не собрано. Когда появится, запусти tools/send_page.py ещё раз."
    return f"""<div class="card" id="{cid}"><div class="top"><label><input type="checkbox" data-id="{cid}"> {n}. <b>{html.escape(c["name"])}</b></label>
<span>{how} · {html.escape(c["phone"])} · <a href="{c["card"]}" target="_blank">2ГИС</a></span></div>{flags}
<div class="body">{cover}<div class="r"><pre>{html.escape(text)}</pre>
<div class="bt">{buttons}<button onclick="cp(this,{js_text})">2. Копировать текст</button></div>
<div class="strip">{thumbs}</div>
<small>{step3} Скрины выше пригодятся на созвоне, они лежат в папке <b>скрины/{cid}</b>.</small></div></div></div>"""


PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title><style>
:root{color-scheme:light}
body{font:15px/1.5 -apple-system,Inter,sans-serif;background:#f4f4f2;color:#1b1b1b;max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px} .rule{background:#fff;border-radius:12px;padding:14px 18px;margin:14px 0 22px} .rule p{margin:8px 0}
.card{background:#fff;border-radius:14px;padding:16px 18px;margin-bottom:16px} .card.done{opacity:.45}
.top{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap} .top b{font-size:17px}
.fl{display:inline-block;background:#fff4d6;border-radius:6px;padding:2px 8px;font-size:12px;margin:6px 6px 0 0}
.body{display:flex;gap:18px;margin-top:12px} video.cover{width:240px;height:150px;border-radius:10px;background:#000;flex:none} .cover img{display:block;width:240px;height:150px;object-fit:cover;object-position:top;border-radius:10px;border:1px solid #ddd}
.r{flex:1;min-width:0} pre{white-space:pre-wrap;font:inherit;background:#f7f7f5;border-radius:10px;padding:12px;margin:0}
.bt{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 8px} .bt a,.bt button{border:0;border-radius:8px;padding:9px 14px;font:600 14px/1.2 inherit;font-family:inherit;cursor:pointer;background:#e9e9e4;color:#111;text-decoration:none}
.bt .b1{background:#2b5cff;color:#fff}
.strip{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px} .strip img{display:block;width:84px;height:56px;object-fit:cover;object-position:top;border-radius:6px;border:1px solid #ddd}
small{opacity:.7;display:block}
@media(max-width:640px){.body{flex-direction:column} .cover img,video.cover{width:100%;height:200px}}
</style></head><body><h1>{title}: {count} сообщений</h1>
<div class="rule"><b>Правила:</b> с рабочего Telegram, не больше 10-15 новых в день. Порядок: открыть чат, перетащить видео, в поле «Подпись» вставить текст, отправить, поставить галочку. Видео и текст уходят одним сообщением.
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


PACKS = {"1": ("Пачка 1", FIRMS), "rossiya": ("Пачка «Россия»", FIRMS_RU)}


def main():
    pack = sys.argv[1] if len(sys.argv) > 1 else "1"
    title, firms = PACKS[pack]
    companies = {c["id"]: c for c in json.loads((ROOT / "companies.json").read_text(encoding="utf-8"))}
    SHOTS.mkdir(parents=True, exist_ok=True)
    cards = "\n".join(card(i, f, companies[f["id"]]) for i, f in enumerate(firms, 1))
    page = SEND / f"пачка-{pack}.html"
    page.write_text(PAGE.replace("{cards}", cards).replace("{title}", title).replace("{count}", str(len(firms))), encoding="utf-8")
    ids = {f["id"] for f in firms}
    with zipfile.ZipFile(SEND / f"пачка-{pack}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(page, page.name)
        for p in sorted(SHOTS.rglob("*.jpg")) + sorted(VIDEOS.glob("*.mp4")):
            cid = p.parent.name if p.suffix == ".jpg" else p.stem
            if cid in ids:
                z.write(p, p.relative_to(SEND).as_posix())
    print(page, "и", SEND / f"пачка-{pack}.zip")


if __name__ == "__main__":
    main()

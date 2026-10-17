"""Собирает лендинги из companies.json, data/<id>.json и template.html.j2.

Запуск: python3 build.py [id ...]   (без аргументов собирает все фирмы, у которых есть data/<id>.json)
Результат: ../out/<id>/index.html и ../out/<id>/img/*
Британские фирмы: python3 build.py --uk [id ...]  берёт ../../uk-brief/companies.json и uk-brief/data/<id>.json,
пишет в uk-brief/out/<id>/, тексты на английском, карта из OpenStreetMap.

Правило текстов: никаких непроверенных обещаний (бесплатный замер, 3D-проект, сроки, гарантии, цены).
"""
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
UK = "--uk" in sys.argv
ROOT = HERE.parent.parent / "uk-brief" if UK else HERE.parent
DATA = ROOT / "data" if UK else HERE / "data"
OUT = ROOT / "out"
GALLERY_SIZE = 6
WATERMARK_CROP = 0 if UK else 0.07  # 2ГИС ставит водяной знак в правый нижний угол, срезаем низ кадра
DEFAULT_ACCENT = "#d6e6c3"

# ---------- тексты по рубрике ----------

STEPS_FURNITURE = [
    ("Пишете", "Оставляете заявку или пишете в WhatsApp."),
    ("Замер", "Приезжаем и делаем замер."),
    ("Проект", "Согласуем проект и называем точную цену."),
    ("Монтаж", "Изготавливаем и устанавливаем у вас дома."),
]
MENU_FURNITURE = [
    ("Кухни", [("Прямая кухня", "за погонный метр"), ("Угловая кухня", "за погонный метр")]),
    ("Шкафы", [("Шкаф-купе", "за погонный метр"), ("Гардеробная", "под ключ")]),
]
PRICE_NOTE = "Точную цену называем после замера: она зависит от размеров, фасадов и фурнитуры."

TEXTS = {
    "Мебель на заказ": dict(
        line="Кухни и шкафы на заказ в Краснодаре",
        intro="Делаем кухни, шкафы и гардеробные по размерам вашей квартиры."),
    "Мебель для кухни": dict(
        line="Кухни на заказ в Краснодаре",
        intro="Делаем кухни по размерам вашей квартиры: прямые, угловые, с островом."),
    "Корпусная мебель": dict(
        line="Корпусная мебель на заказ в Краснодаре",
        intro="Делаем шкафы, кухни и гардеробные по размерам вашей квартиры."),
    "Мебельные магазины": dict(
        line="Мебель на заказ в Краснодаре",
        intro="Делаем кухни, шкафы и гардеробные по размерам вашей квартиры."),
    "Детская мебель": dict(
        line="Детская мебель в Краснодаре",
        intro="Делаем мебель для детской: кровати, шкафы и рабочие места по размерам комнаты.",
        menu=[("Детская", [("Кровать", "обычная или чердак"), ("Шкаф", "для одежды и игрушек")]),
              ("Комната", [("Рабочее место", "стол и полки"), ("Комната целиком", "по проекту")])]),
    "Мягкая мебель": dict(
        line="Диваны и кресла в Краснодаре",
        intro="Делаем диваны и кресла: подбираем размер, механизм и обивку под вашу комнату.",
        steps=[("Пишете", "Оставляете заявку или пишете в WhatsApp."),
               ("Выбор", "Подбираем размер, механизм и ткань."),
               ("Цена", "Называем точную стоимость и сроки."),
               ("Доставка", "Изготавливаем и привозим к вам домой.")],
        menu=[("Диваны", [("Прямой диван", ""), ("Угловой диван", "")]),
              ("Кресла", [("Кресло", ""), ("Перетяжка", "за диван")])],
        price_note="Точную цену называем, когда выбраны размер, механизм и ткань."),
}
TEXTS_TABLES = dict(
    line="Обеденные столы и стулья в Краснодаре",
    intro="Подбираем обеденный стол под размер кухни и стулья к нему. Всё можно посмотреть в шоуруме.",
    steps=[("Пишете", "Оставляете заявку или пишете в WhatsApp."),
           ("Подбор", "Подбираем стол и стулья под вашу кухню."),
           ("Цена", "Называем стоимость и сроки."),
           ("Доставка", "Привозим и собираем у вас дома.")],
    menu=[("Столы", [("Обеденный стол", "керамика, стекло, дерево"), ("Раскладной стол", "")]),
          ("Стулья", [("Стул", ""), ("Комплект", "стол и стулья")])],
    price_note="Цена зависит от размера, столешницы и комплектации.",
    visit_h="Приезжайте в шоурум")

# ---------- тексты для Великобритании ----------

UI_RU = dict(
    lang="ru", works="Работы", prices="Цены", contacts="Контакты", on_source="в 2ГИС", cta="Рассчитать стоимость",
    placeholder="Здесь будут ваши работы", quiz_private="Ответы увидит только мастер", next="Дальше",
    quiz_done="Готово. Отправьте ответы, и мы посчитаем стоимость.", quiz_send="Получить расчёт в WhatsApp",
    price_html='от <span class="blank"></span> ₽', how="Как заказать", review_src="отзыв в 2ГИС",
    entrance="вход", city="Краснодар", messenger="WhatsApp", on_map="на карте", route="Маршрут в 2ГИС", write_wa="Написать в WhatsApp",
    wa_text="Здравствуйте! Хочу расчёт.")
UI_EN = dict(
    lang="en-GB", works="Our work", prices="Prices", contacts="Contact", on_source="on Google", cta="Get a price",
    placeholder="Your photos go here", quiz_private="Only we see your answers", next="Next",
    quiz_done="Done. Send your answers and we'll work out a price.", quiz_send="Get a price on WhatsApp",
    price_html='from £<span class="blank"></span>', how="How it works", review_src="Google review",
    entrance="outside", city="", messenger="WhatsApp", on_map="on the map", route="Directions on Google Maps", write_wa="Message on WhatsApp",
    wa_text="Hi! I'd like a price.")

STEPS_KITCHEN_EN = [
    ("Message", "Send a message or a few photos on WhatsApp."),
    ("Visit", "We come round and measure up."),
    ("Design", "We agree the design and the price."),
    ("Fit", "We fit your new kitchen."),
]
MENU_KITCHEN_EN = [
    ("Kitchens", [("Supply and fit", "full kitchen"), ("Fit only", "you supply the units")]),
    ("Extras", [("Worktops", "laminate, wood or stone"), ("Doors and handles", "kitchen refresh")]),
]
STEPS_FITTED_EN = [
    ("Message", "Send a message or a few photos on WhatsApp."),
    ("Visit", "We come round and measure up."),
    ("Design", "We agree the design and the price."),
    ("Fit", "We build and fit it."),
]
MENU_FITTED_EN = [
    ("Wardrobes", [("Fitted wardrobes", "floor to ceiling"), ("Walk-in wardrobes", "")]),
    ("Living room", [("Media walls", "TV, storage and lighting"), ("Alcove units and shelving", "")]),
]
STEPS_BUILDER_EN = [
    ("Message", "Send a message or a few photos on WhatsApp."),
    ("Visit", "We come round and look at the job."),
    ("Quote", "We agree the work and the price."),
    ("Build", "We get the work done."),
]
MENU_BUILDER_EN = [
    ("Renovations", [("Full renovation", "house or flat"), ("Room refurbishment", "")]),
    ("Extensions", [("Single-storey extension", ""), ("Porch", "")]),
]
TEXTS_EN = {
    "Kitchens": dict(
        line="Kitchens fitted in Greater Manchester",
        intro="We design and fit kitchens around your home and the way you use it.",
        steps=STEPS_KITCHEN_EN, menu=MENU_KITCHEN_EN,
        price_note="The exact price depends on the size, units and worktops. We'll give you a quote after a visit.",
        visit_h="Visit us"),
    "Fitted furniture": dict(
        line="Fitted furniture in Greater Manchester",
        intro="We design and build furniture to fit the space you have.",
        steps=STEPS_FITTED_EN, menu=MENU_FITTED_EN,
        price_note="The exact price depends on the size, materials and finish. We'll give you a quote after a visit.",
        visit_h="Visit us"),
    "Builders": dict(
        line="Building work in Greater Manchester",
        intro="Renovations and extensions, from the first visit to the finished job.",
        steps=STEPS_BUILDER_EN, menu=MENU_BUILDER_EN,
        price_note="The exact price depends on the size of the job and the materials. We'll give you a quote after a visit.",
        visit_h="Visit us"),
}

# ---------- квизы ----------

def ico(body):
    return f'<svg viewBox="0 0 44 30" fill="currentColor" aria-hidden="true">{body}</svg>'

QUIZZES = {
    "kitchen": dict(h="Сколько будет стоить ваша кухня", pre=2, steps=[
        dict(q="Какая планировка кухни?", opts=[
            dict(t="Прямая", d="вдоль одной стены", icon=ico('<rect x="2" y="3" width="40" height="6"/>')),
            dict(t="Угловая", d="Г-образная", icon=ico('<rect x="2" y="3" width="40" height="6"/><rect x="2" y="3" width="6" height="25"/>')),
            dict(t="П-образная", d="вдоль трёх стен", icon=ico('<rect x="2" y="3" width="40" height="6"/><rect x="2" y="3" width="6" height="25"/><rect x="36" y="3" width="6" height="25"/>')),
            dict(t="С островом", d="рабочая зона в центре", icon=ico('<rect x="2" y="3" width="40" height="6"/><rect x="2" y="3" width="6" height="25"/><rect x="18" y="19" width="16" height="8"/>')),
        ]),
        dict(q="Какая длина по стенам?", opts=[
            dict(t="До 2 м", d="небольшая кухня"), dict(t="2-3 м", d=""),
            dict(t="3-4 м", d=""), dict(t="Больше 4 м", d="кухня-гостиная")]),
        dict(q="Какие фасады нравятся?", opts=[
            dict(t="Плёнка МДФ", d=""), dict(t="Эмаль", d="матовая или глянец"),
            dict(t="Пластик", d=""), dict(t="Пока не знаю", d="подскажем")]),
        dict(q="Когда нужна кухня?", opts=[
            dict(t="Как можно скорее", d=""), dict(t="В течение месяца", d=""),
            dict(t="Через 1-3 месяца", d=""), dict(t="Пока присматриваюсь", d="")]),
    ]),
    "kids": dict(h="Сколько будет стоить детская", pre=4, steps=[
        dict(q="Что нужно в детскую?", opts=[
            dict(t="Кровать", d="обычная или чердак"), dict(t="Шкаф", d="для одежды и игрушек"),
            dict(t="Рабочее место", d="стол и полки"), dict(t="Комната целиком", d="")]),
        dict(q="Сколько детей в комнате?", opts=[
            dict(t="Один", d=""), dict(t="Двое", d=""), dict(t="Трое и больше", d=""), dict(t="Пока не знаю", d="")]),
        dict(q="Сколько лет ребёнку?", opts=[
            dict(t="До 3 лет", d=""), dict(t="3-7 лет", d=""), dict(t="7-12 лет", d=""), dict(t="Подросток", d="")]),
        dict(q="Когда нужна мебель?", opts=[
            dict(t="Как можно скорее", d=""), dict(t="В течение месяца", d=""),
            dict(t="Через 1-3 месяца", d=""), dict(t="Пока присматриваюсь", d="")]),
    ]),
    "soft": dict(h="Сколько будет стоить ваш диван", pre=2, steps=[
        dict(q="Какой диван нужен?", opts=[
            dict(t="Прямой", d=""), dict(t="Угловой", d=""),
            dict(t="Модульный", d=""), dict(t="Кресло", d="")]),
        dict(q="Нужно спальное место?", opts=[
            dict(t="Да, каждый день", d=""), dict(t="Иногда, для гостей", d=""),
            dict(t="Нет", d=""), dict(t="Пока не знаю", d="")]),
        dict(q="Какая обивка нравится?", opts=[
            dict(t="Велюр", d=""), dict(t="Рогожка", d=""),
            dict(t="Антикоготь", d="если есть животные"), dict(t="Пока не знаю", d="")]),
        dict(q="Когда нужен диван?", opts=[
            dict(t="Как можно скорее", d=""), dict(t="В течение месяца", d=""),
            dict(t="Через 1-3 месяца", d=""), dict(t="Пока присматриваюсь", d="")]),
    ]),
    "kitchen_en": dict(h="What would your kitchen cost?", pre=2, steps=[
        dict(q="What's the layout?", opts=[
            dict(t="Single wall", d="along one wall", icon=ico('<rect x="2" y="3" width="40" height="6"/>')),
            dict(t="L-shaped", d="two walls", icon=ico('<rect x="2" y="3" width="40" height="6"/><rect x="2" y="3" width="6" height="25"/>')),
            dict(t="U-shaped", d="three walls", icon=ico('<rect x="2" y="3" width="40" height="6"/><rect x="2" y="3" width="6" height="25"/><rect x="36" y="3" width="6" height="25"/>')),
            dict(t="With an island", d="worktop in the middle", icon=ico('<rect x="2" y="3" width="40" height="6"/><rect x="2" y="3" width="6" height="25"/><rect x="18" y="19" width="16" height="8"/>')),
        ]),
        dict(q="How long are the runs of units?", opts=[
            dict(t="Up to 2 m", d="small kitchen"), dict(t="2-3 m", d=""),
            dict(t="3-4 m", d=""), dict(t="Over 4 m", d="open-plan")]),
        dict(q="Which door style do you like?", opts=[
            dict(t="Shaker", d=""), dict(t="Handleless", d=""),
            dict(t="Gloss", d=""), dict(t="Not sure yet", d="we'll help")]),
        dict(q="When do you need it?", opts=[
            dict(t="As soon as possible", d=""), dict(t="Within a month", d=""),
            dict(t="In 1-3 months", d=""), dict(t="Just looking", d="")]),
    ]),
    "fitted_en": dict(h="What would your fitted furniture cost?", pre=2, steps=[
        dict(q="What do you need?", opts=[
            dict(t="Wardrobes", d="fitted or walk-in"), dict(t="Media wall", d="TV, storage and lighting"),
            dict(t="Alcove units", d="cupboards and shelves"), dict(t="Under-stairs storage", d="")]),
        dict(q="Which room is it for?", opts=[
            dict(t="Bedroom", d=""), dict(t="Living room", d=""),
            dict(t="Hall or stairs", d=""), dict(t="More than one", d="")]),
        dict(q="How wide is the space?", opts=[
            dict(t="Up to 2 m", d=""), dict(t="2-3 m", d=""),
            dict(t="3-4 m", d=""), dict(t="Over 4 m", d="whole wall")]),
        dict(q="When do you need it?", opts=[
            dict(t="As soon as possible", d=""), dict(t="Within a month", d=""),
            dict(t="In 1-3 months", d=""), dict(t="Just looking", d="")]),
    ]),
    "builder_en": dict(h="What would your building work cost?", pre=2, steps=[
        dict(q="What's the job?", opts=[
            dict(t="Renovation", d="one room or more"), dict(t="Extension", d="or a porch"),
            dict(t="Outside work", d="render, brickwork"), dict(t="Something else", d="")]),
        dict(q="What kind of property?", opts=[
            dict(t="Terraced", d=""), dict(t="Semi-detached", d=""),
            dict(t="Detached", d=""), dict(t="Flat or bungalow", d="")]),
        dict(q="How big is the job?", opts=[
            dict(t="One room", d=""), dict(t="A few rooms", d=""),
            dict(t="Whole house", d=""), dict(t="Not sure yet", d="we'll take a look")]),
        dict(q="When do you need it?", opts=[
            dict(t="As soon as possible", d=""), dict(t="Within a month", d=""),
            dict(t="In 1-3 months", d=""), dict(t="Just looking", d="")]),
    ]),
    "wardrobe": dict(h="Сколько будет стоить ваша мебель", pre=1, steps=[
        dict(q="Что нужно?", opts=[
            dict(t="Шкаф-купе", d=""), dict(t="Распашной шкаф", d=""),
            dict(t="Прихожая", d=""), dict(t="Диван", d="")]),
        dict(q="Где будет стоять?", opts=[
            dict(t="Прихожая", d=""), dict(t="Спальня", d=""),
            dict(t="Гостиная", d=""), dict(t="Детская", d="")]),
        dict(q="Какая ширина места?", opts=[
            dict(t="До 1,5 м", d=""), dict(t="1,5-2 м", d=""),
            dict(t="2-3 м", d=""), dict(t="Больше 3 м", d="во всю стену")]),
        dict(q="Когда нужна мебель?", opts=[
            dict(t="Как можно скорее", d=""), dict(t="В течение месяца", d=""),
            dict(t="Через 1-3 месяца", d=""), dict(t="Пока присматриваюсь", d="")]),
    ]),
    "tables": dict(h="Подберём стол за минуту", pre=2, steps=[
        dict(q="Сколько человек за столом?", opts=[
            dict(t="2-4", d=""), dict(t="4-6", d=""), dict(t="6-8", d=""), dict(t="Больше 8", d="")]),
        dict(q="Нужен раскладной стол?", opts=[
            dict(t="Да", d="для гостей"), dict(t="Нет", d=""),
            dict(t="Пока не знаю", d=""), dict(t="Покажите оба", d="")]),
        dict(q="Какая столешница нравится?", opts=[
            dict(t="Керамика", d="под мрамор или камень"), dict(t="Стекло", d=""),
            dict(t="Дерево", d=""), dict(t="Пока не знаю", d="")]),
        dict(q="Нужны стулья?", opts=[
            dict(t="Да, к столу", d=""), dict(t="Только стол", d=""),
            dict(t="Только стулья", d=""), dict(t="Пока не знаю", d="")]),
    ]),
}

def variant_for(c, d):
    if d.get("variant") and d["variant"] != "auto":
        return d["variant"]
    if UK:
        return {"Fitted furniture": "fitted_en", "Builders": "builder_en"}.get(c["rubric"], "kitchen_en")
    return {"Детская мебель": "kids", "Мягкая мебель": "soft"}.get(c["rubric"], "kitchen")

CAM_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 8h3l1.5-2h7L17 8h3v11H4z" stroke-linejoin="round"/><circle cx="12" cy="13" r="3.5"/></svg>'

# ---------- утилиты ----------

def fetch(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Referer": "https://2gis.ru/", "User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=40).read()
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 ** k)

def save_photo(url, dst, max_w=1600, crop=None):
    """crop: (left, top, right, bottom) в долях кадра, чтобы выбрать нужную часть фото."""
    if dst.exists():
        return
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(fetch(url)))).convert("RGB")
    im = im.crop((0, 0, im.width, int(im.height * (1 - WATERMARK_CROP))))
    if crop:
        l, t, r, b = crop
        im = im.crop((int(im.width * l), int(im.height * t), int(im.width * r), int(im.height * b)))
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    im.save(dst, quality=84, optimize=True)

def save_map_osm(point, dst, zoom=16, cols=5, rows=5):
    """Карта из плиток OpenStreetMap с меткой в центре (для фирм вне России, где нет 2ГИС)."""
    import math
    from PIL import ImageDraw
    n = 2 ** zoom
    x = (point["lon"] + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(point["lat"]))) / math.pi) / 2 * n
    x0, y0 = int(x) - cols // 2, int(y) - rows // 2
    im = Image.new("RGB", (cols * 256, rows * 256))
    for i in range(cols):
        for j in range(rows):
            req = urllib.request.Request(f"https://tile.openstreetmap.org/{zoom}/{x0 + i}/{y0 + j}.png",
                                         headers={"User-Agent": "local-landing-mockup/1.0 (demo mockups)"})
            im.paste(Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=40).read())).convert("RGB"), (i * 256, j * 256))
    px, py = (x - x0) * 256, (y - y0) * 256
    w, h = 960, 540
    im = im.crop((int(px - w / 2), int(py - h / 2), int(px + w / 2), int(py + h / 2)))
    dr = ImageDraw.Draw(im)
    dr.ellipse((w / 2 - 13, h / 2 - 13, w / 2 + 13, h / 2 + 13), fill="#0f0f0f", outline="#ffffff", width=4)
    note = "© OpenStreetMap contributors"
    dr.rectangle((w - 8 - 6 * len(note), h - 18, w, h), fill="#ffffff")
    dr.text((w - 4 - 6 * len(note), h - 15), note, fill="#333333")
    im.save(dst)

def save_map(point, dst):
    if dst.exists():
        return True
    if UK:
        try:
            save_map_osm(point, dst)
            return True
        except Exception as e:
            print("  карта не скачалась:", e)
            return False
    url = f"https://static.maps.2gis.com/1.0?zoom=16&size=960,540&markers={point['lon']},{point['lat']}"
    try:
        dst.write_bytes(fetch(url))
        return True
    except Exception as e:
        print("  карта не скачалась:", e)
        return False

def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many

def display_vw(name):
    longest = max(len(w) for w in name.split())
    return round(min(16.5, 132 / max(longest, 1)), 2)

# ---------- сборка ----------

def build(cid, companies, env):
    c = dict(companies[cid])
    d = json.loads((DATA / f"{cid}.json").read_text(encoding="utf-8"))
    out = OUT / cid
    img = out / "img"
    img.mkdir(parents=True, exist_ok=True)

    var = variant_for(c, d)
    if UK:
        t = dict(TEXTS_EN.get(c["rubric"], TEXTS_EN["Kitchens"]))
    else:
        t = dict(TEXTS_TABLES if var == "tables" else TEXTS.get(c["rubric"], TEXTS["Мебель на заказ"]))
    t.setdefault("steps", STEPS_FURNITURE)
    t.setdefault("menu", MENU_FURNITURE)
    t.setdefault("price_note", PRICE_NOTE)
    t.setdefault("visit_h", "Приезжайте в салон")
    t.setdefault("remark", "")
    if c.get("city_in"):  # фирмы не из Краснодара: город в строке «что и где»
        t["line"] = t["line"].replace("в Краснодаре", c["city_in"])
    t.update(d.get("texts", {}))

    hero = d.get("hero") or {}
    if hero.get("src"):
        save_photo(hero["src"], img / "hero.jpg", crop=hero.get("crop"))
    if hero.get("src_desktop"):
        save_photo(hero["src_desktop"], img / "hero-d.jpg", max_w=2000, crop=hero.get("crop_desktop"))

    gallery = []
    for i, g in enumerate(d.get("gallery", [])[:GALLERY_SIZE], 1):
        save_photo(g["src"], img / f"w{i}.jpg", max_w=1400, crop=g.get("crop"))
        gallery.append(g)
    while len(gallery) < GALLERY_SIZE:
        gallery.append({"empty": True})

    steps = []
    photos = d.get("steps_photos", [])
    for i, (verb, text) in enumerate(t["steps"]):
        if not UK and not c.get("wa"):
            text = text.replace("WhatsApp", "Telegram")
        s = {"verb": verb, "text": text, "img": None}
        if i < len(photos):
            save_photo(photos[i], img / f"s{i + 1}.jpg", max_w=900)
            s["img"] = f"s{i + 1}.jpg"
        steps.append(s)
    t["steps"] = steps

    if d.get("review_photo"):
        save_photo(d["review_photo"], img / "review.jpg", max_w=1100)
    if d.get("storefront"):
        save_photo(d["storefront"], img / "place.jpg", max_w=2000)
    has_map = bool(d.get("point")) and save_map(d["point"], img / "map.png")

    c["phone_raw"] = c.get("tel") or "+" + re.sub(r"\D", "", c["phone"])
    c["wa_num"] = re.sub(r"\D", "", c.get("wa") or "")
    c["msg"] = c.get("wa") or c.get("tg")  # нет WhatsApp в 2ГИС: все кнопки ведут в Telegram
    rating = c.get("rating")
    n = c["reviews"]
    quiz = dict(QUIZZES[var])
    quiz["n"] = len(quiz["steps"])
    if UK:
        ui = dict(UI_EN, quiz_p=f"{quiz['n']} quick questions, and we'll send you a price on WhatsApp. No obligation.")
        rating_str = f"{rating:.1f}" if rating else ""
        reviews_str = f'{n} {"review" if n == 1 else "reviews"}'
        score_str = f"★ {rating_str} out of 5 from {reviews_str} on Google"
    else:
        ui = dict(UI_RU, quiz_p=f"{quiz['n']} вопроса, а ответ с ценой пришлём в WhatsApp. Ни к чему не обязывает.")
        if c.get("city"):
            ui["city"] = c["city"]
        if not c.get("wa"):
            ui.update(messenger="Telegram", write_wa="Написать в Telegram", quiz_send="Получить расчёт в Telegram",
                      quiz_p=ui["quiz_p"].replace("WhatsApp", "Telegram"))
        rating_str = f"{rating:.1f}".replace(".", ",") if rating else ""
        reviews_str = f'{n} {plural(n, "отзыв", "отзыва", "отзывов")}'
        score_str = f'★ {rating_str} из 5 по {n} {plural(n, "отзыву", "отзывам", "отзывам")} в 2ГИС'

    html = env.get_template("template.html.j2").render(
        c=c, d=d, t=t, ui=ui, gallery=gallery, quiz=quiz, quiz_json=json.dumps(quiz, ensure_ascii=False),
        accent=d.get("accent", DEFAULT_ACCENT), display_vw=d.get("display_vw") or display_vw(c["name"]),  # display_vw в data: вручную для длинных названий
        has_hero=(img / "hero.jpg").exists(), has_hero_desktop=(img / "hero-d.jpg").exists(),
        has_review_photo=(img / "review.jpg").exists(), has_storefront=(img / "place.jpg").exists(),
        show_rating=rating is not None and rating >= 4.6,
        rating_str=rating_str, reviews_str=reviews_str, score_str=score_str,
        has_map=has_map, cam_icon=CAM_ICON)
    (out / "index.html").write_text(html, encoding="utf-8")
    real = sum(1 for g in gallery if not g.get("empty"))
    print(f"{cid}: {out / 'index.html'} ({var}, фото работ {real}/{GALLERY_SIZE})")

def main():
    companies = {c["id"]: c for c in json.loads((ROOT / "companies.json").read_text(encoding="utf-8"))}
    ids = [a for a in sys.argv[1:] if a != "--uk"] or sorted(p.stem for p in DATA.glob("*.json"))
    env = Environment(loader=FileSystemLoader(HERE), autoescape=True)
    for cid in ids:
        build(cid, companies, env)

if __name__ == "__main__":
    main()

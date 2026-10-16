"""Собирает лендинги из companies.json, data/<id>.json и template.html.j2.

Запуск: python3 build.py [id ...]   (без аргументов собирает все фирмы, у которых есть data/<id>.json)
Результат: ../out/<id>/index.html и ../out/<id>/img/*

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
ROOT = HERE.parent
OUT = ROOT / "out"
GALLERY_SIZE = 6
WATERMARK_CROP = 0.07  # 2ГИС ставит водяной знак в правый нижний угол, срезаем низ кадра
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

def save_map(point, dst):
    if dst.exists():
        return True
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
    d = json.loads((HERE / "data" / f"{cid}.json").read_text(encoding="utf-8"))
    out = OUT / cid
    img = out / "img"
    img.mkdir(parents=True, exist_ok=True)

    var = variant_for(c, d)
    t = dict(TEXTS_TABLES if var == "tables" else TEXTS.get(c["rubric"], TEXTS["Мебель на заказ"]))
    t.setdefault("steps", STEPS_FURNITURE)
    t.setdefault("menu", MENU_FURNITURE)
    t.setdefault("price_note", PRICE_NOTE)
    t.setdefault("visit_h", "Приезжайте в салон")
    t.setdefault("remark", "")
    t.update(d.get("texts", {}))

    hero = d.get("hero") or {}
    if hero.get("src"):
        save_photo(hero["src"], img / "hero.jpg", crop=hero.get("crop"))
    if hero.get("src_desktop"):
        save_photo(hero["src_desktop"], img / "hero-d.jpg", max_w=2000, crop=hero.get("crop_desktop"))

    gallery = []
    for i, g in enumerate(d.get("gallery", [])[:GALLERY_SIZE], 1):
        save_photo(g["src"], img / f"w{i}.jpg", max_w=1400)
        gallery.append(g)
    while len(gallery) < GALLERY_SIZE:
        gallery.append({"empty": True})

    steps = []
    photos = d.get("steps_photos", [])
    for i, (verb, text) in enumerate(t["steps"]):
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

    c["phone_raw"] = "+" + re.sub(r"\D", "", c["phone"])
    c["wa_num"] = re.sub(r"\D", "", c["wa"])
    rating = c.get("rating")
    n = c["reviews"]
    quiz = dict(QUIZZES[var])
    quiz["n"] = len(quiz["steps"])

    html = env.get_template("template.html.j2").render(
        c=c, d=d, t=t, gallery=gallery, quiz=quiz, quiz_json=json.dumps(quiz, ensure_ascii=False),
        accent=d.get("accent", DEFAULT_ACCENT), display_vw=display_vw(c["name"]),
        has_hero=(img / "hero.jpg").exists(), has_hero_desktop=(img / "hero-d.jpg").exists(),
        has_review_photo=(img / "review.jpg").exists(), has_storefront=(img / "place.jpg").exists(),
        show_rating=rating is not None and rating >= 4.6,
        rating_str=f"{rating:.1f}".replace(".", ",") if rating else "",
        reviews_str=f'{n} {plural(n, "отзыв", "отзыва", "отзывов")}',
        reviews_dat=f'{n} {plural(n, "отзыву", "отзывам", "отзывам")}',
        has_map=has_map, cam_icon=CAM_ICON)
    (out / "index.html").write_text(html, encoding="utf-8")
    real = sum(1 for g in gallery if not g.get("empty"))
    print(f"{cid}: {out / 'index.html'} ({var}, фото работ {real}/{GALLERY_SIZE})")

def main():
    companies = {c["id"]: c for c in json.loads((ROOT / "companies.json").read_text(encoding="utf-8"))}
    ids = sys.argv[1:] or sorted(p.stem for p in (HERE / "data").glob("*.json"))
    env = Environment(loader=FileSystemLoader(HERE), autoescape=True)
    for cid in ids:
        build(cid, companies, env)

if __name__ == "__main__":
    main()

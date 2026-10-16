"""Собирает лендинги из companies.json, data/<id>.json и template.html.j2.

Запуск: python3 build.py [id ...]   (без аргументов собирает все фирмы, у которых есть data/<id>.json)
Результат: ../out/<id>/index.html и ../out/<id>/img/*.jpg
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

# ---------- тексты по рубрике ----------

STEPS_FURNITURE = [
    ("Заявка", "Оставляете заявку на сайте или пишете в WhatsApp."),
    ("Замер", "Приезжаем и бесплатно делаем замер."),
    ("Проект и цена", "Показываем 3D-проект и называем точную стоимость."),
    ("Изготовление и установка", "Изготавливаем мебель и устанавливаем у вас дома."),
]
STEPS_TABLES = [
    ("Заявка", "Оставляете заявку на сайте или пишете в WhatsApp."),
    ("Подбор", "Подбираем стол и стулья под размер кухни и интерьер."),
    ("Цена", "Называем стоимость и сроки."),
    ("Доставка и сборка", "Привозим и собираем у вас дома."),
]
SUB_FURNITURE = "Бесплатно приедем на замер и сделаем 3D‑проект: увидите мебель в своей комнате до изготовления."

TEXTS = {
    "Мебель на заказ": dict(
        eyebrow="Мебель на заказ · Краснодар", h1="Кухни и шкафы по вашим размерам",
        works_h="Кухни, шкафы и гардеробные, которые мы сделали", foot="мебель на заказ в Краснодаре"),
    "Мебель для кухни": dict(
        eyebrow="Кухни на заказ · Краснодар", h1="Кухня точно под размеры вашей квартиры",
        works_h="Кухни, которые мы сделали", foot="кухни на заказ в Краснодаре"),
    "Корпусная мебель": dict(
        eyebrow="Корпусная мебель · Краснодар", h1="Шкафы, кухни и гардеробные под ваши размеры",
        works_h="Шкафы, кухни и гардеробные, которые мы сделали", foot="корпусная мебель в Краснодаре"),
    "Мебельные магазины": dict(
        eyebrow="Мебель на заказ · Краснодар", h1="Шкафы, кухни и гардеробные под ваши размеры",
        works_h="Шкафы, кухни и гардеробные, которые мы сделали", foot="мебель на заказ в Краснодаре"),
    "Детская мебель": dict(
        eyebrow="Детская мебель · Краснодар", h1="Детская комната, где у каждой вещи своё место",
        works_h="Детские комнаты и мебель, которые мы сделали", foot="детская мебель в Краснодаре"),
    "Мягкая мебель": dict(
        eyebrow="Мягкая мебель · Краснодар", h1="Диваны и кресла под ваш размер и ткань",
        works_h="Диваны и кресла, которые мы сделали", foot="мягкая мебель в Краснодаре",
        sub="Подберём размер, механизм и ткань под вашу комнату. Покажем образцы тканей.",
        steps=[("Заявка", "Оставляете заявку на сайте или пишете в WhatsApp."),
               ("Подбор", "Подбираем размер, механизм и ткань."),
               ("Цена", "Называем точную стоимость и сроки."),
               ("Изготовление и доставка", "Изготавливаем и привозим к вам домой.")],
        price_unit="за диван", steps_h="Четыре шага от заявки до доставки"),
}
TEXTS_TABLES = dict(
    eyebrow="Столы и стулья · Краснодар", h1="Обеденные столы и стулья для вашей кухни",
    works_h="Столы и стулья в нашем шоуруме", foot="столы и стулья в Краснодаре",
    sub="Поможем подобрать стол под размер кухни и стулья к нему. Приезжайте в шоурум посмотреть вживую.",
    steps=STEPS_TABLES, price_unit="за стол", steps_h="Четыре шага от заявки до доставки")

# ---------- квизы ----------

def ico(body):
    return f'<svg viewBox="0 0 44 32" fill="currentColor" aria-hidden="true">{body}</svg>'

QUIZZES = {
    "kitchen": dict(h="Рассчитаем стоимость кухни", pre=2, steps=[
        dict(q="Какая планировка кухни?", opts=[
            dict(t="Прямая", d="вдоль одной стены", icon=ico('<rect x="4" y="5" width="36" height="7" rx="2"/>')),
            dict(t="Угловая", d="Г-образная, самая частая", icon=ico('<rect x="4" y="5" width="36" height="7" rx="2"/><rect x="4" y="5" width="7" height="24" rx="2"/>')),
            dict(t="П-образная", d="вдоль трёх стен", icon=ico('<rect x="4" y="5" width="36" height="7" rx="2"/><rect x="4" y="5" width="7" height="24" rx="2"/><rect x="33" y="5" width="7" height="24" rx="2"/>')),
            dict(t="С островом", d="рабочая зона в центре", icon=ico('<rect x="4" y="5" width="36" height="7" rx="2"/><rect x="4" y="5" width="7" height="24" rx="2"/><rect x="18" y="20" width="16" height="8" rx="2"/>')),
        ]),
        dict(q="Какая длина по стенам?", opts=[
            dict(t="До 2 м", d="небольшая кухня"), dict(t="2-3 м", d="стандартная"),
            dict(t="3-4 м", d="просторная"), dict(t="Больше 4 м", d="кухня-гостиная")]),
        dict(q="Какие фасады нравятся?", opts=[
            dict(t="Плёнка МДФ", d="практично и недорого"), dict(t="Эмаль", d="матовая или глянец"),
            dict(t="Пластик", d="стойкий к царапинам"), dict(t="Пока не знаю", d="подскажем на замере")]),
        dict(q="Когда нужна кухня?", opts=[
            dict(t="Как можно скорее", d=""), dict(t="В течение месяца", d=""),
            dict(t="Через 1-3 месяца", d=""), dict(t="Пока присматриваюсь", d="")]),
    ]),
    "kids": dict(h="Рассчитаем стоимость детской", pre=4, steps=[
        dict(q="Что нужно в детскую?", opts=[
            dict(t="Кровать", d="обычная или чердак"), dict(t="Шкаф", d="для одежды и игрушек"),
            dict(t="Рабочее место", d="стол и полки"), dict(t="Комната целиком", d="всё вместе")]),
        dict(q="Сколько детей в комнате?", opts=[
            dict(t="Один", d=""), dict(t="Двое", d="двухъярусная или две кровати"),
            dict(t="Трое и больше", d=""), dict(t="Пока не знаю", d="")]),
        dict(q="Сколько лет ребёнку?", opts=[
            dict(t="До 3 лет", d=""), dict(t="3-7 лет", d=""), dict(t="7-12 лет", d=""), dict(t="Подросток", d="")]),
        dict(q="Когда нужна мебель?", opts=[
            dict(t="Как можно скорее", d=""), dict(t="В течение месяца", d=""),
            dict(t="Через 1-3 месяца", d=""), dict(t="Пока присматриваюсь", d="")]),
    ]),
    "soft": dict(h="Рассчитаем стоимость дивана", pre=2, steps=[
        dict(q="Какой диван нужен?", opts=[
            dict(t="Прямой", d="классический"), dict(t="Угловой", d="больше места"),
            dict(t="Модульный", d="собирается как нужно"), dict(t="Кресло", d="к дивану или отдельно")]),
        dict(q="Нужно спальное место?", opts=[
            dict(t="Да, каждый день", d="надёжный механизм"), dict(t="Иногда, для гостей", d=""),
            dict(t="Нет", d="только сидеть"), dict(t="Пока не знаю", d="")]),
        dict(q="Какая обивка нравится?", opts=[
            dict(t="Велюр", d="мягкий на ощупь"), dict(t="Рогожка", d="плотная и практичная"),
            dict(t="Антикоготь", d="если есть животные"), dict(t="Пока не знаю", d="покажем образцы")]),
        dict(q="Когда нужен диван?", opts=[
            dict(t="Как можно скорее", d=""), dict(t="В течение месяца", d=""),
            dict(t="Через 1-3 месяца", d=""), dict(t="Пока присматриваюсь", d="")]),
    ]),
    "tables": dict(h="Подберём стол за 1 минуту", pre=2, steps=[
        dict(q="Сколько человек за столом?", opts=[
            dict(t="2-4", d="небольшая кухня"), dict(t="4-6", d="семья"),
            dict(t="6-8", d="с гостями"), dict(t="Больше 8", d="большая гостиная")]),
        dict(q="Нужен раскладной стол?", opts=[
            dict(t="Да", d="раскладываем для гостей"), dict(t="Нет", d="всегда одного размера"),
            dict(t="Пока не знаю", d=""), dict(t="Покажите оба варианта", d="")]),
        dict(q="Какая столешница нравится?", opts=[
            dict(t="Керамика", d="под мрамор или камень"), dict(t="Стекло", d=""),
            dict(t="Дерево", d=""), dict(t="Пока не знаю", d="покажем в шоуруме")]),
        dict(q="Нужны стулья?", opts=[
            dict(t="Да, к столу", d="подберём в комплект"), dict(t="Только стол", d=""),
            dict(t="Только стулья", d=""), dict(t="Пока не знаю", d="")]),
    ]),
}

def variant_for(c, d):
    if d.get("variant") and d["variant"] != "auto":
        return d["variant"]
    return {"Детская мебель": "kids", "Мягкая мебель": "soft"}.get(c["rubric"], "kitchen")

# ---------- иконки ----------

WA_ICON = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.8 11.9 11.9 0 0 0 4.6 4c1.7.7 2.4.8 3.2.7.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.3-.2-.6-.3Z"/></svg>'
TG_ICON = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.4 4.2 2.9 11.3c-1.3.5-1.2 1.2-.2 1.5l4.7 1.5 1.8 5.6c.2.6.4.8.8.8s.6-.2.9-.5l2.3-2.2 4.8 3.5c.9.5 1.5.2 1.7-.8l3.1-14.7c.3-1.3-.5-1.9-1.4-1.6ZM9.6 14.3l-.4 3.8-1.4-4.4 10.4-6.6-8.6 7.2Z"/></svg>'
CAM_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M4 8h3l1.5-2h7L17 8h3v11H4z" stroke-linejoin="round"/><circle cx="12" cy="13" r="3.5"/></svg>'

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

def save_photo(url, dst, max_w=1600):
    if dst.exists():
        return
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(fetch(url)))).convert("RGB")
    im = im.crop((0, 0, im.width, int(im.height * (1 - WATERMARK_CROP))))
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    im.save(dst, quality=84, optimize=True)

def save_map(point, dst):
    if dst.exists():
        return True
    lon, lat = point["lon"], point["lat"]
    url = f"https://static.maps.2gis.com/1.0?zoom=16&size=1200,840&markers={lon},{lat}"
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

def rating_text(r):
    return f"{r:.1f}".replace(".", ",")

# ---------- сборка ----------

def build(cid, companies, env):
    c = dict(companies[cid])
    d = json.loads((HERE / "data" / f"{cid}.json").read_text(encoding="utf-8"))
    out = OUT / cid
    (out / "img").mkdir(parents=True, exist_ok=True)

    var = variant_for(c, d)
    t = dict(TEXTS_TABLES if var == "tables" else TEXTS.get(c["rubric"], TEXTS["Мебель на заказ"]))
    t.setdefault("sub", SUB_FURNITURE)
    t.setdefault("steps", STEPS_FURNITURE)
    t.setdefault("price_unit", "за погонный метр")
    t.setdefault("steps_h", "Четыре шага от заявки до установки")
    t.update(d.get("texts", {}))
    t["title"] = t["eyebrow"].split(" · ")[0].lower()

    if d.get("hero"):
        save_photo(d["hero"]["src"], out / "img" / "hero.jpg")
    gallery = []
    for i, g in enumerate(d.get("gallery", [])[:GALLERY_SIZE], 1):
        save_photo(g["src"], out / "img" / f"w{i}.jpg", max_w=1200)
        gallery.append(g)
    while len(gallery) < GALLERY_SIZE:
        gallery.append({"empty": True})
    has_map = bool(d.get("point")) and save_map(d["point"], out / "img" / "map.png")

    c["phone_raw"] = "+" + re.sub(r"\D", "", c["phone"])
    c["wa_num"] = re.sub(r"\D", "", c["wa"])
    rating = c.get("rating")
    quiz = dict(QUIZZES[var])
    quiz["n"] = len(quiz["steps"])

    html = env.get_template("template.html.j2").render(
        c=c, d=d, t=t, gallery=gallery, quiz=quiz, quiz_json=json.dumps(quiz, ensure_ascii=False),
        show_rating=rating is not None and rating >= 4.6,
        rating_str=rating_text(rating) if rating else "",
        reviews_str=f'{c["reviews"]} {plural(c["reviews"], "отзыв", "отзыва", "отзывов")}',
        has_map=has_map, wa_icon=WA_ICON, tg_icon=TG_ICON, cam_icon=CAM_ICON)
    (out / "index.html").write_text(html, encoding="utf-8")
    print(f"{cid}: {out / 'index.html'} ({var}, фото {sum(1 for g in gallery if not g.get('empty'))}/{GALLERY_SIZE})")

def main():
    companies = {c["id"]: c for c in json.loads((ROOT / "companies.json").read_text(encoding="utf-8"))}
    ids = sys.argv[1:] or sorted(p.stem for p in (HERE / "data").glob("*.json"))
    env = Environment(loader=FileSystemLoader(HERE), autoescape=True)
    for cid in ids:
        build(cid, companies, env)

if __name__ == "__main__":
    main()

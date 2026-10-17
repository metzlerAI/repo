"""Проверка, точно ли у фирм из базы 2ГИС нет сайта. Работает с CSV из шага 8 (разделитель ;, BOM).

Режимы:
  check <csv>                 автоматика по всем строкам: короткие ссылки, домен почты, подбор домена по никам
  todo <csv>                  строки без итога, по одной на фирму: id|название|город|телефон (для веб-поиска)
  url <csv> <id> <ссылка>     проверить сайт, найденный поиском: удалён / заглушка / совпал телефон / чужой
  set <csv> <id> <текст>      записать итог вручную
  final <csv>                 у пустых ставит «сайт не найден», фирмы с сайтом выносит в <csv>-есть-сайт.csv

Итог пишется в колонку «проверка сайта». «есть сайт» ставится только при совпадении телефона или почты
из карточки, остальное помечается «под вопросом» и решается глазами.
Опыт 17.10.2026 (мебель, 38 фирм A по России, факт по выборке): у 7 из 38 сайт был, хотя 2ГИС его не показывал.
3 нашёл подбор домена, 4 только веб-поиск. Ещё у 7 сайт когда-то был, но домен удалён или стоит заглушка.
"""
import concurrent.futures as cf
import csv
import re
import socket
import subprocess
import sys
from pathlib import Path

COL = 'проверка сайта'
PUBLIC_MAIL = re.compile(r'@(mail|bk|list|inbox|internet|yandex|ya|gmail|rambler|icloud|me|outlook|hotmail|ro)\.(ru|com|ua|by|kz)$', re.I)
SHORT = re.compile(r'https?://(clck\.ru|bit\.ly|vk\.cc|goo\.su|tinyurl\.com|cutt\.ly)/', re.I)
SOC = re.compile(r'(2gis|t\.me|wa\.me|whatsapp|vk\.(com|ru)|vk\.cc|max\.ru|taplink|instagram|youtube|ok\.ru|avito|dzen|rutube|tiktok|mssg\.me|clck\.ru|orgs\.biz|yandex)', re.I)
HANDLE = re.compile(r'(?:vk\.com|vk\.ru|t\.me|taplink\.cc|ok\.ru|instagram\.com|youtube\.com/@?)/([A-Za-z0-9_.-]+)/?$')
SKIP = {'club', 'public', 'profile', 'join', 'u', 'channel', 'group', 's'}
TLDS = ('ru', 'com', 'online', 'pro', 'site')
PARKED = re.compile(r'reg\.ru|nic\.ru|parking|домен[^<]{0,40}(прода|зарегистр|припарк)|domain[^<]{0,40}(sale|regist|park)', re.I)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0 Safari/537.36'


def load(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f, delimiter=';'))
    for r in rows:
        r.setdefault(COL, '')
        r[COL] = r[COL] or ''
    return rows


def save(p, rows):
    if not rows:
        return
    keys = list(rows[0].keys())
    if COL in keys:
        keys.remove(COL)
    keys.append(COL)
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys, delimiter=';')
        w.writeheader()
        w.writerows(rows)


def phones(r):
    """Последние 7 цифр всех телефонов фирмы. В колонке «телефоны» номера только цифрами через пробел."""
    nums = (r.get('телефоны') or '').split()
    nums += [re.sub(r'\D', '', x) for x in re.findall(r'\+?\d[\d\s()‒-]{8,}\d', r.get('телефон') or '')]
    nums += re.findall(r'\d{10,}', r.get('whatsapp') or '')
    return {n[-7:] for n in nums if len(n) >= 7}


def mails(r):
    return {m.lower() for m in re.findall(r'[\w.+-]+@[\w.-]+\.\w+', r.get('почта') or '')}


def links(r):
    return re.findall(r'https?://\S+', ' '.join(r.get(k) or '' for k in ('ники', 'url', 'telegram', 'vk')))


def fetch(url):
    """Текст страницы и адрес после редиректов. Через curl: он есть везде и сам берёт системный прокси."""
    out = subprocess.run(['curl', '-sSL', '-m', '15', '-A', UA, '-w', '\n__URL__%{url_effective}', url], capture_output=True)
    t = out.stdout.decode('utf-8', 'ignore')
    body, _, eff = t.rpartition('\n__URL__')
    return body, eff.strip()


def dns_ok(dom):
    """True, если домен существует. Если местный DNS не ответил, перепроверяем через Google DNS:
    удалённым домен считаем только по его ответу NXDOMAIN (Status 3)."""
    d = dom.encode('idna').decode()
    try:
        socket.gethostbyname(d)
        return True
    except Exception:
        pass
    out = subprocess.run(['curl', '-sS', '-m', '10', f'https://dns.google/resolve?name={d}&type=A'], capture_output=True)
    m = re.search(rb'"Status":\s*(\d+)', out.stdout)
    return not (m and m[1] == b'3')


def verify(r, url):
    """Возвращает (итог, подробность). Итог: есть сайт / удалён / заглушка / под вопросом / чужой / не открылся."""
    dom = re.sub(r'^https?://', '', url).split('/')[0].lower()
    if not dns_ok(dom):
        return 'удалён', dom
    base = 'https://' + dom
    pages = [url, base, base + '/contacts', base + '/kontakty', base + '/contact']
    ph, ml, html_all, title = phones(r), mails(r), '', ''
    for u in dict.fromkeys(pages):
        body, _ = fetch(u)
        if not body and u.startswith('https://'):
            body, _ = fetch('http://' + u[8:])
        if not title:
            m = re.search(r'<title[^>]*>([^<]{0,90})', body, re.I)
            title = m[1].strip() if m else ''
        html_all += body
        digits = re.sub(r'\D', '', html_all)
        hit = sorted({p for p in ph if p in digits} | {m for m in ml if m in html_all.lower()})
        if hit:
            return 'есть сайт', f'{dom} (совпало: {", ".join(hit)})'
    if len(html_all) < 300:
        return 'не открылся', dom
    if title.lower() in (dom, 'www.' + dom) or (len(html_all) < 40000 and PARKED.search(html_all)):
        return 'заглушка', dom
    name = re.split(r'[,«»"]', r.get('название') or '')[0].strip().lower()
    cnt = html_all.lower().count(name) if len(name) >= 4 else 0
    if cnt >= 3:
        return 'под вопросом', f'{dom}: название «{name}» на сайте {cnt} раз, телефон другой | {title[:60]}'
    return 'чужой', f'{dom} | {title[:60]}'


def guesses(r):
    hs = set()
    for m in mails(r):
        loc = m.split('@')[0]
        hs |= {re.sub(r'[^a-z0-9]', '', loc), re.sub(r'[^a-z0-9-]', '', loc.replace('.', '-').replace('_', '-'))}
    for u in links(r):
        m = HANDLE.search(u.split('?')[0])
        if m and m[1].lower() not in SKIP and not m[1].startswith('+'):
            h = m[1].lower()
            hs |= {h.replace('_', '-'), h.replace('_', ''), h.replace('.', '-'), h.replace('.', '')}
    return [h + '.' + t for h in hs if len(h) >= 4 and not h.isdigit() for t in TLDS]


def check_row(r):
    # 1. Короткие ссылки (clck.ru и т.п.) в карточке: куда ведут
    for u in links(r):
        if SHORT.match(u):
            _, eff = fetch(u)
            if eff and not SOC.search(eff.split('?')[0]):
                st, d = verify(r, eff)
                if st == 'удалён':
                    return f'сайт был, домен удалён: {d} (по короткой ссылке)'
                return f'есть сайт: {eff.split("?")[0]} (короткая ссылка из карточки ведёт сюда)'
    # 2. Почта на своём домене
    for m in mails(r):
        if not PUBLIC_MAIL.search(m):
            st, d = verify(r, 'https://' + m.split('@')[1])
            if st in ('есть сайт', 'под вопросом', 'заглушка', 'удалён'):
                return f'{st}: {d} (домен почты)'
    # 3. Подбор домена по никам: засчитываем только совпадение телефона или почты
    for dom in guesses(r):
        if dns_ok(dom):
            st, d = verify(r, 'https://' + dom)
            if st == 'есть сайт':
                return f'{st}: {d} (подбор домена)'
    return ''


def main():
    mode, p = sys.argv[1], Path(sys.argv[2])
    rows = load(p)
    by = {r['id']: r for r in rows}
    if mode == 'check':
        todo = [r for r in rows if not r[COL] and r.get('сайт', r.get('сайт(нет/соц/есть)', '')) != 'есть']
        with cf.ThreadPoolExecutor(12) as ex:
            res = list(ex.map(check_row, todo))
        for r, s in zip(todo, res):
            r[COL] = s
        save(p, rows)
        found = [s for s in res if s]
        print(f'проверено {len(todo)}, найдено автоматически {len(found)}, на веб-поиск {len(todo) - len(found)}')
        for r, s in zip(todo, res):
            if s:
                print(r['id'], '|', r['название'][:30], '|', s)
    elif mode == 'todo':
        for r in rows:
            if not r[COL]:
                print(r['id'], '|', r['название'], '|', r['город'], '|', r['телефон'])
    elif mode == 'url':
        r = by[sys.argv[3]]
        st, d = verify(r, sys.argv[4])
        labels = {'удалён': 'сайт был, домен удалён', 'заглушка': 'на домене заглушка, сайта нет'}
        if st in ('есть сайт', 'под вопросом', 'удалён', 'заглушка'):
            r[COL] = f'{labels.get(st, st)}: {d}'
            save(p, rows)
        print(st, '|', d)
    elif mode == 'set':
        by[sys.argv[3]][COL] = sys.argv[4]
        save(p, rows)
        print('ok')
    elif mode == 'final':
        for r in rows:
            r[COL] = r[COL] or 'сайт не найден (карточка, почта, подбор домена, веб-поиск)'
        has = [r for r in rows if r[COL].startswith('есть сайт')]
        keep = [r for r in rows if r not in has]
        save(p, keep)
        if has:
            save(p.with_name(p.stem + '-есть-сайт.csv'), has)
        q = sum(r[COL].startswith('под вопросом') for r in keep)
        dead = sum(r[COL].startswith(('сайт был', 'на домене заглушка')) for r in keep)
        print(f'в базе {len(keep)}, убрано с сайтом {len(has)}, под вопросом {q}, сайт умер или заглушка {dead}')


if __name__ == '__main__':
    main()

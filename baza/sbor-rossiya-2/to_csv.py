# Строки 16-50 листа «база 50» из baza-rossiya.xlsx в CSV формата скилла sbor-bazy-2gis (шаг 7) для proverka_saita.py.
# Почту, все телефоны и ники берёт из карточки 2ГИС (contact_groups в HTML страницы фирмы).
# Запуск из корня репозитория: python3 baza/sbor-rossiya-2/to_csv.py  →  a.csv (строки 16-32) и b.csv (33-50)
import concurrent.futures as cf
import csv
import json
import re
import subprocess
from pathlib import Path

import openpyxl

HERE = Path(__file__).parent
SKIP = {47}  # Smeg: магазин бытовой техники
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'
HEAD = 'приоритет;зона;город;название;рубрика;отзывов;рейтинг;сайт;url;telegram;whatsapp;vk;телефон;адрес;запрос стр;id;почта;телефоны;ники;проверка сайта;№'.split(';')


def balanced(text, at):
    depth, s = 0, False
    for i in range(at, len(text)):
        ch = text[i]
        if s:
            if ch == '\\':
                continue
            if ch == '"' and text[i - 1] != '\\':
                s = False
            continue
        if ch == '"':
            s = True
        elif ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                return text[at:i + 1]


def contacts(card):
    html = subprocess.run(['curl', '-sSL', '-m', '30', '-A', UA, card], capture_output=True).stdout.decode('utf-8', 'ignore')
    at = html.find('"contact_groups":[')
    if at < 0:
        return None
    groups = json.loads(balanced(html, at + len('"contact_groups":')))
    cs = [c for g in groups for c in g.get('contacts', [])]
    mail = ' '.join(c['value'] for c in cs if c['type'] == 'email')
    tel = ' '.join(re.sub(r'\D', '', c['value']) for c in cs if c['type'] == 'phone')
    nick = ' '.join((c.get('url') or c['value']).split('?', 1)[-1] if 'link.2gis.ru' in (c.get('url') or '') else (c.get('url') or c['value'])
                    for c in cs if c['type'] not in ('phone', 'email'))
    vk = ' '.join(c.get('print_text') or c['value'] for c in cs if c['type'] == 'vkontakte')
    return mail, tel, nick, vk


def main():
    ws = openpyxl.load_workbook('baza-rossiya.xlsx')['база 50']
    rows = list(ws.iter_rows(values_only=True))
    todo = [(i, rows[i]) for i in range(16, 51) if i not in SKIP]
    with cf.ThreadPoolExecutor(4) as ex:
        got = list(ex.map(lambda t: contacts(t[1][12]), todo))
    out = {'a': [], 'b': []}
    for (i, r), c in zip(todo, got):
        if c is None:
            print('нет контактов в карточке:', i, r[2])
            c = ('', '', '', '')
        mail, tel, nick, vk = c
        site = r[7] or 'нет'
        d = dict(zip(HEAD, [r[0], '', r[1], r[2], r[3], r[4], r[5], 'нет' if site == 'нет' else 'соц',
                            re.findall(r'https?://[^)\s]+', site)[0] if 'http' in site else '', r[8] or '', r[9] or '', vk,
                            r[10], r[11] or '', '', r[12].rsplit('/', 1)[1], mail, tel, nick, '', i]))
        out['a' if i <= 32 else 'b'].append(d)
    for k, rs in out.items():
        with open(HERE / f'{k}.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=HEAD, delimiter=';')
            w.writeheader()
            w.writerows(rs)
        print(k, len(rs), 'строк')


if __name__ == '__main__':
    main()

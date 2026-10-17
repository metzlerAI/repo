# ver.py <id-хвост> <url> ...: есть ли на странице сайта любой телефон или почта из карточки 2ГИС
import json, re, subprocess, sys
deep = {x['id'][-6:]: x for x in json.load(open('deep.json'))}
args = sys.argv[1:]
for k, url in zip(args[::2], args[1::2]):
    cs = deep[k]['cs']
    phones = {re.sub(r'\D', '', c)[-7:] for c in cs if c.startswith(('phone:', 'whatsapp:'))}
    mails = {c.split(':', 1)[1].lower() for c in cs if c.startswith('email:')}
    pages = [url] + [url.rstrip('/') + p for p in ('/contacts', '/contact', '/kontakty')]
    hit = set(); title = ''
    for u in pages:
        h = subprocess.run(['curl', '-sSL', '-m', '15', '-A', 'Mozilla/5.0', u], capture_output=True).stdout.decode('utf8', 'ignore')
        if not title: title = (re.search(r'<title[^>]*>([^<]{0,60})', h, re.I) or [None, ''])[1].strip()
        d = re.sub(r'\D', '', h)
        hit |= {p for p in phones if p in d} | {m for m in mails if m in h.lower()}
    print(k, url, '| совпало:', sorted(hit) or 'НЕТ', '|', title)

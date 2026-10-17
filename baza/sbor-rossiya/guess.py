# подбор доменов по никам фирмы (VK, Telegram, Taplink, почта) и проверка: открывается ли сайт и есть ли на нём телефон фирмы
import json, re, socket, subprocess, concurrent.futures as cf
deep = {x['id']: x for x in json.load(open('deep.json'))}
cards = json.load(open('cards.json'))
A = json.load(open('a_ids.json'))
SKIP = {'club', 'public', 'profile', 'join', 'u', 'channel'}
def handles(x):
    hs = set()
    for c in deep[x['id']]['cs'] + [cards[x['id']]['site']]:
        v = c.split(':', 1)[1] if ':' in c and not c.startswith('http') else c
        if c.startswith('email:'):
            hs.add(re.sub(r'[^a-z0-9-]', '', v.split('@')[0].lower().replace('.', '-'))); hs.add(re.sub(r'[^a-z0-9]', '', v.split('@')[0].lower()))
        m = re.search(r'(?:vk\.com|t\.me|taplink\.cc|ok\.ru|youtube\.com/@)/?([A-Za-z0-9_.-]+)$', v)
        if m and m[1].lower() not in SKIP and not m[1].startswith('+'):
            h = m[1].lower(); hs |= {h.replace('_', '-'), h.replace('_', ''), h.replace('.', '-'), h.replace('.', '')}
    return {h for h in hs if len(h) >= 4 and not h.isdigit()}
def digits(s): return re.sub(r'\D', '', s)[-7:]
def check(dom, ph):
    try: socket.gethostbyname(dom)
    except Exception: return None
    r = subprocess.run(['curl', '-sSL', '-m', '15', '-A', 'Mozilla/5.0', 'https://' + dom], capture_output=True)
    html = r.stdout.decode('utf8', 'ignore')
    if len(html) < 500: return None
    d = re.sub(r'\D', '', html)
    return {'dom': dom, 'phone_match': bool(ph and ph in d), 'title': (re.search(r'<title[^>]*>([^<]{0,80})', html, re.I) or [None, ''])[1].strip()}
jobs = []
for x in A:
    ph = digits(cards[x['id']]['ph'])
    for h in handles(x):
        for tld in ('ru', 'com', 'online', 'pro', 'site'):
            jobs.append((x, h + '.' + tld, ph))
print('доменов к проверке', len(jobs))
with cf.ThreadPoolExecutor(24) as ex:
    res = list(ex.map(lambda j: (j[0], check(j[1], j[2])), jobs))
for x, r in res:
    if r: print(x['n'].split(',')[0][:20], '|', r['dom'], '| тел' if r['phone_match'] else '| -', '|', r['title'][:60])

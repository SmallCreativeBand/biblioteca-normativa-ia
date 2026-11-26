#!/usr/bin/env python3
"""Rutina semanal de novedades: versión automática de prompt_rutina_semanal.md.

Revisa las fuentes oficiales del prompt durante los 7 días anteriores (incluido el día
de la fecha), compara lo encontrado con biblioteca.xlsx y escribe novedades/AAAA-MM-DD.md
con el mismo formato que los informes hechos a mano. No descarga documentos, no mueve
archivos y no toca biblioteca.xlsx: solo propone.

Uso:
    python3 herramientas/rutina_semanal.py                 # fecha de hoy (hora de Madrid)
    python3 herramientas/rutina_semanal.py --fecha 2026-11-30
    python3 herramientas/rutina_semanal.py --salida /tmp/prueba.md   # no escribe en novedades/

Solo usa la biblioteca estándar de Python 3.9+. En GitHub Actions, si existe la variable
GITHUB_OUTPUT, deja en ella la ruta del informe, si hay algo que avisar y un título.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import generar_biblioteca_html as gen  # noqa: E402  (lector de biblioteca.xlsx e informes)

MADRID = ZoneInfo('Europe/Madrid')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
MESES_EN = {m: i for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                                         'September', 'October', 'November', 'December'], start=1)}

FUERTE_ES = re.compile(r'(?i:inteligencia artificial|2024/1689)|\bIA\b')  # «IA» solo en mayúsculas
DEBIL_ES = re.compile(r'algoritm|automatizad', re.I)
FUERTE_EN = re.compile(r'(?i:artificial intelligence)|\bAI\b|\bGPAI\b')  # «AI» solo en mayúsculas
BLOQUEO = re.compile(r'plan de estudios|m[aá]ster universitario|\bgrado en\b', re.I)
TEMAS = [
    (r'datos personales|protecci[oó]n de datos|RGPD|privacidad|GDPR|personal data', 'protección de datos y decisiones automatizadas'),
    (r'agente|ag[eé]ntica|agentic', 'agentes de IA'),
    (r'transparencia|etiquetad|deepfake|ultrafals|contenido generado|labelling|transparency', 'transparencia y contenido generado'),
    (r'uso general|GPAI|general-purpose|modelos fundacionales', 'IA de uso general (GPAI)'),
    (r'alto riesgo|high-risk', 'alto riesgo'),
    (r'prohibid|prohibited', 'prácticas prohibidas'),
    (r'sandbox|espacios? controlados? de pruebas|gobernanza|supervisi[oó]n|autoridad|governance|enforcement', 'gobernanza y supervisión'),
    (r'formaci[oó]n|alfabetizaci[oó]n|literacy|skills', 'alfabetización y formación'),
    (r'derechos de autor|propiedad intelectual|copyright', 'propiedad intelectual'),
    (r'administraci[oó]n|sector p[uú]blico|public sector', 'sector público'),
    (r'consumidor|responsabilidad civil|liability|consumer', 'responsabilidad y consumidores'),
    (r'definici[oó]n|definition', 'definiciones y ámbito'),
]
STOP = set('para como sobre entre desde hasta donde cuando porque inteligencia referencia consejo ministros '
           'contra asunto sentencia'.split())


# ---------------------------------------------------------------- utilidades
def norm(s):
    s = unicodedata.normalize('NFD', str(s or ''))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower()


def limpio(s, n=None):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', str(s or '')))
    s = re.sub(r'\s+', ' ', s).strip()
    return (s[:n - 1] + '…') if n and len(s) > n else s


def celda(s):
    return limpio(s).replace('|', '/')


def descargar(url, accept=None, intentos=2):
    """Devuelve (código, cabeceras en minúsculas, texto, url final). Nunca lanza."""
    ultimo = None
    for i in range(intentos):
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                                                    **({'Accept': accept} if accept else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                cuerpo = r.read()
                cab = {k.lower(): v for k, v in r.headers.items()}
                enc = r.headers.get_content_charset() or 'utf-8'
                return r.status, cab, cuerpo.decode(enc, 'replace'), r.geturl()
        except urllib.error.HTTPError as e:
            cab = {k.lower(): v for k, v in (e.headers or {}).items()}
            return e.code, cab, (e.read() or b'').decode('utf-8', 'replace'), url
        except Exception as e:  # red, tiempo de espera, TLS…
            ultimo = e
            time.sleep(3)
    return 0, {}, '', str(ultimo)


def bloqueo_antirobots(codigo, cab, texto):
    if 'x-amzn-waf-action' in cab:
        return 'control anti-robots (AWS WAF)'
    if codigo == 403 and ('cloudflare' in cab.get('server', '').lower() or 'Attention Required' in texto):
        return 'bloqueo de Cloudflare (403)'
    return None


PUBLICA = re.compile(r'\b(publica|publican|aprueba|aprueban|presenta|lanza|suscrib\w*|firma\w*|establece|adopta|declaraci[oó]n|gu[ií]a|estudio|informe|'
                     r'orientaciones|est[aá]ndares|c[oó]digo|reglamento|acto de ejecuci[oó]n|directrices|norma)\b', re.I)


def fuerza(texto, ingles=False):
    if FUERTE_ES.search(texto) or (ingles and FUERTE_EN.search(texto)):
        nivel = 'fuerte'
    elif DEBIL_ES.search(texto):
        nivel = 'debil'
    else:
        return None
    return 'bloqueado' if BLOQUEO.search(texto) else nivel


def fuerza_nota(titulo, entradilla):
    """Notas de prensa y noticias: cuenta como documento si menciona la IA (en el título o
    la entradilla) y el título anuncia que se publica, aprueba o firma algo. Si no, es para revisar."""
    nivel = fuerza(titulo + ' ' + entradilla)
    if nivel == 'fuerte' and PUBLICA.search(titulo):
        return 'fuerte'
    return 'debil' if nivel in ('fuerte', 'debil') else None


def temas_de(texto):
    out = [t for pat, t in TEMAS if re.search(pat, texto, re.I)]
    return out or ['PENDIENTE']


def tipo_de(titulo, por_defecto='PENDIENTE'):
    t = norm(titulo)
    if re.match(r'(reglamento|directiva|decision|ley|real decreto|decreto|orden|regulation|directive)\b', t):
        return 'norma'
    if re.match(r'(sentencia|auto |asunto|judgment)', t):
        return 'caso'
    if re.search(r'directrices|guia|codigo de (buenas )?practicas|recomendacion|guidelines|code of practice', t):
        return 'guia'
    return por_defecto


def candidato(fuente, titulo, fecha, url, resumen='', urls_doc=None, tipo=None, ingles=False):
    texto = titulo + ' ' + resumen
    return {'fuente': fuente, 'titulo': limpio(titulo), 'fecha': fecha, 'url': url, 'resumen': limpio(resumen, 260),
            'urls_doc': urls_doc or [], 'tipo': tipo or tipo_de(titulo), 'temas': temas_de(texto),
            'fuerza': fuerza(texto, ingles)}


# ---------------------------------------------------------------- fuentes
def fuente_eurlex(dias):
    vistos, ediciones, titulos, cands, desc = set(), set(), [], [], []
    for d in dias:
        for serie in ('L', 'C'):
            url = f'https://eur-lex.europa.eu/oj/daily-view/{serie}-series/default.html?locale=es&ojDate={d:%d%m%Y}'
            cod, cab, txt, _ = descargar(url)
            motivo = bloqueo_antirobots(cod, cab, txt)
            if motivo or cod != 200:
                return [], [], [], f'Falla: {motivo or "HTTP " + str(cod)} al pedir la serie {serie} del {d}.', False
            m = re.search(r'name="ojDate" value="(\d{8})"', txt)
            edicion = dt.datetime.strptime(m.group(1), '%d%m%Y').date() if m else d
            if edicion < dias[0] or (serie, edicion) in ediciones:
                continue
            ediciones.add((serie, edicion))
            for href, t in re.findall(r'<a[^>]+href="([^"]*uri=OJ:[^"]+)"[^>]*>(.*?)</a>', txt, re.S):
                href = urllib.parse.urljoin(url, html.unescape(href))
                t = limpio(t)
                if href in vistos or not t:
                    continue
                vistos.add(href)
                titulos.append((t, href, edicion.isoformat()))
                c = candidato('Diario Oficial de la UE', t, edicion.isoformat(), href)
                if c['fuerza'] == 'fuerte':
                    cands.append(c)
                elif c['fuerza'] in ('debil', 'bloqueado'):
                    desc.append((c, 'solo coincide con «algoritm» o «automatizad» en el título; no parece regular la IA (revísalo)'))
            time.sleep(1)
    n_ed = len({e for _, e in ediciones})
    return cands, desc, titulos, f'Correcto. {len(vistos)} actos distintos en {n_ed} ediciones (series L y C); {len(cands)} sobre IA en el título.', True


def fuente_comision(dias):
    url = 'https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai'
    cod, cab, txt, _ = descargar(url)
    motivo = bloqueo_antirobots(cod, cab, txt)
    if motivo or cod != 200:
        return [], [], f'Falla: {motivo or "HTTP " + str(cod)}.', False
    m = re.search(r'Last update[\s\S]{0,300}?(\d{1,2}) (' + '|'.join(MESES_EN) + r') (\d{4})', txt)
    ultima = dt.date(int(m.group(3)), MESES_EN[m.group(2)], int(m.group(1))).isoformat() if m else 'desconocida'
    cands, desc, n_periodo = [], [], 0
    for art in re.findall(r'<article\s+class="ecl-content-item[\s\S]*?</article>', txt):
        f = re.search(r'>\s*(\d{1,2}) (' + '|'.join(MESES_EN) + r') (\d{4})\s*<', art)
        a = re.search(r'<a\s[^>]*href="([^"]+)"[^>]*>\s*<span>([\s\S]*?)</span>', art)
        if not f or not a:
            continue
        fecha = dt.date(int(f.group(3)), MESES_EN[f.group(2)], int(f.group(1)))
        if not (dias[0] <= fecha <= dias[-1]):
            continue
        n_periodo += 1
        c = candidato('Comisión Europea', a.group(2), fecha.isoformat(), urllib.parse.urljoin(url, html.unescape(a.group(1))), ingles=True)
        if c['fuerza'] == 'fuerte':
            cands.append(c)
        else:
            desc.append((c, 'noticia de la Comisión que no trata de IA (por el título)'))
    return cands, desc, f'Correcto. Última actualización: {ultima}. {n_periodo} noticia(s) en el periodo; {len(cands)} sobre IA.', True


def guias_aesia_conocidas():
    conocidas = set()
    for carpeta in ('guias', 'descargas'):
        ruta = os.path.join(RAIZ, carpeta)
        if os.path.isdir(ruta):
            for f in os.listdir(ruta):
                if 'aesia' in f and f.endswith('.md'):
                    conocidas |= set(re.findall(r'https://aesia\.digital\.gob\.es/storage/media/[^\s)]+\.pdf', open(os.path.join(ruta, f), encoding='utf-8').read()))
    return conocidas


def fuente_aesia(dias):
    resultados, cands, desc, ok = [], [], [], True
    url = 'https://aesia.digital.gob.es/es/guias'
    cod, cab, txt, _ = descargar(url)
    if bloqueo_antirobots(cod, cab, txt) or cod != 200:
        resultados.append(('AESIA, guías', f'Falla: HTTP {cod}.'))
        ok = False
    else:
        pdfs = set(re.findall(r'https://aesia\.digital\.gob\.es/storage/media/[^"\'\s]+\.pdf', txt))
        conocidas = guias_aesia_conocidas()
        nuevas = sorted(pdfs - conocidas) if conocidas else []
        for p in nuevas:
            nombre = os.path.basename(p)[:-4].replace('-', ' ')
            c = candidato('AESIA, guías', 'Guía AESIA: ' + nombre, 'PENDIENTE (la página no fecha las guías)', p, tipo='guia')
            c['fuerza'] = 'fuerte'
            cands.append(c)
        resultados.append(('AESIA, guías', f'Correcto. {len(pdfs)} guías en PDF; ' +
                           (f'{len(nuevas)} que no estaban en la copia de la biblioteca.' if conocidas else 'no encuentro la copia de la página en la biblioteca para comparar.')))
    url = 'https://aesia.digital.gob.es/es/actualidad'
    cod, cab, txt, _ = descargar(url)
    if bloqueo_antirobots(cod, cab, txt) or cod != 200:
        resultados.append(('AESIA, noticias', f'Falla: HTTP {cod}.'))
        ok = False
    else:
        vistos, ultima = set(), None
        for href, ymd, t in re.findall(r'<a[^>]+href="(https://aesia\.digital\.gob\.es/es/actualidad/(\d{8})-[^"]+)"[^>]*>([\s\S]*?)</a>', txt):
            if href in vistos or not limpio(t):
                continue
            vistos.add(href)
            fecha = dt.datetime.strptime(ymd, '%Y%m%d').date()
            ultima = max(ultima, fecha) if ultima else fecha
            if dias[0] <= fecha <= dias[-1]:
                c = candidato('AESIA, noticias', t, fecha.isoformat(), href)
                # Todo lo de la AESIA trata de IA: lo que importa es si publica algo o es una crónica.
                if PUBLICA.search(c['titulo']):
                    c['fuerza'] = 'fuerte'
                    cands.append(c)
                else:
                    desc.append((c, 'noticia de la AESIA que no anuncia ningún documento (crónica o evento); revísala'))
        resultados.append(('AESIA, noticias', f'Correcto. Última noticia: {ultima or "sin fecha"}; ' +
                           f'{sum(1 for c in cands if c["fuente"] == "AESIA, noticias")} en el periodo.'))
    return cands, desc, resultados, ok


def pdfs_de_nota(url):
    cod, _, txt, final = descargar(url)
    if cod != 200:
        return []
    out = []
    for h in re.findall(r'href="([^"]+\.pdf)"', txt, re.I):
        h = urllib.parse.urljoin(final, html.unescape(h))
        if h.startswith('https://') and 'aepd.es' in urllib.parse.urlparse(h).netloc and h not in out:
            out.append(h)
    return out


def fuente_aepd(dias):
    url = 'https://www.aepd.es/prensa-y-comunicacion/notas-de-prensa'
    cod, cab, txt, _ = descargar(url)
    if bloqueo_antirobots(cod, cab, txt) or cod != 200:
        return [], [], f'Falla: HTTP {cod}.', False
    cands, desc, n = [], [], 0
    for art in re.split(r'<article\s+class="node node--type-noticia', txt)[1:]:
        t = re.search(r'<h2>([\s\S]*?)</h2>', art)
        f = re.search(r'<time datetime="([^"]+)"', art)
        a = re.search(r'class="more-link"[^>]*href="([^"]+)"', art)
        e = re.search(r'field--name-entradilla[^>]*>([\s\S]*?)</div>', art)
        if not (t and f and a):
            continue
        fecha = dt.datetime.fromisoformat(f.group(1).replace('Z', '+00:00')).astimezone(MADRID).date()
        if not (dias[0] <= fecha <= dias[-1]):
            continue
        n += 1
        enlace = urllib.parse.urljoin(url, html.unescape(a.group(1)))
        c = candidato('AEPD, notas de prensa', t.group(1), fecha.isoformat(), enlace, e.group(1) if e else '', tipo='guia')
        c['fuerza'] = fuerza_nota(c['titulo'], c['resumen'])
        if c['fuerza'] == 'fuerte':
            c['urls_doc'] = pdfs_de_nota(enlace)
            cands.append(c)
        elif c['fuerza'] == 'debil':
            desc.append((c, 'menciona la IA, pero no anuncia ningún documento sobre IA (crónica o noticia); revísala'))
        else:
            desc.append((c, 'nota de la AEPD que no trata de IA'))
    return cands, desc, f'Correcto. {n} nota(s) en el periodo; {len(cands)} sobre IA.', True


def fuente_boe(dias):
    cands, desc, titulos, total, sin_boe = [], [], [], 0, []

    def recorrer(o):
        if isinstance(o, dict):
            if 'titulo' in o and 'identificador' in o:
                yield o
            for v in o.values():
                yield from recorrer(v)
        elif isinstance(o, list):
            for v in o:
                yield from recorrer(v)

    for d in dias:
        cod, cab, txt, _ = descargar(f'https://www.boe.es/datosabiertos/api/boe/sumario/{d:%Y%m%d}', accept='application/json')
        if cod == 404:
            sin_boe.append(d.isoformat())
            continue
        if cod != 200:
            return [], [], [], f'Falla: HTTP {cod} en el sumario del {d}.', False
        try:
            datos = json.loads(txt)
        except ValueError:
            return [], [], [], f'Falla: el sumario del {d} no es JSON.', False
        for o in recorrer(datos):
            total += 1
            u = o.get('url_html')
            u = u.get('texto') if isinstance(u, dict) else u
            u = u or f'https://www.boe.es/diario_boe/txt.php?id={o["identificador"]}'
            titulos.append((o['titulo'], u, d.isoformat()))
            c = candidato('BOE', o['titulo'], d.isoformat(), u)
            c['identificador'] = o['identificador']
            if c['fuerza'] == 'fuerte':
                cands.append(c)
            elif c['fuerza'] == 'bloqueado':
                desc.append((c, f'{o["identificador"]}: plan de estudios universitario; no regula el uso de la IA'))
            elif c['fuerza'] == 'debil':
                desc.append((c, f'{o["identificador"]}: solo coincide con «algoritm» o «automatizad»; no parece regular la IA (revísalo)'))
        time.sleep(1)
    extra = f' Sin BOE: {", ".join(sin_boe)}.' if sin_boe else ''
    return cands, desc, titulos, f'Correcto. {total} disposiciones; {len(cands)} sobre IA en el título.{extra}', True


def fuente_tjue():
    cod, cab, txt, final = descargar('https://curia.europa.eu/juris/recherche.jsf?language=es')
    if cod == 200 and '<app-root' in txt:
        return 'Falla: redirige a la aplicación InfoCuria, que solo carga con JavaScript. Hay que mirarlo a mano.'
    return f'Falla: HTTP {cod}. Hay que mirarlo a mano.' if cod != 200 else 'Responde, pero el script no sabe leer esta página: míralo a mano.'


# ---------------------------------------------------------------- comparación y cambios de estado
def palabras_clave(titulo):
    base = norm(titulo.split(' (')[0])
    return [w for w in re.findall(r'[a-z0-9]{5,}', base) if w not in STOP]


def menciona(doc_titulo, texto):
    claves = palabras_clave(doc_titulo)
    if len(claves) < 3:
        return False
    t = norm(texto)
    aciertos = sum(1 for w in claves if w in t)
    return aciertos >= max(3, round(len(claves) * 0.6))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--fecha', help='fecha del informe (AAAA-MM-DD); por defecto, hoy en Madrid')
    ap.add_argument('--salida', help='ruta del informe; por defecto novedades/AAAA-MM-DD.md')
    args = ap.parse_args()
    hoy = dt.date.fromisoformat(args.fecha) if args.fecha else dt.datetime.now(MADRID).date()
    dias = [hoy - dt.timedelta(days=i) for i in range(6, -1, -1)]

    hojas = gen.leer_xlsx(gen.XLSX)
    filas = hojas.get('biblioteca', [])
    urls_lib = {}
    for f in filas:
        if f.get('url'):
            urls_lib[f['url']] = f['id']
    for n in hojas.get('novedades', []):
        if n.get('url'):
            urls_lib.setdefault(n['url'], 'hoja «novedades»')
    salida = args.salida or os.path.join(RAIZ, 'novedades', f'{hoy}.md')
    if not args.salida and os.path.exists(salida):
        k = 2
        while os.path.exists(os.path.join(RAIZ, 'novedades', f'{hoy}-{k}.md')):
            k += 1
        salida = os.path.join(RAIZ, 'novedades', f'{hoy}-{k}.md')
    propuestos = {}
    nov_dir = os.path.join(RAIZ, 'novedades')
    if os.path.isdir(nov_dir):
        for f in sorted(os.listdir(nov_dir)):
            if f.endswith('.md') and os.path.join(nov_dir, f) != os.path.abspath(salida):
                inf = gen.leer_informe(os.path.join(nov_dir, f))
                for dn in (inf or {}).get('documentos_nuevos', []):
                    for u in dn['urls']:
                        propuestos.setdefault(u, inf['fecha'])

    # Fuentes
    fuentes, cands, desc, todos_titulos = [], [], [], []
    c1, d1, t1, r, _ = fuente_eurlex(dias); cands += c1; desc += d1; todos_titulos += t1
    fuentes.append(('EUR-Lex, Diario Oficial de la UE (vista diaria, series L y C)', r))
    c2, d2, r, _ = fuente_comision(dias); cands += c2; desc += d2
    fuentes.append(('Comisión Europea, marco regulador de la IA', r))
    c3, d3, rs, _ = fuente_aesia(dias); cands += c3; desc += d3
    fuentes += rs
    c4, d4, r, _ = fuente_aepd(dias); cands += c4; desc += d4
    fuentes.append(('AEPD, notas de prensa', r))
    c5, d5, t5, r, _ = fuente_boe(dias); cands += c5; desc += d5; todos_titulos += t5
    fuentes.append(('BOE (sumarios diarios de datos abiertos)', r))
    fuentes.append(('TJUE (curia.europa.eu)', fuente_tjue()))

    # Compara con la biblioteca
    nuevos = []
    for c in cands:
        ya = next((urls_lib[u] for u in [c['url']] + c['urls_doc'] if u in urls_lib), None)
        if ya:
            desc.append((c, f'ya está en la biblioteca ({ya})'))
            continue
        antes = next((propuestos[u] for u in [c['url']] + c['urls_doc'] if u in propuestos), None)
        c['ya_propuesto'] = antes
        nuevos.append(c)

    # Cambios de estado de lo que está en tramitación, diferido, recurrido o PENDIENTE
    vigilar = [f for f in filas if norm(f.get('estado')) in ('en tramitacion', 'aplicacion diferida', 'recurrido / anulado', 'pendiente')]
    periodo = f'del {dias[0]} al {dias[-1]}'
    cambios = []
    textos = todos_titulos + [(c['titulo'] + ' ' + c['resumen'], c['url'], c['fecha']) for c in cands]
    for f in vigilar:
        amb = f.get('ambito', '')
        mirado = {'España': f'BOE {periodo}', 'UE': f'Diario Oficial de la UE {periodo}'}.get(amb, '—')
        posibles = [(t, u) for t, u, _ in textos if menciona(f.get('titulo', ''), t)]
        if posibles:
            t, u = posibles[0]
            res = f'Posible cambio: «{limpio(t, 160)}» ({u}). Revísalo antes de cambiar el estado.'
        elif mirado == '—':
            pais = re.search(r'País: ([^.]+)\.', f.get('notas', ''))
            donde = pais.group(1) if pais else amb or 'su ámbito'
            res = f'Sin comprobar: ninguna fuente de la rutina cubre {donde}.'
        else:
            res = 'Sin publicaciones que lo mencionen en el periodo.'
        cambios.append((f['id'], f.get('estado', ''), mirado, res))
    posibles_cambios = [c for c in cambios if c[3].startswith('Posible cambio')]
    fallos = [n for n, r in fuentes if r.startswith('Falla')]

    # Informe
    L = [f'# Novedades · {hoy}', '',
         f'Periodo revisado: del {dias[0]} al {dias[-1]}. Fecha de consulta: {dt.datetime.now(MADRID):%Y-%m-%d}. '
         'Informe generado automáticamente con herramientas/rutina_semanal.py: el tipo, los temas y «por qué importa» son propuestas que hay que revisar.', '',
         '## Resumen']
    if nuevos:
        lista = '; '.join(limpio(c['titulo'], 90) for c in nuevos[:3]) + ('; …' if len(nuevos) > 3 else '')
        L.append(f'1. {len(nuevos)} documento(s) nuevo(s) en el periodo: {lista}' + ('' if lista.endswith(('…', '.')) else '.'))
    else:
        L.append('1. No hay documentos nuevos en el periodo.')
    L.append(f'2. Diario Oficial de la UE: {fuentes[0][1]} BOE: {next(r for n, r in fuentes if n.startswith("BOE"))}')
    L.append('3. ' + ' '.join(f'{n}: {r}' for n, r in fuentes if n.startswith(('Comisión', 'AESIA', 'AEPD'))))
    L.append('4. Cambios de estado: ' + (f'{len(posibles_cambios)} posible(s) cambio(s) que revisar ({", ".join(c[0] for c in posibles_cambios)}).'
                                         if posibles_cambios else 'ninguno detectado en las fuentes de la rutina.'))
    L.append('5. ' + ('Fuentes que no se pudieron consultar: ' + ', '.join(fallos) + '.' if fallos else 'Todas las fuentes respondieron.'))
    L += ['', '## Documentos nuevos', '']
    if not nuevos:
        L.append('No hay documentos nuevos en el periodo.')
    for i, c in enumerate(nuevos, 1):
        L.append(f'### {i}. {c["titulo"]}')
        L.append(f'- **Organismo:** {c["fuente"].split(",")[0]}')
        L.append(f'- **Fecha:** {c["fecha"]}')
        urls = f'{c["url"]}' + (' · documento (PDF): ' + ' · '.join(c['urls_doc']) if c['urls_doc'] else '')
        L.append(f'- **URL:** {urls}')
        L.append(f'- **Tipo:** {c["tipo"]} (propuesto)')
        L.append(f'- **Temas:** {"; ".join(c["temas"])} (propuestos)')
        porque = (f'según la fuente: «{c["resumen"]}»' if c['resumen'] else f'su título menciona la IA y se ha publicado en {c["fuente"]}; revisa si afecta a la biblioteca')
        L.append(f'- **Por qué importa:** {porque}.')
        if c.get('ya_propuesto'):
            L.append(f'- **Nota:** ya se propuso en el informe del {c["ya_propuesto"]} y sigue sin estar en la biblioteca.')
        L.append('')
    L += ['', '## Cambios de estado', '']
    if cambios:
        L += ['| ID | Estado en biblioteca.xlsx | Qué se ha mirado | Resultado |', '|---|---|---|---|']
        L += [f'| {celda(a)} | {celda(b)} | {celda(c)} | {celda(d)} |' for a, b, c, d in cambios]
    else:
        L.append('En la biblioteca no hay nada en tramitación, en aplicación diferida, recurrido ni PENDIENTE.')
    L += ['', '## Fuentes consultadas', '', '| Fuente | Resultado |', '|---|---|']
    L += [f'| {celda(n)} | {celda(r)} |' for n, r in fuentes]
    L += ['', '## Descartados en el periodo']
    if desc:
        L += [f'- {c["fuente"]}, {c["fecha"]}: «{limpio(c["titulo"], 140)}». Motivo: {m}.' for c, m in desc]
    else:
        L.append('Nada.')
    L += ['', '## Propuesta',
          ('Revisar y, si encajan, añadir a la biblioteca las novedades ' + ', '.join(f'n.º {i}' for i in range(1, len(nuevos) + 1)) + '.' if nuevos
           else 'Nada que añadir esta semana.') +
          (' Revisar también los posibles cambios de estado.' if posibles_cambios else '') +
          ' No se ha descargado nada ni se ha tocado biblioteca.xlsx.', '']
    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    with open(salida, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L))
    rel = os.path.relpath(salida, RAIZ) if os.path.abspath(salida).startswith(RAIZ) else salida
    resumen = (f'{len(nuevos)} documento(s) nuevo(s), {len(posibles_cambios)} posible(s) cambio(s) de estado' +
               (f', {len(fallos)} fuente(s) con fallo' if fallos else ''))
    print(f'Informe escrito en {rel}: {resumen}.')

    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as fh:
            fh.write(f'informe={rel}\n')
            fh.write(f'avisar={"si" if (nuevos or posibles_cambios) else "no"}\n')
            fh.write(f'titulo=Novedades {hoy}: {resumen}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

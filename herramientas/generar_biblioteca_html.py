#!/usr/bin/env python3
"""Genera biblioteca.html a partir de biblioteca.xlsx, /fichas y /novedades.

Uso (desde cualquier carpeta):
    python3 herramientas/generar_biblioteca_html.py

Solo usa la biblioteca estándar de Python. Lee:
  - biblioteca.xlsx: hojas «biblioteca» (una fila por documento) y «novedades».
  - fichas/*.md: la ficha de cada documento (tabla de campos y apartados).
  - novedades/*.md: los informes semanales (resumen, documentos nuevos, cambios de estado).
Escribe biblioteca.html con los datos embebidos como JSON. Si ya existía, mueve la
versión anterior a papelera/ (no borra nada).
"""
import base64
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLA = os.path.join(RAIZ, 'herramientas', 'plantilla_biblioteca.html')
XLSX = os.path.join(RAIZ, 'biblioteca.xlsx')
SALIDA = os.path.join(RAIZ, 'biblioteca.html')
M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
COLUMNAS_FECHA = {'fecha', 'fecha_consulta', 'fecha_alta', 'fecha_informe'}
avisos = []


# ---------- biblioteca.xlsx (inline strings o shared strings, como lo guarde Excel)
def leer_xlsx(ruta):
    with zipfile.ZipFile(ruta) as z:
        compartidas = []
        if 'xl/sharedStrings.xml' in z.namelist():
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(M + 'si'):
                compartidas.append(''.join(t.text or '' for t in si.iter(M + 't')))
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        destino = {r.get('Id'): r.get('Target') for r in rels}
        hojas = {}
        for s in wb.iter(M + 'sheet'):
            target = destino[s.get(R + 'id')].lstrip('/')
            ruta_hoja = target if target.startswith('xl/') else 'xl/' + target
            hojas[s.get('name')] = leer_hoja(z.read(ruta_hoja), compartidas)
        return hojas


def leer_hoja(xml, compartidas):
    filas = []
    for row in ET.fromstring(xml).iter(M + 'row'):
        valores = {}
        for c in row.findall(M + 'c'):
            col = re.match(r'[A-Z]+', c.get('r')).group(0)
            t = c.get('t')
            v = c.find(M + 'v')
            if t == 'inlineStr':
                txt = ''.join(x.text or '' for x in c.iter(M + 't'))
            elif t == 's' and v is not None:
                txt = compartidas[int(v.text)]
            elif v is not None:
                txt = v.text or ''
            else:
                txt = ''
            valores[col] = (txt, t)
        filas.append(valores)
    if not filas:
        return []
    cabecera = {col: val[0].strip() for col, val in filas[0].items() if val[0].strip()}
    salida = []
    for fila in filas[1:]:
        d = {}
        for col, nombre in cabecera.items():
            txt, t = fila.get(col, ('', None))
            if nombre in COLUMNAS_FECHA and t not in ('s', 'inlineStr', 'str') and re.fullmatch(r'\d+(\.0+)?', txt or ''):
                txt = (dt.date(1899, 12, 30) + dt.timedelta(days=int(float(txt)))).isoformat()  # fecha de Excel
            d[nombre] = (txt or '').strip()
        if any(d.values()):
            salida.append(d)
    return salida


# ---------- fichas/*.md
def leer_ficha(ruta):
    titulo, campos, secciones, actual = '', [], [], None
    for linea in open(ruta, encoding='utf-8').read().splitlines():
        if linea.startswith('# ') and not titulo:
            titulo = linea[2:].strip()
            continue
        if linea.startswith('## '):
            actual = {'titulo': linea[3:].strip(), 'parrafos': [], 'items': []}
            secciones.append(actual)
            continue
        if actual is None:
            m = re.match(r'^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$', linea)
            if m and m.group(1) != 'Campo' and not re.fullmatch(r'[-: ]+', m.group(1)):
                campos.append([m.group(1), m.group(2)])
            continue
        if linea.startswith('- '):
            actual['items'].append(linea[2:].strip())
        elif linea.strip():
            actual['parrafos'].append(linea.strip())
    return {'titulo': titulo, 'campos': campos, 'secciones': secciones}


def campo(ficha, nombre):
    for k, v in ficha['campos']:
        if k == nombre:
            return v
    return ''


def fechas_clave(ficha):
    out = []
    for s in ficha['secciones']:
        if s['titulo'].lower().startswith('fechas clave'):
            for item in s['items']:
                m = re.match(r'^(\d{4}(?:-\d{2}){0,2}):\s*(.+)$', item)
                if m:
                    out.append({'fecha': m.group(1), 'texto': m.group(2)})
    return out


# ---------- novedades/*.md (informes semanales)
def leer_informe(ruta):
    nombre = os.path.basename(ruta)
    m = re.match(r'(\d{4}-\d{2}-\d{2})', nombre)
    if not m:
        return None
    texto = open(ruta, encoding='utf-8').read()
    partes = re.split(r'^## ', texto, flags=re.M)
    inf = {'fecha': m.group(1), 'archivo': 'novedades/' + nombre, 'resumen': [], 'documentos_nuevos': [], 'cambios': []}
    for parte in partes[1:]:
        cab, _, cuerpo = parte.partition('\n')
        cab = cab.strip().lower()
        if cab.startswith('resumen'):
            inf['resumen'] = [re.sub(r'^(\d+\.|-)\s+', '', l).strip() for l in cuerpo.splitlines() if re.match(r'^(\d+\.|-)\s+', l)]
        elif cab.startswith('documentos nuevos'):
            for bloque in re.split(r'^### ', cuerpo, flags=re.M)[1:]:
                tit, _, resto = bloque.partition('\n')
                inf['documentos_nuevos'].append({
                    'titulo': re.sub(r'^\d+\.\s*', '', tit).strip(),
                    'urls': [u.rstrip('.,;)') for u in re.findall(r'https?://[^\s<>«»"]+', resto)],
                })
        elif cab.startswith('cambios de estado'):
            filas = [l for l in cuerpo.splitlines() if l.strip().startswith('|')]
            for l in filas[2:]:  # salta cabecera y separador
                celdas = [c.strip() for c in l.strip().strip('|').split('|')]
                if len(celdas) >= 4 and celdas[0]:
                    inf['cambios'].append({'id': celdas[0], 'estado': celdas[1], 'mirado': celdas[2], 'resultado': celdas[3]})
    return inf


def main():
    hojas = leer_xlsx(XLSX)
    filas = hojas.get('biblioteca', [])
    novedades_hoja = hojas.get('novedades', [])
    urls_rutina = {n.get('url') for n in novedades_hoja if (n.get('decision') or '').lower() in ('añadir', 'anadir')}

    fichas_dir = os.path.join(RAIZ, 'fichas')
    fichas = {}
    for f in sorted(os.listdir(fichas_dir)):
        if f.endswith('.md'):
            fichas['fichas/' + f] = leer_ficha(os.path.join(fichas_dir, f))
    fichas_por_id = {campo(fi, 'ID'): (ruta, fi) for ruta, fi in fichas.items()}

    documentos, usadas = [], set()
    for fila in filas:
        id_ = fila.get('id', '')
        ruta_ficha = fila.get('ficha', '')
        ficha = fichas.get(ruta_ficha)
        if ficha is None and id_ in fichas_por_id:
            ruta_ficha, ficha = fichas_por_id[id_]
        if ficha is None:
            avisos.append(f'{id_}: no encuentro su ficha ({fila.get("ficha")})')
            ficha = {'titulo': '', 'campos': [], 'secciones': []}
        else:
            usadas.add(ruta_ficha)
            if campo(ficha, 'ID') and campo(ficha, 'ID') != id_:
                avisos.append(f'{id_}: la ficha {ruta_ficha} dice ID {campo(ficha, "ID")}')
        archivo = fila.get('archivo', '')
        if archivo and not os.path.exists(os.path.join(RAIZ, archivo)):
            avisos.append(f'{id_}: no existe el archivo {archivo}')
        m = re.search(r'\(([^)]+)\)', campo(ficha, 'Ámbito'))
        documentos.append({
            'id': id_, 'tipo': fila.get('tipo', ''), 'ambito': fila.get('ambito', ''), 'pais': m.group(1) if m else '',
            'organismo': fila.get('organismo', ''), 'titulo': fila.get('titulo', ''), 'corto': ficha['titulo'],
            'fecha': fila.get('fecha', ''), 'estado': fila.get('estado', ''), 'vinculante': fila.get('vinculante', ''),
            'temas': [t.strip() for t in (fila.get('temas') or '').split(';') if t.strip()],
            'resumen': fila.get('resumen', ''), 'archivo': archivo, 'ficha_archivo': ruta_ficha, 'url': fila.get('url', ''),
            'fecha_consulta': fila.get('fecha_consulta', ''), 'fecha_alta': fila.get('fecha_alta', ''),
            'notas': fila.get('notas', ''),
            'origen': 'rutina semanal' if id_.startswith('NUEVO-') or fila.get('url') in urls_rutina else 'alta inicial',
            'fechas_clave': fechas_clave(ficha), 'ficha': ficha, 'xlsx': fila,
        })
    for ruta in sorted(set(fichas) - usadas):
        avisos.append(f'{ruta}: ficha sin fila en biblioteca.xlsx (no aparece en la página)')

    nov_dir = os.path.join(RAIZ, 'novedades')
    informes = []
    if os.path.isdir(nov_dir):
        for f in sorted(os.listdir(nov_dir)):
            if f.endswith('.md'):
                inf = leer_informe(os.path.join(nov_dir, f))
                if inf:
                    informes.append(inf)

    fechas = [d[k] for d in documentos for k in ('fecha_alta', 'fecha_consulta') if re.fullmatch(r'\d{4}-\d{2}-\d{2}', d[k] or '')]
    fechas += [i['fecha'] for i in informes]
    datos = {
        'actualizado': max(fechas) if fechas else '',
        'generado': dt.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'documentos': documentos,
        'novedades_hoja': novedades_hoja,
        'informes': informes,
    }
    # JSON seguro dentro de <script type="application/json">: sin «<», «>» ni «&» literales.
    js = json.dumps(datos, ensure_ascii=False, indent=1)
    js = js.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')

    html = open(PLANTILLA, encoding='utf-8').read()
    assert html.count('__DATOS__') == 1 and html.count('__CSP__') == 1, 'plantilla sin marcadores'
    html = html.replace('__DATOS__', js)

    # CSP estricta: solo el estilo y el script propios de la página (por hash), nada externo.
    def h(texto):
        return "'sha256-" + base64.b64encode(hashlib.sha256(texto.encode('utf-8')).digest()).decode() + "'"
    estilos = re.findall(r'<style>(.*?)</style>', html, re.S)
    scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
    assert len(estilos) == 1 and len(scripts) == 1, 'se esperaba un <style> y un <script> propios'
    csp = ("default-src 'none'; script-src " + h(scripts[0]) + "; style-src " + h(estilos[0]) +
           "; img-src data:; base-uri 'none'; form-action 'none'; object-src 'none'")
    html = html.replace('__CSP__', csp)

    if os.path.exists(SALIDA):
        papelera = os.path.join(RAIZ, 'papelera')
        os.makedirs(papelera, exist_ok=True)
        destino = os.path.join(papelera, 'biblioteca_' + dt.datetime.now().strftime('%Y-%m-%d_%H%M%S') + '.html')
        shutil.move(SALIDA, destino)
        print('Versión anterior movida a', os.path.relpath(destino, RAIZ))
    with open(SALIDA, 'w', encoding='utf-8') as f:
        f.write(html)

    n_fechas = sum(len(d['fechas_clave']) for d in documentos)
    print(f'biblioteca.html generada: {len(documentos)} documentos, {len(informes)} informe(s), '
          f'{n_fechas} fechas clave; última actualización {datos["actualizado"]}.')
    if avisos:
        print('AVISOS:')
        for a in avisos:
            print('  -', a)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

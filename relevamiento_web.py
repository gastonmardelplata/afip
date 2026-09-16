#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
relevamiento_web.py — Relevamiento forense de sitio web para constatación pericial.

Versión 1.2

Cambios respecto de v1.1:
- Corrige falsos positivos del control de calidad causados por iframes about:blank.
- Separa documentos de CONTROL POSITIVO de documentos de BÚSQUEDA.
- Los iframes se preservan y se buscan, pero no invalidan la captura principal.
- Identifica y documenta marcos auxiliares/vacíos.
- Revisión de enlaces internos ampliada a 100 por defecto.
- Mantiene capturas, DOM, MHTML, PDF, SHA-256, DNS, TLS, HTTP, sitemaps,
  API REST de WordPress, inventario de enlaces y archivo web.

Uso recomendado:
    python relevamiento_web_v1_2.py --url https://triunfoseguros.com/ \
      --salida C:\\Desarrollo\\Ponce\\EVIDENCIA \
      --causa "PONCE CINTIA IVANA C/ TRIUNFO COOPERATIVA DE SEGUROS LIMITADA" \
      --perito "Carlos Gastón Nat" \
      --revisar-enlaces --limite-enlaces 100

Dependencias:
    pip install requests dnspython playwright
    playwright install chromium
"""

import argparse
import csv
import hashlib
import json
import platform
import re
import socket
import ssl
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:
    TZ = None

try:
    import dns.resolver
    DNS_DISPONIBLE = True
except ImportError:
    DNS_DISPONIBLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_DISPONIBLE = True
except ImportError:
    PLAYWRIGHT_DISPONIBLE = False

VERSION = "1.2"

TERMINOS_POR_DEFECTO = [
    "Contratos de adhesión",
    "Contratos de adhesion",
    "Ley N° 24.240",
    "Ley 24.240",
    "24.240",
    "24240",
    "Defensa del Consumidor",
    "Condiciones Generales",
    "271/2020",
    "Resolución 271",
    "Resolucion 271",
]

TERMINOS_DOCUMENTACION = [
    "adhesion", "contrato", "condiciones", "clausula", "poliza",
    "legales", "transparencia", "consumidor", "reclamo", "ssn",
    "motovehiculo", "moto",
]

TEXTOS_CIERRE_AVISO = [
    "aceptar", "acepto", "entendido", "de acuerdo", "continuar",
    "cerrar", "ok", "got it", "close",
]

SUBDIRECTORIOS = [
    "01_ENTORNO", "02_INFRAESTRUCTURA", "03_CAPTURAS", "04_CODIGO",
    "05_ENLACES", "06_BUSQUEDAS", "07_ARCHIVO_WEB",
]

USER_AGENT_HTTP = (
    f"Mozilla/5.0 (X11; Linux x86_64) relevamiento_web/{VERSION} "
    "(pericia informatica)"
)


def ahora():
    return datetime.now(TZ) if TZ else datetime.now()


def marca_tiempo(dt=None):
    dt = dt or ahora()
    return dt.strftime("%Y-%m-%d %H:%M:%S %z") or dt.isoformat()


class Bitacora:
    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.ruta, "a", encoding="utf-8")
        self.alertas = []

    def __call__(self, mensaje, nivel="INFO"):
        linea = f"[{marca_tiempo()}] [{nivel}] {mensaje}"
        try:
            print(linea)
        except UnicodeEncodeError:
            print(linea.encode("ascii", "replace").decode("ascii"))
        self.fh.write(linea + "\n")
        self.fh.flush()
        if nivel in ("ERROR", "ALERTA"):
            self.alertas.append(linea)

    def cerrar(self):
        self.fh.close()


def normalizar(texto):
    desc = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in desc if not unicodedata.combining(c)).lower()


def sha256_archivo(ruta, bloque=1 << 20):
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for trozo in iter(lambda: fh.read(bloque), b""):
            h.update(trozo)
    return h.hexdigest()


def guardar_texto(ruta, contenido):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def extraer_texto_html_simple(html):
    if not html:
        return ""
    texto = re.sub(r"(?is)<script\b[^>]*>.*?</script>", " ", html)
    texto = re.sub(r"(?is)<style\b[^>]*>.*?</style>", " ", texto)
    texto = re.sub(r"(?s)<[^>]+>", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def es_marco_auxiliar(nombre, contenido):
    if "about:blank" in normalizar(nombre):
        return True, "URL about:blank"
    texto = extraer_texto_html_simple(contenido)
    if len(texto) < 50:
        return True, "sin contenido textual significativo"
    return False, ""


def relevar_entorno(base, log, url, causa, perito, hash_script):
    log("Registrando entorno de la diligencia")
    ip_publica = None
    for servicio in ("https://api.ipify.org?format=json", "https://ifconfig.co/json"):
        try:
            r = requests.get(servicio, timeout=10, headers={"User-Agent": USER_AGENT_HTTP})
            ip_publica = r.json().get("ip")
            if ip_publica:
                log(f"IP pública obtenida desde {servicio}: {ip_publica}")
                break
        except Exception as e:
            log(f"No se pudo obtener IP pública desde {servicio}: {e}", "WARN")

    entorno = {
        "causa": causa,
        "perito": perito,
        "url_objeto": url,
        "inicio_diligencia": marca_tiempo(),
        "zona_horaria": str(TZ) if TZ else "no determinada",
        "utc_offset": ahora().strftime("%z"),
        "equipo_hostname": socket.gethostname(),
        "sistema_operativo": f"{platform.system()} {platform.release()} ({platform.version()})",
        "arquitectura": platform.machine(),
        "python": sys.version.split()[0],
        "ip_publica": ip_publica or "no determinada",
        "herramienta": f"relevamiento_web.py v{VERSION}",
        "sha256_herramienta": hash_script,
    }
    guardar_texto(base / "01_ENTORNO" / "entorno.json", json.dumps(entorno, ensure_ascii=False, indent=2))
    guardar_texto(base / "01_ENTORNO" / "entorno.txt", "\n".join(f"{k}: {v}" for k, v in entorno.items()))
    return entorno


def relevar_dns(base, log, host):
    log(f"Consultando registros DNS de {host}")
    lineas = [f"Consulta DNS de {host} — {marca_tiempo()}", ""]
    if not DNS_DISPONIBLE:
        lineas += ["dnspython NO INSTALADO; no se registraron datos de resolución.", "Instalar con: pip install dnspython"]
        log("dnspython no instalado: dns.txt queda sin datos de resolución.", "ALERTA")
    else:
        resolver = dns.resolver.Resolver()
        lineas += [f"Servidores DNS utilizados: {', '.join(str(x) for x in resolver.nameservers)}", ""]
        for tipo in ("A", "AAAA", "CNAME", "NS", "MX", "TXT", "SOA"):
            lineas.append(f"--- {tipo} ---")
            try:
                for rdata in resolver.resolve(host, tipo):
                    lineas.append(str(rdata))
            except Exception as e:
                lineas.append(f"(sin respuesta: {type(e).__name__})")
            lineas.append("")
    guardar_texto(base / "02_INFRAESTRUCTURA" / "dns.txt", "\n".join(lineas))


def relevar_rdap(base, log, host):
    partes = host.split(".")
    dominio = ".".join(partes[-2:]) if len(partes) >= 2 else host
    log(f"Consultando RDAP de {dominio}")
    try:
        r = requests.get(f"https://rdap.org/domain/{dominio}", timeout=20, headers={"User-Agent": USER_AGENT_HTTP})
        guardar_texto(base / "02_INFRAESTRUCTURA" / "rdap.json", json.dumps(r.json(), ensure_ascii=False, indent=2))
        log(f"RDAP obtenido (HTTP {r.status_code})")
    except Exception as e:
        log(f"RDAP no disponible: {e}", "WARN")
    try:
        salida = subprocess.run(["whois", dominio], capture_output=True, text=True, timeout=40)
        if salida.stdout.strip():
            guardar_texto(base / "02_INFRAESTRUCTURA" / "whois.txt", salida.stdout)
            log("whois de sistema registrado")
    except Exception as e:
        log(f"whois de sistema no disponible (normal en Windows): {e}", "WARN")


def relevar_tls(base, log, host, puerto=443):
    log(f"Verificando certificado TLS de {host}:{puerto}")
    lineas = [f"Certificado TLS de {host}:{puerto} — {marca_tiempo()}", ""]
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, puerto), timeout=20) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
                lineas += [
                    f"Protocolo negociado: {tls.version()}", f"Cifrado: {tls.cipher()}", "",
                    f"Sujeto: {cert.get('subject')}", f"Emisor: {cert.get('issuer')}",
                    f"Número de serie: {cert.get('serialNumber')}", f"Válido desde: {cert.get('notBefore')}",
                    f"Válido hasta: {cert.get('notAfter')}",
                ]
                sans = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
                lineas.append(f"Nombres alternativos (SAN): {', '.join(sans)}")
    except Exception as e:
        lineas.append(f"ERROR: no se pudo establecer la sesión TLS: {e}")
        log(f"Fallo en verificación TLS: {e}", "WARN")
    guardar_texto(base / "02_INFRAESTRUCTURA" / "tls.txt", "\n".join(lineas))


def relevar_http(base, log, url):
    log(f"Solicitando cabeceras HTTP de {url}")
    lineas = [f"Solicitud HTTP a {url} — {marca_tiempo()}", ""]
    fuente_html, cabeceras = "", {}
    try:
        r = requests.get(url, timeout=30, allow_redirects=True, headers={"User-Agent": USER_AGENT_HTTP})
        if r.history:
            lineas.append("--- Cadena de redirecciones ---")
            for salto in r.history:
                lineas.append(f"{salto.status_code} {salto.url} -> {salto.headers.get('Location', '')}")
            lineas.append("")
        lineas += [f"URL final: {r.url}", f"Código de estado: {r.status_code}"]
        try:
            lineas.append(f"IP resuelta del host: {socket.gethostbyname(urlparse(r.url).hostname)}")
        except Exception:
            lineas.append("IP resuelta del host: no determinada")
        lineas += ["", "--- Cabeceras de respuesta ---"]
        for k, v in r.headers.items():
            lineas.append(f"{k}: {v}")
        cabeceras = dict(r.headers)
        fuente_html = r.text
        log(f"HTTP {r.status_code} — {len(fuente_html)} bytes de HTML sin renderizar")
        low = {k.lower(): v for k, v in r.headers.items()}
        for clave in ("x-litespeed-cache", "cf-cache-status", "x-cache", "age"):
            if clave in low:
                log(f"Respuesta servida con intervención de caché ({clave}: {low[clave]})", "WARN")
    except Exception as e:
        lineas.append(f"ERROR: {e}")
        log(f"Fallo en la solicitud HTTP: {e}", "ERROR")
    guardar_texto(base / "02_INFRAESTRUCTURA" / "http_cabeceras.txt", "\n".join(lineas))
    if fuente_html:
        guardar_texto(base / "04_CODIGO" / "home_fuente_sin_renderizar.html", fuente_html)
    return fuente_html, cabeceras


def descubrir_sitemaps(base, log, url):
    raiz = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    candidatos, urls_paginas = [], []
    try:
        r = requests.get(urljoin(raiz + "/", "robots.txt"), timeout=20, headers={"User-Agent": USER_AGENT_HTTP})
        guardar_texto(base / "05_ENLACES" / "robots.txt", f"<!-- HTTP {r.status_code} — {marca_tiempo()} -->\n{r.text}")
        log(f"robots.txt: HTTP {r.status_code}")
        for m in re.finditer(r"(?im)^\s*sitemap:\s*(\S+)", r.text):
            candidatos.append(m.group(1).strip())
            log(f"  sitemap declarado en robots.txt: {m.group(1).strip()}")
    except Exception as e:
        log(f"robots.txt no accesible: {e}", "WARN")
    for ruta in ("sitemap.xml", "wp-sitemap.xml", "sitemap_index.xml"):
        candidatos.append(urljoin(raiz + "/", ruta))
    vistos, pendientes = set(), list(dict.fromkeys(candidatos))
    dir_sm = base / "05_ENLACES" / "sitemaps"
    while pendientes and len(vistos) < 40:
        sm = pendientes.pop(0)
        if sm in vistos:
            continue
        vistos.add(sm)
        try:
            r = requests.get(sm, timeout=30, headers={"User-Agent": USER_AGENT_HTTP})
            cuerpo = r.text
            if "<loc>" not in cuerpo:
                log(f"  {sm}: HTTP {r.status_code} sin contenido de sitemap")
                continue
            nombre = re.sub(r"[^A-Za-z0-9._-]", "_", sm.split("/")[-1]) or "sitemap.xml"
            guardar_texto(dir_sm / nombre, f"<!-- Origen: {sm} — HTTP {r.status_code} — {marca_tiempo()} -->\n{cuerpo}")
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", cuerpo, re.I)
            if re.search(r"<sitemapindex\b", cuerpo, re.I):
                log(f"  {sm}: HTTP {r.status_code} — índice con {len(locs)} sitemap(s)")
                pendientes.extend(locs)
            else:
                log(f"  {sm}: HTTP {r.status_code} — {len(locs)} URL(s)")
                urls_paginas.extend(locs)
        except Exception as e:
            log(f"  {sm}: error {e}", "WARN")
    return sorted(set(urls_paginas))


def enumerar_api_rest(base, log, url):
    raiz = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    paginas = []
    for tipo in ("pages", "posts"):
        pagina_nro = 1
        while pagina_nro <= 10:
            try:
                r = requests.get(
                    f"{raiz}/wp-json/wp/v2/{tipo}", timeout=30,
                    params={"per_page": 100, "page": pagina_nro, "_fields": "id,link,slug,title,date,modified"},
                    headers={"User-Agent": USER_AGENT_HTTP},
                )
                if r.status_code != 200:
                    if pagina_nro == 1:
                        log(f"API REST /{tipo}: HTTP {r.status_code} (no disponible)")
                    break
                lote = r.json()
                if not lote:
                    break
                for p in lote:
                    paginas.append({
                        "tipo": tipo, "id": p.get("id"),
                        "titulo": (p.get("title") or {}).get("rendered", ""),
                        "slug": p.get("slug", ""), "url": p.get("link", ""),
                        "modificado": p.get("modified", ""),
                    })
                total = r.headers.get("X-WP-TotalPages")
                log(f"API REST /{tipo}: página {pagina_nro} de {total or '?'} — {len(lote)} elemento(s)")
                if total and pagina_nro >= int(total):
                    break
                pagina_nro += 1
            except Exception as e:
                log(f"API REST /{tipo}: error {e}", "WARN")
                break
    if paginas:
        guardar_texto(base / "05_ENLACES" / "api_rest_contenidos.json", json.dumps(paginas, ensure_ascii=False, indent=2))
    return paginas


def volcar_paginas_publicadas(base, log, urls_sitemap, paginas_api, terminos_doc):
    filas, vistos = [], set()
    for u in urls_sitemap:
        if u not in vistos:
            vistos.add(u)
            filas.append({"origen": "sitemap", "titulo": "", "url": u})
    for p in paginas_api:
        if p["url"] in vistos:
            for f in filas:
                if f["url"] == p["url"]:
                    f["titulo"] = p["titulo"]
                    f["origen"] = "sitemap+api"
            continue
        vistos.add(p["url"])
        filas.append({"origen": f"api:{p['tipo']}", "titulo": p["titulo"], "url": p["url"]})
    for f in filas:
        texto = normalizar(f["url"] + " " + f["titulo"])
        encontrados = []
        for t in terminos_doc:
            patron = rf"(?<![a-z0-9]){re.escape(normalizar(t))}(?![a-z0-9])"
            if re.search(patron, texto):
                encontrados.append(t)
        f["terminos"] = "|".join(encontrados)
    ruta = base / "05_ENLACES" / "paginas_publicadas.csv"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["origen", "titulo", "url", "terminos"])
        w.writeheader(); w.writerows(filas)
    con_interes = [f for f in filas if f["terminos"]]
    log(f"Contenidos publicados consolidados: {len(filas)} URL(s); {len(con_interes)} con términos de documentación contractual")
    for f in con_interes[:25]:
        log(f"  [{f['terminos']}] {f['url']}")
    return filas


JS_INVENTARIO_ENLACES = r"""
() => Array.from(document.querySelectorAll('a[href]')).map(a => {
    let ubicacion = 'cuerpo';
    if (a.closest('footer, [class*="footer" i], [id*="footer" i]')) ubicacion = 'footer';
    else if (a.closest('header, [class*="header" i], [id*="header" i]')) ubicacion = 'header';
    else if (a.closest('nav, [class*="menu" i], [class*="nav" i]')) ubicacion = 'nav';
    return {
        href: a.href,
        texto: (a.innerText || a.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 200),
        titulo: a.getAttribute('title') || '',
        aria: a.getAttribute('aria-label') || '',
        ubicacion: ubicacion,
        visible: !!(a.offsetWidth || a.offsetHeight || a.getClientRects().length)
    };
})
"""

JS_DESPLAZAR = r"""
async () => {
    await new Promise(resolver => {
        let recorrido = 0;
        const paso = Math.max(200, Math.floor(window.innerHeight * 0.75));
        const temporizador = setInterval(() => {
            window.scrollBy(0, paso);
            recorrido += paso;
            if (recorrido >= document.body.scrollHeight + window.innerHeight) {
                clearInterval(temporizador);
                window.scrollTo(0, 0);
                setTimeout(resolver, 1200);
            }
        }, 250);
    });
}
"""

JS_DIAGNOSTICO = r"""
() => ({
    alto_documento: document.body.scrollHeight,
    nodos: document.getElementsByTagName('*').length,
    scripts: document.scripts.length,
    imagenes: document.images.length,
    imagenes_sin_cargar: Array.from(document.images).filter(i => !i.complete || i.naturalWidth === 0).length,
    diferidos: document.querySelectorAll('[data-lazyloaded], [data-src], [data-litespeed-src], [loading="lazy"]').length,
    iframes: Array.from(document.querySelectorAll('iframe')).map(f => f.src || f.getAttribute('data-src') || '(sin src)')
})
"""


def cerrar_aviso_modal(pagina, log, perfil):
    for texto in TEXTOS_CIERRE_AVISO:
        try:
            control = pagina.get_by_role("button", name=re.compile(rf"^\s*{re.escape(texto)}\s*$", re.I))
            if control.count() and control.first.is_visible():
                etiqueta = control.first.inner_text().strip()
                control.first.click(timeout=5000); pagina.wait_for_timeout(1200)
                log(f"[{perfil}] Aviso superpuesto cerrado mediante el control «{etiqueta}»")
                return etiqueta
        except Exception:
            pass
    for texto in TEXTOS_CIERRE_AVISO:
        try:
            control = pagina.get_by_text(re.compile(rf"^\s*{re.escape(texto)}\s*$", re.I))
            if control.count() and control.first.is_visible():
                etiqueta = control.first.inner_text().strip()
                control.first.click(timeout=5000); pagina.wait_for_timeout(1200)
                log(f"[{perfil}] Aviso superpuesto cerrado mediante el elemento «{etiqueta}»")
                return etiqueta
        except Exception:
            pass
    log(f"[{perfil}] No se detectó aviso superpuesto que requiera cierre")
    return None


def capturar_con_navegador(base, log, url, perfil, dispositivo=None):
    resultado = {"perfil": perfil, "dom": "", "enlaces": [], "marcos": {}, "marcos_meta": []}
    cap = base / "03_CAPTURAS"; cap.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        log(f"[{perfil}] Navegador Chromium {navegador.version}")
        opciones = dict(dispositivo) if dispositivo else {"viewport": {"width": 1920, "height": 1080}}
        opciones.update({"locale": "es-AR", "timezone_id": "America/Argentina/Buenos_Aires"})
        contexto = navegador.new_context(**opciones)
        pagina = contexto.new_page()
        hora_acceso = marca_tiempo(); log(f"[{perfil}] Acceso a {url} — {hora_acceso}")
        respuesta = pagina.goto(url, wait_until="networkidle", timeout=90000)
        resultado.update({
            "hora_acceso": hora_acceso, "url_final": pagina.url,
            "estado_http": respuesta.status if respuesta else None,
            "navegador": f"Chromium {navegador.version}",
        })
        log(f"[{perfil}] URL final: {pagina.url} — HTTP {resultado['estado_http']}")
        pagina.wait_for_timeout(3000)
        pagina.screenshot(path=str(cap / f"{perfil}_01_primer_acceso_viewport.png"), full_page=False)
        pagina.screenshot(path=str(cap / f"{perfil}_01_primer_acceso_completa.png"), full_page=True)
        log(f"[{perfil}] Estado 1 (primer acceso) capturado")
        resultado["aviso_cerrado"] = cerrar_aviso_modal(pagina, log, perfil)
        log(f"[{perfil}] Desplazando la página para forzar el contenido diferido")
        try:
            pagina.evaluate(JS_DESPLAZAR)
        except Exception as e:
            log(f"[{perfil}] Fallo en el desplazamiento: {e}", "WARN")
        try:
            pagina.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        pagina.wait_for_timeout(2000)
        pagina.screenshot(path=str(cap / f"{perfil}_02_navegable_viewport.png"), full_page=False)
        pagina.screenshot(path=str(cap / f"{perfil}_02_navegable_completa.png"), full_page=True)
        log(f"[{perfil}] Estado 2 (navegable) capturado")
        diag = pagina.evaluate(JS_DIAGNOSTICO); resultado["diagnostico"] = diag
        log(f"[{perfil}] Diagnóstico: {diag['nodos']} nodos, {diag['alto_documento']} px de alto, {diag['imagenes']} imágenes ({diag['imagenes_sin_cargar']} sin cargar), {diag['diferidos']} elementos diferidos, {len(diag['iframes'])} marco(s)")
        if diag["imagenes_sin_cargar"] > max(3, diag["imagenes"] * 0.3):
            log(f"[{perfil}] Proporción alta de imágenes sin cargar: revisar visualmente las capturas", "ALERTA")
        dom = pagina.content(); guardar_texto(base / "04_CODIGO" / f"home_dom_{perfil}.html", dom)
        resultado["dom"] = dom; log(f"[{perfil}] DOM renderizado guardado ({len(dom)} bytes)")
        for i, marco in enumerate(pagina.frames):
            if marco == pagina.main_frame:
                continue
            try:
                contenido = marco.content(); nombre = f"marco_{perfil}_{i}"; identificador = f"{nombre} ({marco.url})"
                guardar_texto(base / "04_CODIGO" / f"{nombre}.html", f"<!-- URL del marco: {marco.url} -->\n{contenido}")
                resultado["marcos"][identificador] = contenido
                auxiliar, motivo = es_marco_auxiliar(identificador, contenido)
                resultado["marcos_meta"].append({
                    "nombre": nombre, "url": marco.url, "auxiliar": auxiliar, "motivo": motivo,
                    "bytes": len(contenido), "texto_util": len(extraer_texto_html_simple(contenido)),
                })
                sufijo = f" — auxiliar ({motivo})" if auxiliar else ""
                log(f"[{perfil}] Marco {i} capturado: {marco.url}{sufijo}")
            except Exception as e:
                log(f"[{perfil}] Marco {i} no accesible: {e}", "WARN")
        guardar_texto(base / "04_CODIGO" / f"marcos_{perfil}.json", json.dumps(resultado["marcos_meta"], ensure_ascii=False, indent=2))
        try:
            cdp = contexto.new_cdp_session(pagina); snap = cdp.send("Page.captureSnapshot", {"format": "mhtml"})
            guardar_texto(base / "04_CODIGO" / f"home_{perfil}.mhtml", snap["data"])
            log(f"[{perfil}] Instantánea MHTML generada")
        except Exception as e:
            log(f"[{perfil}] MHTML no generado: {e}", "WARN")
        if perfil == "escritorio":
            try:
                pagina.pdf(path=str(cap / "home_escritorio.pdf"), print_background=True, format="A4")
                log("[escritorio] PDF de la página generado")
            except Exception as e:
                log(f"[escritorio] PDF no generado: {e}", "WARN")
        resultado["enlaces"] = pagina.evaluate(JS_INVENTARIO_ENLACES)
        log(f"[{perfil}] {len(resultado['enlaces'])} enlaces inventariados")
        contexto.close(); navegador.close()
    return resultado


def volcar_enlaces(base, log, enlaces, host):
    ruta = base / "05_ENLACES" / "inventario_enlaces.csv"; ruta.parent.mkdir(parents=True, exist_ok=True)
    vistos, conteo = set(), {}
    with open(ruta, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["url", "texto", "titulo", "aria_label", "ubicacion", "visible", "mismo_dominio"])
        for e in enlaces:
            href = e.get("href", "")
            if not href or href in vistos:
                continue
            vistos.add(href); ubicacion = e.get("ubicacion", "cuerpo"); conteo[ubicacion] = conteo.get(ubicacion, 0) + 1
            netloc = urlparse(href).netloc
            mismo = netloc == host or netloc.endswith("." + host)
            w.writerow([href, e.get("texto", ""), e.get("titulo", ""), e.get("aria", ""), ubicacion,
                        "sí" if e.get("visible") else "no", "sí" if mismo else "no"])
    log(f"Inventario de enlaces volcado: {len(vistos)} URLs únicas — " + ", ".join(f"{k}: {v}" for k, v in sorted(conteo.items())))
    return sorted(vistos)


def comparar_fuente_dom(base, log, fuente, capturas, terminos):
    log("Comparando código fuente contra DOM renderizado")
    lineas = [f"Comparación fuente vs. DOM — {marca_tiempo()}", "", f"Código fuente sin renderizar: {len(fuente)} bytes"]
    for c in capturas:
        lineas.append(f"DOM renderizado ({c['perfil']}): {len(c['dom'])} bytes (diferencia: {len(c['dom']) - len(fuente):+d})")
    lineas.append(""); f_norm = normalizar(fuente); inyectados = []
    for c in capturas:
        d_norm = normalizar(c["dom"]); lineas.append(f"--- Divergencia por término ({c['perfil']}) ---")
        for t in terminos:
            t_n = normalizar(t); en_f, en_d = t_n in f_norm, t_n in d_norm
            if en_d and not en_f:
                estado = "SOLO EN DOM — contenido inyectado por JavaScript"; inyectados.append((t, c["perfil"]))
            elif en_f and not en_d:
                estado = "SOLO EN FUENTE — presente en HTML pero removido al renderizar"
            elif en_f and en_d:
                estado = "en ambos"
            else:
                estado = "en ninguno"
            lineas.append(f'  "{t}": {estado}')
        lineas.append("")
    guardar_texto(base / "04_CODIGO" / "comparacion_fuente_dom.txt", "\n".join(lineas))
    return inyectados


def buscar_terminos(base, log, documentos, terminos, nombre_archivo="busquedas"):
    log(f"Ejecutando búsquedas textuales ({nombre_archivo})")
    resultados = []
    for termino in terminos:
        t_norm = normalizar(termino)
        for nombre, contenido in documentos.items():
            if not contenido:
                continue
            c_norm = normalizar(contenido)
            posiciones = [m.start() for m in re.finditer(re.escape(t_norm), c_norm)]
            contextos = []
            for pos in posiciones[:5]:
                ini, fin = max(0, pos - 120), min(len(contenido), pos + 120)
                contextos.append(contenido[ini:fin].replace("\n", " ").strip())
            resultados.append({"termino": termino, "documento": nombre, "coincidencias": len(posiciones), "contextos": contextos})
    lineas = [f"Búsquedas textuales — {marca_tiempo()}", "Comparación insensible a mayúsculas y a acentuación.", ""]
    for r in resultados:
        estado = f"{r['coincidencias']} coincidencia(s)" if r["coincidencias"] else "SIN COINCIDENCIAS"
        lineas.append(f'Término "{r["termino"]}" en {r["documento"]}: {estado}')
        for ctx in r["contextos"]:
            lineas.append(f"    ...{ctx}...")
        lineas.append("")
    guardar_texto(base / "06_BUSQUEDAS" / f"{nombre_archivo}.txt", "\n".join(lineas))
    guardar_texto(base / "06_BUSQUEDAS" / f"{nombre_archivo}.json", json.dumps(resultados, ensure_ascii=False, indent=2))
    total = sum(r["coincidencias"] for r in resultados); log(f"Búsquedas completadas: {total} coincidencia(s) en total")
    return resultados


def derivar_control(url, fuente, extra):
    if extra:
        return [t.strip() for t in extra.split(",") if t.strip()]
    host = urlparse(url).netloc.replace("www.", ""); etiqueta = host.split(".")[0]; control = [etiqueta]
    m = re.search(r"<title[^>]*>(.*?)</title>", fuente or "", re.I | re.S)
    if m:
        palabras = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{5,}", m.group(1)); control.extend(palabras[:3])
    return list(dict.fromkeys(control))


def control_positivo(base, log, documentos_principales, terminos_control, marcos_auxiliares=None):
    log(f"Control positivo con los términos: {', '.join(terminos_control)}")
    lineas = [
        f"CONTROL POSITIVO — {marca_tiempo()}", "",
        "Verifica que la captura principal contiene contenido real del sitio.",
        "Los iframes se preservan y se incluyen en las búsquedas, pero no invalidan",
        "el control positivo del documento principal, pues pueden ser auxiliares o about:blank.", "",
    ]
    fallas = []
    for nombre, contenido in documentos_principales.items():
        lineas.append(f"--- {nombre} ---")
        if not contenido:
            lineas += ["  DOCUMENTO VACÍO", ""]
            fallas.append((nombre, "[documento vacío]")); continue
        c_norm = normalizar(contenido)
        for t in terminos_control:
            n = len(re.findall(re.escape(normalizar(t)), c_norm))
            lineas.append(f'  "{t}": {n} coincidencia(s)')
            if n == 0:
                fallas.append((nombre, t))
        lineas.append("")
    if marcos_auxiliares:
        lineas.append("--- Marcos preservados (informativo; no invalidan el control) ---")
        for m in marcos_auxiliares:
            estado = "auxiliar" if m.get("auxiliar") else "con contenido significativo"
            motivo = f" — {m.get('motivo')}" if m.get("motivo") else ""
            lineas.append(f"  {m.get('nombre')} | {m.get('url')} | {estado}{motivo} | {m.get('bytes')} bytes")
        lineas.append("")
    if fallas:
        lineas.insert(1, ">>> CONTROL POSITIVO FALLIDO <<<")
        for nombre, t in fallas:
            log(f'CONTROL POSITIVO FALLIDO: "{t}" no aparece en {nombre}. No presentar un resultado negativo hasta resolver la captura.', "ERROR")
        ok = False
    else:
        lineas.insert(1, ">>> CONTROL POSITIVO SUPERADO <<<")
        log("Control positivo superado: la captura principal contiene contenido real del sitio")
        ok = True
    guardar_texto(base / "06_BUSQUEDAS" / "control_positivo.txt", "\n".join(lineas))
    return ok


def revisar_enlaces_internos(base, log, urls, host, terminos, limite=100):
    log(f"Revisando hasta {limite} enlaces internos en busca de documentación contractual")
    hallazgos = []
    internos = [u for u in urls if urlparse(u).netloc == host or urlparse(u).netloc.endswith("." + host)][:limite]
    for u in internos:
        try:
            r = requests.get(u, timeout=25, allow_redirects=True, headers={"User-Agent": USER_AGENT_HTTP})
            cuerpo_norm = normalizar(r.text)
            encontrados = [t for t in terminos if normalizar(t) in cuerpo_norm]
            pdfs = re.findall(r"href=[\"']([^\"']+\.pdf(?:\?[^\"']*)?)[\"']", r.text, re.I)
            hallazgos.append({
                "url_solicitada": u, "url_final": r.url, "estado_http": r.status_code,
                "content_type": r.headers.get("Content-Type", ""), "terminos_hallados": encontrados,
                "pdf_enlazados": [urljoin(r.url, p) for p in pdfs[:30]],
            })
            if encontrados or pdfs:
                log(f"  {u} -> términos {encontrados or '-'} / {len(pdfs)} PDF")
        except Exception as e:
            hallazgos.append({"url_solicitada": u, "error": str(e)})
    guardar_texto(base / "05_ENLACES" / "revision_enlaces_internos.json", json.dumps(hallazgos, ensure_ascii=False, indent=2))
    return hallazgos


def relevar_archivo_web(base, log, url, fechas):
    log("Consultando repositorio de archivo web (Wayback Machine)")
    host = urlparse(url).netloc; salida = {"consultas_disponibilidad": [], "cdx": None}
    for fecha in fechas:
        try:
            r = requests.get("https://archive.org/wayback/available", params={"url": host, "timestamp": fecha}, timeout=30, headers={"User-Agent": USER_AGENT_HTTP})
            datos = r.json(); salida["consultas_disponibilidad"].append({"fecha_solicitada": fecha, "respuesta": datos})
            inst = datos.get("archived_snapshots", {}).get("closest", {})
            log(f"  {fecha} -> {inst.get('timestamp', 'sin instantánea')} {inst.get('url', '')}")
        except Exception as e:
            log(f"  {fecha} -> error: {e}", "WARN")
    try:
        r = requests.get("https://web.archive.org/cdx/search/cdx", params={
            "url": host, "output": "json", "fl": "timestamp,original,statuscode,digest",
            "filter": "statuscode:200", "collapse": "timestamp:8",
        }, timeout=60, headers={"User-Agent": USER_AGENT_HTTP})
        salida["cdx"] = r.json(); log(f"  Índice CDX: {max(0, len(salida['cdx']) - 1)} instantáneas listadas")
    except Exception as e:
        log(f"  Índice CDX no disponible: {e}", "WARN")
    guardar_texto(base / "07_ARCHIVO_WEB" / "archivo_web.json", json.dumps(salida, ensure_ascii=False, indent=2))
    return salida


def generar_manifiesto(base, log):
    log("Calculando hashes SHA-256 del paquete de evidencia")
    filas, lineas = [], ["MANIFIESTO DE INTEGRIDAD — SHA-256", f"Generado: {marca_tiempo()}", "=" * 100, ""]
    for ruta in sorted(base.rglob("*")):
        if not ruta.is_file() or ruta.name in ("ANEXO_HASHES.txt", "manifiesto.json"):
            continue
        rel = ruta.relative_to(base); h = sha256_archivo(ruta); tam = ruta.stat().st_size
        mod = datetime.fromtimestamp(ruta.stat().st_mtime, TZ) if TZ else datetime.fromtimestamp(ruta.stat().st_mtime)
        filas.append({"archivo": str(rel), "bytes": tam, "sha256": h, "modificado": marca_tiempo(mod)})
        lineas += [f"Archivo   : {rel}", f"Tamaño    : {tam} bytes", f"SHA-256   : {h}", f"Modificado: {marca_tiempo(mod)}", "-" * 100]
    lineas.append(f"\nTotal: {len(filas)} archivo(s).")
    guardar_texto(base / "ANEXO_HASHES.txt", "\n".join(lineas))
    guardar_texto(base / "manifiesto.json", json.dumps(filas, ensure_ascii=False, indent=2))
    log(f"Manifiesto generado sobre {len(filas)} archivo(s)")
    return filas


def seccion_en_inicio(busquedas):
    for r in busquedas:
        if r["coincidencias"] <= 0:
            continue
        if not normalizar(r["termino"]).startswith("contratos de adhesion"):
            continue
        doc = normalizar(r["documento"])
        if "codigo fuente sin renderizar" in doc or "dom renderizado" in doc:
            return True
    return False


def generar_informe(base, log, entorno, capturas, busquedas, enlaces, paginas, control_ok, inyectados, alertas, revision_enlaces=None):
    log("Generando borrador de informe técnico")
    veredicto = "SE CONSTATÓ" if seccion_en_inicio(busquedas) else "NO SE CONSTATÓ"
    md = [
        "# BORRADOR DE INFORME TÉCNICO — CONSTATACIÓN DE SITIO WEB\n",
        f"**Causa:** {entorno['causa']}  ", f"**Perito:** {entorno['perito']}  ",
        f"**Sitio constatado:** {entorno['url_objeto']}  ",
        f"**Fecha y hora de la diligencia:** {entorno['inicio_diligencia']}\n",
    ]
    if not control_ok:
        md.append("> **ADVERTENCIA: EL CONTROL POSITIVO FALLÓ.** No presentar conclusiones negativas sin resolver la causa instrumental.\n")
    md += ["## 1. Entorno técnico\n", "| Parámetro | Valor |", "|---|---|"]
    for k, v in entorno.items():
        md.append(f"| {k.replace('_', ' ')} | {v} |")
    md += ["", "## 2. Acceso al sitio\n", "| Perfil | Hora de acceso | URL final | HTTP | Navegador | Aviso cerrado |", "|---|---|---|---|---|---|"]
    for c in capturas:
        md.append(f"| {c['perfil']} | {c.get('hora_acceso','-')} | {c.get('url_final','-')} | {c.get('estado_http','-')} | {c.get('navegador','-')} | {c.get('aviso_cerrado') or 'no'} |")
    md.append("\nCada perfil se capturó en dos estados: primer acceso y página navegable, luego de cerrar avisos y recorrer la página para forzar contenido diferido.\n")
    md += ["## 3. Control positivo\n", "Superado.\n" if control_ok else "**FALLIDO.**\n",
           "El control positivo se aplicó a los documentos principales. Los iframes se preservaron y se incluyeron en búsquedas, pero no invalidan la captura principal.\n"]
    md += ["## 4. Búsquedas textuales dirigidas\n", "| Término | Documento | Coincidencias |", "|---|---|---|"]
    for r in busquedas:
        md.append(f"| {r['termino']} | {r['documento']} | {r['coincidencias']} |")
    md += ["", "## 5. Respuesta preliminar a los puntos periciales\n",
           f"**Punto 1.** {veredicto} la existencia, en la página de inicio, de una sección denominada \"Contratos de adhesión – Ley N° 24.240 de Defensa del Consumidor\". [[VERIFICAR VISUALMENTE LAS CAPTURAS DEL ESTADO 2 ANTES DE DAR POR FIRME]].\n",
           f"**Punto 2.** Se inventariaron {len(enlaces)} enlaces únicos y se consolidaron {len(paginas)} contenidos publicados según sitemap/API, cuando estuvieron disponibles.\n",
           "**Punto 3.** Se acompañan capturas de la página de inicio en perfiles escritorio y móvil, con URL, fecha, hora e integridad SHA-256.\n",
           "## 6. Reservas y limitaciones técnicas\n",
           "- La constatación refleja el estado del sitio únicamente en la fecha y hora consignadas; el contenido web es mutable.\n- La verificación fue del lado cliente, sin acceso a servidores ni registros internos.\n- Sitemaps, API REST, enlaces internos y archivo web son elementos auxiliares de localización y deben diferenciarse de la constatación visual.\n"]
    if revision_enlaces is not None:
        con_interes = [x for x in revision_enlaces if x.get("terminos_hallados") or x.get("pdf_enlazados")]
        md.append(f"Se revisaron {len(revision_enlaces)} enlaces internos; {len(con_interes)} presentaron términos de interés o enlaces PDF. [[REVISAR INDIVIDUALMENTE LOS HALLAZGOS]].\n")
    if alertas:
        md.append("## 7. Incidencias registradas durante la diligencia\n")
        for a in alertas:
            md.append(f"- {a}")
    md += ["", "---\n", "> Borrador generado automáticamente. Requiere revisión visual y eliminación de los marcadores `[[...]]` antes de su presentación.\n"]
    guardar_texto(base / "INFORME_TECNICO_BORRADOR.md", "\n".join(md)); log("Borrador de informe generado")


def main():
    ap = argparse.ArgumentParser(description="Relevamiento forense de sitio web para constatación pericial.")
    ap.add_argument("--url", required=True)
    ap.add_argument("--salida", default="./EVIDENCIA")
    ap.add_argument("--causa", default="[[completar]]")
    ap.add_argument("--perito", default="[[completar]]")
    ap.add_argument("--terminos", help="Archivo con un término de búsqueda por línea")
    ap.add_argument("--control", help="Términos de control positivo separados por coma")
    ap.add_argument("--revisar-enlaces", action="store_true")
    ap.add_argument("--limite-enlaces", type=int, default=100)
    ap.add_argument("--fechas-archivo", default="", help="Fechas YYYYMMDD separadas por coma para Wayback")
    ap.add_argument("--sin-navegador", action="store_true")
    args = ap.parse_args()

    sello = ahora().strftime("%Y%m%d_%H%M%S"); base = Path(args.salida) / f"RELEVAMIENTO_{sello}"
    for sub in SUBDIRECTORIOS:
        (base / sub).mkdir(parents=True, exist_ok=True)
    log = Bitacora(base / "00_LOG_DILIGENCIA.txt")
    try:
        log("=" * 70); log(f"INICIO DE LA DILIGENCIA DE RELEVAMIENTO — herramienta v{VERSION}")
        log(f"URL objeto: {args.url}"); log(f"Directorio de evidencia: {base.resolve()}"); log("=" * 70)
        hash_script = sha256_archivo(Path(__file__)); log(f"SHA-256 de la herramienta utilizada: {hash_script}")
        host = urlparse(args.url).netloc
        terminos = list(TERMINOS_POR_DEFECTO)
        if args.terminos:
            terminos = [l.strip() for l in Path(args.terminos).read_text(encoding="utf-8").splitlines() if l.strip()]
            log(f"Términos cargados desde {args.terminos}: {len(terminos)}")
        entorno = relevar_entorno(base, log, args.url, args.causa, args.perito, hash_script)
        relevar_dns(base, log, host); relevar_rdap(base, log, host); relevar_tls(base, log, host)
        fuente, _ = relevar_http(base, log, args.url)
        log("Descubriendo sitemaps declarados"); urls_sitemap = descubrir_sitemaps(base, log, args.url)
        log("Enumerando contenidos publicados vía API REST"); paginas_api = enumerar_api_rest(base, log, args.url)
        paginas = volcar_paginas_publicadas(base, log, urls_sitemap, paginas_api, TERMINOS_DOCUMENTACION)

        capturas, enlaces_unicos = [], []
        documentos_busqueda = {"código fuente sin renderizar": fuente}
        documentos_control = {"código fuente sin renderizar": fuente}
        marcos_meta_total = []

        if args.sin_navegador:
            log("Capturas con navegador omitidas por --sin-navegador", "WARN")
        elif not PLAYWRIGHT_DISPONIBLE:
            log("Playwright no instalado: pip install playwright && playwright install chromium", "ERROR")
        else:
            dispositivos = [
                ("escritorio", None),
                ("movil", {
                    "viewport": {"width": 390, "height": 844}, "device_scale_factor": 3,
                    "is_mobile": True, "has_touch": True,
                    "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
                }),
            ]
            todos_enlaces = []
            for perfil, disp in dispositivos:
                try:
                    res = capturar_con_navegador(base, log, args.url, perfil, disp); capturas.append(res)
                    nombre_dom = f"DOM renderizado ({perfil})"
                    documentos_busqueda[nombre_dom] = res["dom"]; documentos_control[nombre_dom] = res["dom"]
                    documentos_busqueda.update(res["marcos"]); marcos_meta_total.extend(res["marcos_meta"])
                    todos_enlaces.extend(res["enlaces"])
                except Exception as e:
                    log(f"[{perfil}] Fallo en la captura: {e}", "ERROR")
            if todos_enlaces:
                enlaces_unicos = volcar_enlaces(base, log, todos_enlaces, host)

        control_ok = control_positivo(base, log, documentos_control, derivar_control(args.url, fuente, args.control), marcos_meta_total)
        busquedas = buscar_terminos(base, log, documentos_busqueda, terminos)
        inyectados = comparar_fuente_dom(base, log, fuente, capturas, terminos) if capturas else []
        revision_enlaces = None
        if args.revisar_enlaces and enlaces_unicos:
            revision_enlaces = revisar_enlaces_internos(base, log, enlaces_unicos, host, TERMINOS_DOCUMENTACION, args.limite_enlaces)
        if args.fechas_archivo:
            fechas = [f.strip() for f in args.fechas_archivo.split(",") if f.strip()]
            relevar_archivo_web(base, log, args.url, fechas)
        generar_informe(base, log, entorno, capturas, busquedas, enlaces_unicos, paginas, control_ok, inyectados, log.alertas, revision_enlaces)
        generar_manifiesto(base, log)
        log("=" * 70); log("CIERRE DE LA DILIGENCIA")
        if log.alertas:
            log(f"Se registraron {len(log.alertas)} incidencia(s); revisar antes de presentar")
        else:
            log("Diligencia finalizada sin incidencias críticas")
        log(f"Paquete de evidencia: {base.resolve()}"); log("=" * 70)
    finally:
        log.cerrar()


if __name__ == "__main__":
    main()

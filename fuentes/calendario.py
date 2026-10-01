# -*- coding: utf-8 -*-
"""
CALENDARIO — la lista cerrada de anuncios del pre-registro (4.8), armada desde
las fuentes oficiales. No tiene precios.

Salidas (versionadas):
  calendario/anuncios.csv    una fila por anuncio que cuenta:
      t_utc        instante de publicacion, en UTC
      tipo         fomc, empleo, ipc o bce (los nombres que usa el motor)
      fecha_local, hora_local, zona   la hora en el reloj de la fuente
      fuente_hora  de donde sale la hora (comunicado, minutas o regla publicada)
      url          el comunicado
  calendario/excluidos.csv   lo que aparece en las fuentes y NO cuenta, con el
                             motivo (no programado, cancelado, sin comunicado).
  calendario/pendientes.csv  anuncios que SI cuentan pero cuya hora no aparece
                             en la fuente oficial. No entran a anuncios.csv
                             hasta que el grupo decida (no se adivina la hora).

Reglas (pre-registro 4.8):
  - Fed: comunicados de las reuniones PROGRAMADAS del FOMC, desde las paginas
    historicas de cada ano. No cuentan las conferencias telefonicas ni lo que
    la Fed marca "(unscheduled)", "(cancelled)" o "(notation vote)", ni una
    reunion sin comunicado. La hora sale del comunicado ("For release at 2:15
    p.m. EST"). Los mas antiguos dicen "For immediate release", sin hora:
    entonces sale de las minutas de esa misma reunion ("...statement to be
    released at 2:15 p.m."). Si tampoco las minutas la dicen (las de 2003
    dicen "to be released shortly after the meeting"), el anuncio va a
    pendientes.csv.
  - BLS: Employment Situation (empleo) y Consumer Price Index (ipc). La fecha
    real sale de las paginas de archivo de cada serie, que listan cada
    comunicado con su fecha de publicacion (tambien los atrasados, como los de
    octubre de 2013). La hora es la habitual, 8:30 ET, y se verifica en una
    muestra de comunicados (la linea de embargo de cada uno).
  - BCE: "Monetary policy decisions" de las reuniones programadas, desde la
    lista por ano de ecb.europa.eu. El comunicado no dice su hora: se usa la
    regla publicada del BCE (13:45 CET; 14:15 desde el 21-07-2022). Las
    reuniones de politica monetaria son los jueves; una decision en otro dia
    es no programada (por ejemplo, el recorte coordinado del 08-10-2008) y va
    a excluidos.csv.
  - Conversion a UTC con la base de zonas fijada (tzdata 2026.4):
    America/New_York para la Fed y el BLS, Europe/Berlin para el BCE.

Las paginas se guardan en RUTA_CRUDOS/calendario/ (para retomar y para
reproducir) y su huella entra al manifiesto. Hay una pausa entre pedidos. El
BLS pide que un programa se identifique con un contacto: sale de la variable
de entorno CUARTINHOS_CONTACTO y no se escribe en ningun archivo.

Uso:
    python -m fuentes.calendario        (con CUARTINHOS_CONTACTO definida)
"""
import argparse
import datetime as dt
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                   # noqa: E402
from fuentes import manifiesto  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join("calendario", "anuncios.csv")
SALIDA_EXCLUIDOS = os.path.join("calendario", "excluidos.csv")
SALIDA_PENDIENTES = os.path.join("calendario", "pendientes.csv")
COLUMNAS = ["t_utc", "tipo", "fecha_local", "hora_local", "zona", "fuente_hora", "url"]

FED = "https://www.federalreserve.gov"
BLS = "https://www.bls.gov"
BCE = "https://www.ecb.europa.eu"
AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Cuartinhos_EURUSD/1.0 "
          "(tesis academica; calendario de anuncios)")

_MESES = {m: k for k, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


class CalendarioError(RuntimeError):
    """Una fuente no trae lo que se espera; mejor detenerse que adivinar."""


# -----------------------------------------------------------------------------
#  Pedidos, con copia local
# -----------------------------------------------------------------------------
def agente(con_contacto=False):
    """User-Agent. Con contacto (BLS), lo lee de CUARTINHOS_CONTACTO."""
    if not con_contacto:
        return AGENTE
    contacto = os.environ.get("CUARTINHOS_CONTACTO", "").strip()
    if not contacto:
        raise CalendarioError("el BLS pide un contacto: defina la variable de entorno "
                              "CUARTINHOS_CONTACTO antes de correr")
    return f"Cuartinhos_EURUSD/1.0 (tesis academica; calendario de anuncios; contacto: {contacto})"


def _nombre_local(url):
    partes = urllib.parse.urlsplit(url)
    return re.sub(r"[^A-Za-z0-9._-]+", "_", partes.netloc + partes.path)


def pagina(url, cfg=None, repo=None, con_contacto=False):
    """Texto de una pagina; la baja (con pausa y reintentos) solo si no esta guardada."""
    cfg = cfg or config
    carpeta = os.path.join(cfg.RUTA_CRUDOS, "calendario")
    ruta = os.path.join(carpeta, _nombre_local(url))
    if not os.path.exists(ruta):
        os.makedirs(carpeta, exist_ok=True)
        pedido = urllib.request.Request(url, headers={"User-Agent": agente(con_contacto)})
        for intento in range(1, cfg.DESCARGA_REINTENTOS + 1):
            try:
                with urllib.request.urlopen(pedido, timeout=cfg.DESCARGA_TIMEOUT_SEG) as r:
                    contenido = r.read()
                break
            except Exception as error:
                if intento == cfg.DESCARGA_REINTENTOS:
                    raise CalendarioError(f"{url}: {error}") from error
                time.sleep(cfg.CALENDARIO_PAUSA_SEG * 2 ** intento)
        with open(ruta + ".parcial", "wb") as f:
            f.write(contenido)
        os.replace(ruta + ".parcial", ruta)
        manifiesto.registrar(ruta, "calendario", url, cfg=cfg, repo=repo)
        time.sleep(cfg.CALENDARIO_PAUSA_SEG)
    with open(ruta, encoding="utf-8", errors="replace") as f:
        return f.read()


def _texto(html):
    """El texto visible, con los espacios juntados."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def a_utc(fecha, hora, minuto, zona):
    """Una hora local de la fuente, en UTC."""
    local = pd.Timestamp(dt.datetime.combine(fecha, dt.time(hora, minuto)))
    return local.tz_localize(zona).tz_convert("UTC")


def _hora_12(h, m, ampm):
    h = int(h) % 12 + (12 if ampm.lower() == "p" else 0)
    return h, int(m)


# -----------------------------------------------------------------------------
#  Fed
# -----------------------------------------------------------------------------
def reuniones_fomc(html):
    """
    Las reuniones de una pagina historica del FOMC: titulo, si es programada,
    y los enlaces del comunicado y de las minutas (HTML).
    """
    titulos = re.findall(r"<h5[^>]*>(.*?)</h5>", html, re.S)
    cuerpos = re.split(r"<h5[^>]*>.*?</h5>", html, flags=re.S)[1:]
    salida = []
    for titulo, cuerpo in zip(titulos, cuerpos):
        titulo = _texto(titulo)
        enlaces = [(_texto(t), u) for u, t in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', cuerpo, re.S)]
        comunicado = next((u for t, u in enlaces if t == "Statement"), None)
        minutas = next((u for t, u in enlaces
                        if t.startswith("Minutes") and u.endswith(".htm") and "minutes" in u.lower()), None)
        if minutas is None:
            minutas = next((u for t, u in enlaces if t == "HTML" and "minutes" in u.lower()), None)
        programada = ("Meeting" in titulo and "(" not in titulo and "Conference Call" not in titulo)
        salida.append({"titulo": titulo, "programada": programada,
                       "comunicado": comunicado, "minutas": minutas})
    return salida


_FECHA_URL_FED = re.compile(r"(?:monetary|/)(\d{4})(\d{2})(\d{2})(?:a\.htm|/default\.htm|/)$")


def fecha_de_url_fomc(url):
    m = _FECHA_URL_FED.search(url)
    if not m:
        raise CalendarioError(f"no reconozco la fecha en {url}")
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def hora_del_comunicado(html):
    """(hora, minuto) de "For release at 2:15 p.m. EST", o None si no la dice."""
    m = re.search(r"For release at (\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?", _texto(html), re.I)
    return _hora_12(*m.groups()) if m else None


def hora_de_las_minutas(html):
    """(hora, minuto) de "...statement to be released at 2:15 p.m.", o None."""
    m = re.search(r"released at (\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?", _texto(html), re.I)
    return _hora_12(*m.groups()) if m else None


def fecha_del_comunicado(html):
    """La fecha de "Release Date: January 27, 2016", o None."""
    m = re.search(r"Release Date:\s*([A-Za-z]+) (\d{1,2}), (\d{4})", _texto(html))
    if not m or m.group(1).lower() not in _MESES:
        return None
    return dt.date(int(m.group(3)), _MESES[m.group(1).lower()], int(m.group(2)))


def fomc(cfg, repo):
    anuncios, excluidos, pendientes = [], [], []
    for anio in range(cfg.CALENDARIO_ANIOS[0], cfg.CALENDARIO_ANIOS[1] + 1):
        url_anio = f"{FED}/monetarypolicy/fomchistorical{anio}.htm"
        for r in reuniones_fomc(pagina(url_anio, cfg, repo)):
            if not r["programada"] or r["comunicado"] is None:
                motivo = "no programada" if not r["programada"] else "sin comunicado"
                excluidos.append({"tipo": "fomc", "fecha": r["titulo"], "motivo": motivo,
                                  "url": url_anio})
                continue
            url = urllib.parse.urljoin(FED, r["comunicado"])
            fecha = fecha_de_url_fomc(url)
            html = pagina(url, cfg, repo)
            declarada = fecha_del_comunicado(html)
            if declarada is not None and declarada != fecha:
                raise CalendarioError(f"{url}: la fecha del enlace ({fecha}) y la del "
                                      f"comunicado ({declarada}) no coinciden")
            hora, fuente_hora = hora_del_comunicado(html), "comunicado"
            url_minutas = urllib.parse.urljoin(FED, r["minutas"]) if r["minutas"] else ""
            if hora is None and url_minutas:
                hora = hora_de_las_minutas(pagina(url_minutas, cfg, repo))
                fuente_hora = "minutas de la reunion"
            if hora is None:
                pendientes.append({"tipo": "fomc", "fecha_local": fecha.isoformat(),
                                   "motivo": "ni el comunicado ni las minutas dicen la hora",
                                   "url": url, "url_minutas": url_minutas})
                continue
            anuncios.append(_fila(fecha, hora, "fomc", cfg.CALIDAD_ZONA_NUEVA_YORK,
                                  fuente_hora, url))
    return anuncios, excluidos, pendientes


# -----------------------------------------------------------------------------
#  BLS
# -----------------------------------------------------------------------------
SERIES_BLS = {"empleo": "empsit", "ipc": "cpi"}


def comunicados_bls(html, serie):
    """Fechas de publicacion y enlaces (HTML) de la pagina de archivo de una serie."""
    vistos = {}
    for url, mes, dia, anio in re.findall(
            rf'href="(/news\.release/archives/{serie}_(\d{{2}})(\d{{2}})(\d{{4}})\.htm)"', html):
        vistos[dt.date(int(anio), int(mes), int(dia))] = url
    return sorted(vistos.items())


def verificar_hora_bls(html):
    """True si la linea de embargo del comunicado dice 8:30 a.m."""
    return bool(re.search(r"8:30\s*a\.?\s*m\.?", _texto(html), re.I))


def bls(cfg, repo):
    anuncios, verificados = [], []
    hora = tuple(cfg.HORA_BLS)
    for tipo, serie in SERIES_BLS.items():
        url_archivo = f"{BLS}/bls/news-release/{serie}.htm"
        lista = [(f, u) for f, u in comunicados_bls(pagina(url_archivo, cfg, repo, con_contacto=True), serie)
                 if cfg.CALENDARIO_ANIOS[0] <= f.year <= cfg.CALENDARIO_ANIOS[1]]
        for fecha, url in lista:
            anuncios.append(_fila(fecha, hora, tipo, cfg.CALIDAD_ZONA_NUEVA_YORK,
                                  "hora habitual de la serie (8:30 ET), verificada en una muestra",
                                  urllib.parse.urljoin(BLS, url)))
        # Muestra: el primer comunicado de cada ano elegido, y los de octubre de
        # 2013 (atrasados por el cierre del gobierno de EE. UU.).
        muestra = [next((f, u) for f, u in lista if f.year == a) for a in cfg.VERIFICACION_BLS_ANIOS
                   if any(f.year == a for f, _ in lista)]
        muestra += [(f, u) for f, u in lista if f.year == 2013 and f.month == 10]
        for fecha, url in muestra:
            html = pagina(urllib.parse.urljoin(BLS, url), cfg, repo, con_contacto=True)
            verificados.append({"tipo": tipo, "fecha": fecha, "dice_8_30": verificar_hora_bls(html),
                                "url": urllib.parse.urljoin(BLS, url)})
    return anuncios, verificados


# -----------------------------------------------------------------------------
#  BCE
# -----------------------------------------------------------------------------
def decisiones_bce(html):
    """(fecha, titulo, enlace) de cada entrada de la lista anual del BCE."""
    salida = []
    for iso, cuerpo in re.findall(r'<dt isoDate="(\d{4}-\d{2}-\d{2})">.*?</dt>\s*<dd>(.*?)</dd>', html, re.S):
        m = re.search(r'<div class="title"><a href="([^"]+)"[^>]*>(.*?)</a>', cuerpo, re.S)
        if m:
            salida.append((dt.date.fromisoformat(iso), _texto(m.group(2)), m.group(1)))
    return salida


def hora_bce(fecha, cfg):
    desde, hora_nueva = cfg.HORA_BCE_DESDE_2022
    return tuple(hora_nueva) if fecha >= dt.date.fromisoformat(desde) else tuple(cfg.HORA_BCE)


def bce(cfg, repo):
    anuncios, excluidos = [], []
    for anio in range(cfg.CALENDARIO_ANIOS[0], cfg.CALENDARIO_ANIOS[1] + 1):
        url_anio = f"{BCE}/press/govcdec/mopo/{anio}/html/index_include.en.html"
        for fecha, titulo, enlace in decisiones_bce(pagina(url_anio, cfg, repo)):
            url = urllib.parse.urljoin(BCE, enlace)
            if "monetary policy decision" not in titulo.lower():
                excluidos.append({"tipo": "bce", "fecha": fecha.isoformat(), "motivo":
                                  f"no es una decision de politica monetaria: {titulo}", "url": url})
                continue
            if fecha.weekday() != 3:
                excluidos.append({"tipo": "bce", "fecha": fecha.isoformat(), "motivo":
                                  "no programada (no es jueves)", "url": url})
                continue
            anuncios.append(_fila(fecha, hora_bce(fecha, cfg), "bce", cfg.ZONA_BCE,
                                  "regla publicada del BCE (13:45 CET; 14:15 desde el 21-07-2022)", url))
    return anuncios, excluidos


# -----------------------------------------------------------------------------
#  Armado
# -----------------------------------------------------------------------------
def _fila(fecha, hora, tipo, zona, fuente_hora, url):
    t = a_utc(fecha, hora[0], hora[1], zona)
    return {"t_utc": t.strftime("%Y-%m-%dT%H:%MZ"), "tipo": tipo, "fecha_local": fecha.isoformat(),
            "hora_local": f"{hora[0]:02d}:{hora[1]:02d}", "zona": zona,
            "fuente_hora": fuente_hora, "url": url}


def armar(cfg=None, repo=None):
    cfg = cfg or config
    repo = repo or RAIZ
    agente(con_contacto=True)          # falla antes de pedir nada si falta el contacto
    fed, fed_fuera, pendientes = fomc(cfg, repo)
    bls_filas, verificados = bls(cfg, repo)
    bce_filas, bce_fuera = bce(cfg, repo)
    anuncios = pd.DataFrame(fed + bls_filas + bce_filas, columns=COLUMNAS)
    anuncios = anuncios.sort_values(["t_utc", "tipo"]).reset_index(drop=True)
    if anuncios.duplicated(["t_utc", "tipo"]).any():
        raise CalendarioError("hay anuncios repetidos")
    excluidos = pd.DataFrame(fed_fuera + bce_fuera, columns=["tipo", "fecha", "motivo", "url"])
    pendientes = pd.DataFrame(pendientes, columns=["tipo", "fecha_local", "motivo", "url", "url_minutas"])
    return anuncios, excluidos, pd.DataFrame(verificados), pendientes


def main(argv=None):
    argparse.ArgumentParser(description="Calendario de anuncios (pre-registro 4.8)").parse_args(argv)
    anuncios, excluidos, verificados, pendientes = armar()
    os.makedirs(os.path.join(RAIZ, "calendario"), exist_ok=True)
    anuncios.to_csv(os.path.join(RAIZ, SALIDA), index=False, lineterminator="\n")
    excluidos.to_csv(os.path.join(RAIZ, SALIDA_EXCLUIDOS), index=False, lineterminator="\n")
    pendientes.to_csv(os.path.join(RAIZ, SALIDA_PENDIENTES), index=False, lineterminator="\n")
    anios = pd.to_datetime(anuncios["t_utc"]).dt.year
    print(pd.crosstab(anios, anuncios["tipo"]).to_string())
    print("\nExcluidos:\n" + excluidos.to_string(index=False))
    print("\nVerificacion de la hora del BLS:\n" + verificados.to_string(index=False))
    print("\nHoras locales por tipo:\n" + anuncios.groupby(["tipo", "hora_local", "fuente_hora"])
          .size().to_string())
    print(f"\nPENDIENTES (hora no dicha por la fuente): {len(pendientes)}\n"
          + (pendientes.to_string(index=False) if len(pendientes) else ""))


if __name__ == "__main__":
    main()

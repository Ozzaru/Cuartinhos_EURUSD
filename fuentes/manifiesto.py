# -*- coding: utf-8 -*-
"""
MANIFIESTO — registro versionado de los archivos crudos.

`registro/manifiesto_datos.csv` tiene una fila por archivo crudo: su ruta
relativa a RUTA_CRUDOS, la fuente, de donde salio (URL o exportacion manual),
la fecha de descarga en UTC, el tamano y el sha256. No trae precios: es lo
unico de los datos que va al repositorio. Sirve para dos cosas:

  - probar que los crudos siguen sin modificar: el cargador no convierte un
    archivo que no este en el manifiesto o cuyo tamano o sha256 no calce;
  - reproducir: cualquiera puede bajar lo mismo y comparar las huellas.

Aqui los archivos de precios se leen como bytes, solo para calcular la huella.
Nunca se interpretan.

Proteccion del sellado (incidente del 2026-10-01): un CSV de Dukascopy se
registra solo si su NOMBRE declara una fecha final anterior al inicio del
sellado. Se revisa antes de calcular la huella, o sea sin leer el archivo. Un
nombre sin fecha final reconocible tambien se rechaza.

Uso:
    python -m fuentes.manifiesto --registrar-manuales dukascopy
    python -m fuentes.manifiesto --verificar
"""
import argparse
import csv
import datetime as dt
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVO = os.path.join("registro", "manifiesto_datos.csv")
CAMPOS = ["archivo", "fuente", "url", "fecha_descarga_utc", "tamano_bytes", "sha256"]

# Origen que se anota para los CSV de Dukascopy, que se exportan a mano (los
# terminos de uso de dukascopy.com prohiben la descarga automatica).
ORIGEN_JFOREX = ("exportacion manual: JForex, Historical Data Manager (cuenta demo), "
                 "EUR/USD 1 minuto, hora UTC, sin filtro de velas planas")


class ManifiestoError(RuntimeError):
    """Un crudo no esta registrado, o cambio desde que se registro."""


class SelladoError(PermissionError):
    """Se pidio algo del tramo sellado (o posterior) antes de la Etapa 5."""


# Fecha final en el nombre de una exportacion de Dukascopy:
#   JForex:          ..._AAAA.MM.DD_AAAA.MM.DD.csv   (EURUSD_1 Min_Bid_2003.05.04_2020.12.31.csv)
#   exportador web:  ..._DD.MM.AAAA-DD.MM.AAAA.csv   (EURUSD_Candlestick_1_M_BID_01.01.2016-31.01.2016.csv)
_FIN_JFOREX = re.compile(r"_\d{4}\.\d{2}\.\d{2}_(\d{4})\.(\d{2})\.(\d{2})\.csv$", re.IGNORECASE)
_FIN_WEB = re.compile(r"_\d{2}\.\d{2}\.\d{4}-(\d{2})\.(\d{2})\.(\d{4})\.csv$", re.IGNORECASE)


def fecha_final_en_nombre(nombre):
    """La fecha final que declara el nombre de una exportacion de Dukascopy, o None."""
    m = _FIN_JFOREX.search(nombre)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _FIN_WEB.search(nombre)
    if m:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def exigir_nombre_antes_del_sellado(ruta, cfg=None):
    """
    Rechaza, SIN abrirlo, un crudo de Dukascopy cuyo nombre no declare una
    fecha final anterior a DESCARGA_TOPE (el inicio del sellado).
    """
    cfg = cfg or config
    nombre = os.path.basename(ruta)
    fin = fecha_final_en_nombre(nombre)
    tope = dt.date.fromisoformat(cfg.DESCARGA_TOPE)
    if fin is None:
        raise SelladoError(f"{nombre}: el nombre no dice hasta que fecha llega; no se registra "
                           "ni se lee (se exige una fecha final anterior al sellado)")
    if fin >= tope:
        raise SelladoError(f"{nombre}: el nombre dice que llega al {fin}, desde el {tope} es el "
                           "tramo sellado. No se registra ni se lee: hay que borrarlo y re-exportar.")


def sha256(ruta):
    """Huella sha256 del archivo, leido por bloques."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def relativa(ruta, cfg=None):
    """Ruta de un crudo relativa a RUTA_CRUDOS, con barras normales."""
    cfg = cfg or config
    return os.path.relpath(ruta, cfg.RUTA_CRUDOS).replace("\\", "/")


def leer(repo=None):
    """El manifiesto como diccionario {archivo: fila}."""
    ruta = os.path.join(repo or RAIZ, ARCHIVO)
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8", newline="") as f:
        return {fila["archivo"]: fila for fila in csv.DictReader(f)}


def _escribir(filas, repo=None):
    ruta = os.path.join(repo or RAIZ, ARCHIVO)
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS, lineterminator="\n")
        escritor.writeheader()
        for clave in sorted(filas):
            escritor.writerow(filas[clave])


def registrar(ruta, fuente, url, fecha_utc=None, cfg=None, repo=None):
    """Agrega (o reemplaza) la fila de un crudo y devuelve esa fila."""
    if fuente == "dukascopy":
        exigir_nombre_antes_del_sellado(ruta, cfg)      # antes de leer un solo byte
    filas = leer(repo)
    fila = {
        "archivo": relativa(ruta, cfg),
        "fuente": fuente,
        "url": url,
        "fecha_descarga_utc": fecha_utc or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tamano_bytes": str(os.path.getsize(ruta)),
        "sha256": sha256(ruta),
    }
    filas[fila["archivo"]] = fila
    _escribir(filas, repo)
    return fila


def registrado(ruta, cfg=None, repo=None):
    """True si el archivo esta en el manifiesto con el mismo tamano y sha256."""
    fila = leer(repo).get(relativa(ruta, cfg))
    return (fila is not None
            and int(fila["tamano_bytes"]) == os.path.getsize(ruta)
            and fila["sha256"] == sha256(ruta))


def verificar(ruta, cfg=None, repo=None):
    """Levanta ManifiestoError si el crudo no esta registrado o cambio."""
    fila = leer(repo).get(relativa(ruta, cfg))
    if fila is None:
        raise ManifiestoError(f"{ruta} no esta en {ARCHIVO}: registrelo antes de convertirlo")
    if int(fila["tamano_bytes"]) != os.path.getsize(ruta) or fila["sha256"] != sha256(ruta):
        raise ManifiestoError(f"{ruta} cambio desde que se registro: los crudos no se modifican")


def registrar_manuales(fuente, origen=ORIGEN_JFOREX, cfg=None, repo=None):
    """
    Registra los crudos de una fuente que se exportaron a mano y todavia no
    estan en el manifiesto. La fecha de descarga es la de modificacion del
    archivo (la exportacion), en UTC.
    """
    cfg = cfg or config
    carpeta = os.path.join(cfg.RUTA_CRUDOS, fuente)
    ya = leer(repo)
    candidatos = [os.path.join(carpeta, n) for n in sorted(os.listdir(carpeta))]
    candidatos = [r for r in candidatos if os.path.isfile(r) and relativa(r, cfg) not in ya]
    if fuente == "dukascopy":
        # Todos los nombres se revisan antes de leer nada: si uno llega al
        # sellado, no se registra ninguno.
        malos = []
        for ruta in candidatos:
            try:
                exigir_nombre_antes_del_sellado(ruta, cfg)
            except SelladoError as error:
                malos.append(str(error))
        if malos:
            raise SelladoError("no se registro nada:\n  " + "\n  ".join(malos))
    nuevas = []
    for ruta in candidatos:
        fecha = dt.datetime.fromtimestamp(os.path.getmtime(ruta), dt.timezone.utc)
        nuevas.append(registrar(ruta, fuente, origen, fecha.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                cfg, repo))
    return nuevas


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manifiesto de los datos crudos")
    parser.add_argument("--registrar-manuales", metavar="FUENTE")
    parser.add_argument("--verificar", action="store_true")
    args = parser.parse_args(argv)
    if args.registrar_manuales:
        for fila in registrar_manuales(args.registrar_manuales):
            print(f"registrado: {fila['archivo']}  {fila['tamano_bytes']} bytes  {fila['sha256'][:16]}")
    if args.verificar:
        malos = 0
        for archivo in leer():
            ruta = os.path.join(config.RUTA_CRUDOS, archivo)
            ok = os.path.exists(ruta) and registrado(ruta)
            malos += not ok
            print(f"{'ok ' if ok else 'MAL'}  {archivo}")
        if malos:
            raise SystemExit(f"{malos} archivos no calzan con el manifiesto")


if __name__ == "__main__":
    main()

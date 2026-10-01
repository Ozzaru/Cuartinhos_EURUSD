# -*- coding: utf-8 -*-
"""
El candado del punto G (pre-registro 2.4; regla 3 del punto G).

  - Mientras no exista la etiqueta prerregistro-v1, el cargador rechaza todo lo
    que no sea el modulo de calidad, en cualquier tramo.
  - Cada lectura de calidad que toca validacion queda anotada en
    registro/aperturas.md y exige el arbol de git limpio.
  - Con la etiqueta, rige la seccion 2.4: abrir validacion o el sellado exige
    la bandera y deja una linea "apertura".
  - El modulo de calidad no importa resultados, nula ni inferencia, y ninguna
    salida suya trae retornos posteriores ni los tipos sostenida o reingreso.
  - Nada desde el inicio del sellado se descarga ni se convierte.

Todo corre sobre precios SIMULADOS escritos como si fueran los procesados, en
carpetas temporales y con un repositorio de git temporal.
"""
import ast
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

import ayuda
from fuentes import calidad, cargador, descarga_histdata
from simulacion import mercado

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# -----------------------------------------------------------------------------
#  Fixtures: un repositorio de git y datos procesados falsos
# -----------------------------------------------------------------------------
def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    raiz = tmp_path / "repo"
    (raiz / "registro").mkdir(parents=True)
    (raiz / "registro" / "LEEME.md").write_text("repositorio de prueba\n", encoding="utf-8")
    _git(str(raiz), "init", "-q")
    _git(str(raiz), "config", "user.name", "Prueba")
    _git(str(raiz), "config", "user.email", "prueba@ejemplo.invalid")
    _git(str(raiz), "config", "commit.gpgsign", "false")
    _git(str(raiz), "add", "-A")
    _git(str(raiz), "commit", "-q", "-m", "inicio")
    return str(raiz)


def _procesados_falsos(carpeta, datos, anio):
    """Escribe un ano simulado como si fueran los parquet de las dos fuentes."""
    datos = datos[datos.index.year == anio]
    duka = datos.copy()
    for x in ("open", "high", "low", "close"):
        duka[f"mid_{x}"] = (datos[f"bid_{x}"] + datos[f"ask_{x}"]) / 2.0
    duka["bid_volumen"] = 1.0
    duka["ask_volumen"] = 1.0
    hist = datos[[f"bid_{x}" for x in ("open", "high", "low", "close")]].copy()
    hist["volumen"] = 0.0
    for fuente, tabla in (("dukascopy", duka[cargador.COLUMNAS_DUKASCOPY]),
                          ("histdata", hist[cargador.COLUMNAS_HISTDATA])):
        os.makedirs(os.path.join(carpeta, fuente), exist_ok=True)
        tabla.index.name = "apertura_utc"
        tabla.to_parquet(os.path.join(carpeta, fuente, f"{fuente}_EURUSD_M1_{anio}.parquet"))


@pytest.fixture(scope="module")
def procesados(tmp_path_factory):
    carpeta = str(tmp_path_factory.mktemp("procesados"))
    cfg = ayuda.cfg_prueba()
    for anio in (2016, 2017):
        datos, _ = mercado.generar(1, cfg.SEMILLA + anio, cfg, inicio=f"{anio}-01-01")
        _procesados_falsos(carpeta, datos, anio)
    return carpeta


@pytest.fixture
def cfg(procesados):
    return ayuda.cfg_prueba(RUTA_PROCESADOS=procesados)


def _aperturas(repo):
    ruta = os.path.join(repo, cargador.REGISTRO_APERTURAS)
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as f:
        return [l for l in f if l.startswith("| 20")]


# -----------------------------------------------------------------------------
#  Tramos
# -----------------------------------------------------------------------------
def test_tramos_en_los_bordes(cfg):
    assert cargador.tramos("2016-12-31", "2016-12-31", cfg) == ["desarrollo"]
    assert cargador.tramos("2016-12-29", "2017-01-01", cfg) == ["desarrollo", "validacion"]
    assert cargador.tramos("2017-01-01", "2020-12-31", cfg) == ["validacion"]
    assert cargador.tramos("2020-12-31", "2021-01-01", cfg) == ["validacion", "sellado"]
    assert cargador.tramos("2003-05-04", "2016-12-31", cfg) == ["desarrollo"]
    assert cargador.tramos("2010-01-01", "2026-08-31", cfg) == ["desarrollo", "validacion", "sellado"]


# -----------------------------------------------------------------------------
#  Sin etiqueta: solo el modulo de calidad
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("proposito", ["analisis", "resultados", "nula", "inferencia", "exploracion"])
@pytest.mark.parametrize("rango", [("2016-01-04", "2016-01-08"), ("2017-01-02", "2017-01-06")])
def test_sin_etiqueta_el_cargador_rechaza_todo_lo_que_no_sea_calidad(cfg, repo, proposito, rango):
    for abrir in (None, "validacion"):
        with pytest.raises(cargador.CandadoError):
            cargador.leer("dukascopy", *rango, proposito=proposito, abrir=abrir, cfg=cfg, repo=repo)
    assert _aperturas(repo) == []


def test_el_proposito_calidad_solo_lo_puede_usar_el_modulo_de_calidad(cfg, repo):
    with pytest.raises(cargador.CandadoError, match="fuentes.calidad"):
        cargador.leer("dukascopy", "2016-01-04", "2016-01-08", proposito="calidad", cfg=cfg, repo=repo)
    assert _aperturas(repo) == []


def test_la_calidad_lee_desarrollo_sin_anotar(cfg, repo):
    tablas = calidad.correr("2016-01-04", "2016-01-29", cfg=cfg, repo=repo)
    assert len(tablas["barras"]) == 2
    assert _aperturas(repo) == []


def test_la_lectura_de_calidad_de_validacion_queda_anotada(cfg, repo):
    calidad.correr("2017-01-02", "2017-01-27", cfg=cfg, repo=repo)
    lineas = _aperturas(repo)
    assert len(lineas) == 2, "una linea por fuente"
    commit = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    for linea, fuente in zip(lineas, ("dukascopy", "histdata")):
        campos = [c.strip() for c in linea.strip().strip("|").split("|")]
        fecha, clase, tramo, fte, proposito, rango, hash_, usuario = campos
        assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", fecha)
        assert (clase, tramo, fte, proposito) == ("lectura de calidad", "validacion", fuente, "calidad")
        assert rango == "2017-01-02 a 2017-01-27"
        assert hash_ == commit
        assert usuario == "Prueba"
    # La segunda corrida tambien pasa: el propio registro no ensucia el arbol.
    calidad.correr("2017-01-02", "2017-01-06", cfg=cfg, repo=repo)
    assert len(_aperturas(repo)) == 4


def test_el_registro_de_aperturas_solo_admite_lineas_agregadas(cfg, repo):
    calidad.correr("2017-01-02", "2017-01-06", cfg=cfg, repo=repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "cierre de sesion: registro de aperturas")
    ruta = os.path.join(repo, cargador.REGISTRO_APERTURAS)
    with open(ruta, encoding="utf-8") as f:
        original = f.read()
    # Agregar al final: pasa.
    calidad.correr("2017-01-02", "2017-01-06", cfg=cfg, repo=repo)
    assert len(_aperturas(repo)) == 4
    # Editar una linea ya commiteada: no pasa, y no se agrega nada.
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(original.replace("lectura de calidad", "lectura", 1))
    with pytest.raises(cargador.CandadoError, match="solo admite lineas agregadas"):
        calidad.correr("2017-01-02", "2017-01-06", cfg=cfg, repo=repo)
    assert len(_aperturas(repo)) == 2
    # Borrar el archivo: tampoco.
    os.remove(ruta)
    with pytest.raises(cargador.CandadoError, match="borrado"):
        calidad.correr("2017-01-02", "2017-01-06", cfg=cfg, repo=repo)


def test_la_lectura_de_validacion_exige_el_arbol_limpio(cfg, repo):
    with open(os.path.join(repo, "sin_commitear.py"), "w") as f:
        f.write("x = 1\n")
    with pytest.raises(cargador.CandadoError, match="no esta limpio"):
        calidad.correr("2017-01-02", "2017-01-06", cfg=cfg, repo=repo)
    assert _aperturas(repo) == [], "si no pasa, no se anota ni se entrega nada"
    # Desarrollo no lo exige.
    calidad.correr("2016-01-04", "2016-01-08", cfg=cfg, repo=repo)


def test_el_sellado_no_se_lee_ni_para_calidad(cfg, repo):
    with pytest.raises(cargador.CandadoError):
        calidad.correr("2021-01-04", "2021-01-08", cfg=cfg, repo=repo)
    with pytest.raises(cargador.CandadoError):
        calidad.correr("2020-12-28", "2021-01-08", cfg=cfg, repo=repo)


# -----------------------------------------------------------------------------
#  Con etiqueta: la seccion 2.4
# -----------------------------------------------------------------------------
def test_con_etiqueta_rige_la_seccion_2_4(cfg, repo):
    _git(repo, "tag", "-a", "prerregistro-v1", "-m", "congelamiento de prueba")
    # Desarrollo: libre, sin anotar, y llega limpio (sin planas ni invalidas).
    datos = cargador.leer("dukascopy", "2016-01-04", "2016-01-08", proposito="analisis",
                          cfg=cfg, repo=repo)
    assert len(datos) > 0 and _aperturas(repo) == []
    # Validacion sin bandera, o con la bandera equivocada: error.
    for abrir in (None, "sellado"):
        with pytest.raises(cargador.CandadoError):
            cargador.leer("dukascopy", "2017-01-02", "2017-01-06", proposito="analisis",
                          abrir=abrir, cfg=cfg, repo=repo)
    # Con la bandera: se abre y queda la linea "apertura".
    cargador.leer("dukascopy", "2017-01-02", "2017-01-06", proposito="analisis",
                  abrir="validacion", cfg=cfg, repo=repo)
    lineas = _aperturas(repo)
    assert len(lineas) == 1 and "| apertura | validacion | dukascopy | analisis |" in lineas[0]
    # Un rango que toca validacion y sellado no se abre de una vez.
    with pytest.raises(cargador.CandadoError):
        cargador.leer("dukascopy", "2020-12-28", "2021-01-08", proposito="analisis",
                      abrir="validacion", cfg=cfg, repo=repo)


# -----------------------------------------------------------------------------
#  El modulo de calidad: que importa y que devuelve
# -----------------------------------------------------------------------------
PROHIBIDOS = ("motor.resultados", "motor.nula", "motor.inferencia", "motor.eventos",
              "motor.moderadores", "motor.auditoria")


def test_calidad_no_importa_resultados_nula_ni_inferencia():
    # 1. En un proceso nuevo: importar el modulo de calidad no carga ninguno.
    codigo = ("import sys, fuentes.calidad; "
              "print(','.join(sorted(m for m in sys.modules if m.startswith('motor'))))")
    salida = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True,
                            text=True, check=True).stdout.strip().split(",")
    assert "motor.rupturas" in salida and "motor.franjas" in salida
    assert not set(salida) & set(PROHIBIDOS), salida
    # 2. En el texto: ningun import los nombra.
    for archivo in ("calidad.py", "cargador.py", "formatos.py"):
        with open(os.path.join(RAIZ, "fuentes", archivo), encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        nombres = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                nombres |= {a.name for a in nodo.names}
            elif isinstance(nodo, ast.ImportFrom):
                nombres |= {f"{nodo.module}.{a.name}" for a in nodo.names}
        assert not {n for n in nombres if n.startswith(PROHIBIDOS)}, (archivo, nombres)


def test_ninguna_salida_de_calidad_trae_retornos_posteriores_ni_otros_tipos(cfg, repo):
    tablas = calidad.correr("2016-01-04", "2016-02-26", cfg=cfg, repo=repo)
    texto = calidad.informe(tablas, "2016-01-04", "2016-02-26", cfg, 0.0)
    assert {"barras", "zona", "semanas", "rupturas", "extremos"} <= set(tablas)
    patron = re.compile(r"^(ret|r_)|retorno|posterior", re.IGNORECASE)
    for nombre, tabla in tablas.items():
        assert not [c for c in tabla.columns if patron.search(str(c))], nombre
        texto_tabla = tabla.astype(str).to_numpy().ravel()
        assert not any(v in ("sostenida", "reingreso") for v in texto_tabla), nombre
    for prohibida in ("sostenida", "reingreso", "retorno"):
        assert prohibida not in texto.lower()
    categorias = set(tablas["rupturas_matriz"]["dukascopy"]) | set(tablas["rupturas_matriz"]["histdata"])
    assert categorias <= {"sin ruptura", "alcista", "bajista", "ambigua"}


def test_con_el_mismo_bid_las_fuentes_coinciden_en_todo(cfg, repo):
    # Las dos fuentes falsas comparten el bid: zona en 0 y acuerdo total.
    tablas = calidad.correr("2016-01-04", "2016-02-26", cfg=cfg, repo=repo)
    zona = tablas["zona"].iloc[0]
    assert zona["desfase_del_maximo"] == 0 and zona["correlacion_en_0"] == pytest.approx(1.0)
    rup = tablas["rupturas"].iloc[0]
    assert rup["pct_acuerdo"] == 1.0 and rup["pct_misma_hora"] == 1.0
    assert rup["franjas_comparables"] > 100
    assert tablas["extremos"].iloc[0]["H_p95_abs"] == 0
    assert not tablas["semanas"]["fuera_de_rango"].any()
    assert tablas["barras"]["invalidas"].sum() == 0


@pytest.mark.parametrize("horas", [1, -3])
def test_un_desfase_de_horas_se_detecta(cfg, repo, tmp_path, horas):
    # HistData corrida una hora (horario de verano) o tres hacia atras (hora de
    # Chile): el barrido amplio lo encuentra siempre; la ventana de +-120 solo
    # si cae adentro.
    carpeta = str(tmp_path / "procesados")
    for fuente in ("dukascopy", "histdata"):
        os.makedirs(os.path.join(carpeta, fuente))
        origen = os.path.join(cfg.RUTA_PROCESADOS, fuente, f"{fuente}_EURUSD_M1_2016.parquet")
        tabla = pd.read_parquet(origen)
        if fuente == "histdata":
            tabla.index = tabla.index + pd.Timedelta(hours=horas)
        tabla.to_parquet(os.path.join(carpeta, fuente, f"{fuente}_EURUSD_M1_2016.parquet"))
    cfg2 = ayuda.cfg_prueba(RUTA_PROCESADOS=carpeta)
    tablas = calidad.correr("2016-01-04", "2016-01-29", cfg=cfg2, repo=repo)
    zona = tablas["zona"].iloc[0]
    assert zona["desfase_del_maximo_amplio"] == 60 * horas
    assert not zona["cumple"]
    if abs(horas) <= 2:
        assert zona["desfase_del_maximo"] == 60 * horas


# -----------------------------------------------------------------------------
#  El sellado no se descarga ni se convierte
# -----------------------------------------------------------------------------
def test_la_descarga_rechaza_el_sellado():
    for desde, hasta in [("2021-01-01", "2021-12-31"), ("2020-12-31", "2021-01-01"),
                         ("2026-01-01", "2026-08-31")]:
        with pytest.raises(descarga_histdata.SelladoError):
            descarga_histdata.exigir_antes_del_sellado(desde, hasta)
    descarga_histdata.exigir_antes_del_sellado("2020-01-01", "2020-12-31")

    class SinRed:
        def open(self, *a, **k):
            raise AssertionError("no debio pedir nada a la red")
    with pytest.raises(descarga_histdata.SelladoError):
        descarga_histdata.descargar_anio(2021, abridor=SinRed())
    # La linea de comandos valida todos los anos antes de pedir el primero.
    with pytest.raises(descarga_histdata.SelladoError):
        descarga_histdata.main(["--anios", "2020", "2021"])


def test_la_conversion_rechaza_el_sellado(cfg, repo):
    with pytest.raises(cargador.CandadoError):
        cargador.convertir("histdata", "2020-12-01", "2021-01-31", cfg=cfg, repo=repo)
    indice = pd.DatetimeIndex(["2020-12-31 21:59", "2021-01-01 00:00"], tz="UTC")
    with pytest.raises(cargador.CandadoError):
        cargador._exigir_antes_del_tope(indice, "prueba", cfg)


# -----------------------------------------------------------------------------
#  Solo el cargador lee precios
# -----------------------------------------------------------------------------
def test_solo_el_cargador_lee_los_archivos_de_precios():
    """
    Ningun modulo del proyecto, salvo fuentes/cargador.py, lee parquet; y solo
    los modulos de datos conocen las rutas de los precios.
    """
    pueden_ver_rutas = {"config.py", os.path.join("fuentes", "cargador.py"),
                        os.path.join("fuentes", "manifiesto.py"),
                        os.path.join("fuentes", "descarga_histdata.py"),
                        os.path.join("fuentes", "calendario.py")}
    for carpeta in ("motor", "simulacion", "experimentos", "fuentes"):
        for nombre in os.listdir(os.path.join(RAIZ, carpeta)):
            if not nombre.endswith(".py"):
                continue
            relativo = os.path.join(carpeta, nombre)
            with open(os.path.join(RAIZ, relativo), encoding="utf-8") as f:
                texto = f.read()
            if relativo != os.path.join("fuentes", "cargador.py"):
                assert not re.search(r"read_parquet|read_table|ParquetFile", texto), relativo
            if re.search(r"RUTA_(CRUDOS|PROCESADOS)", texto):
                assert relativo in pueden_ver_rutas, relativo

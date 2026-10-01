# -*- coding: utf-8 -*-
"""
Formatos, manifiesto, conversion y que barra cuenta (punto G), con archivos
pequenos escritos a mano en carpetas temporales.
"""
import io
import os
import subprocess
import zipfile

import numpy as np
import pandas as pd
import pytest

import ayuda
from fuentes import cargador, formatos, manifiesto


# -----------------------------------------------------------------------------
#  Formatos
# -----------------------------------------------------------------------------
HISTDATA = ("20160103 170000;1.087010;1.087130;1.086980;1.087130;0\n"
            "20160103 170100;1.087130;1.087200;1.087100;1.087150;0\n")


def test_histdata_pasa_de_est_fijo_a_utc_sumando_cinco_horas():
    tabla = formatos.histdata_m1(io.StringIO(HISTDATA), 5)
    assert list(tabla.index) == [pd.Timestamp("2016-01-03 22:00", tz="UTC"),
                                 pd.Timestamp("2016-01-03 22:01", tz="UTC")]
    assert tabla.index.name == "apertura_utc"
    assert tabla.iloc[0]["open"] == 1.08701 and tabla.iloc[1]["close"] == 1.08715
    # En julio tambien +5: EST fijo, sin horario de verano.
    julio = formatos.histdata_m1(io.StringIO("20160704 120000;1.1;1.1;1.1;1.1;0\n"), 5)
    assert julio.index[0] == pd.Timestamp("2016-07-04 17:00", tz="UTC")


def test_histdata_rechaza_campos_vacios():
    with pytest.raises(formatos.FormatoError):
        formatos.histdata_m1(io.StringIO("20160103 170000;1.08;;1.08;1.08;0\n"), 5)


RANGO = (0.5, 2.5)


def test_dukascopy_lee_la_coma_decimal_de_jforex_en_espanol():
    # Como lo exporto JForex en el piloto: coma decimal y coma separadora; el
    # volumen entero viene sin decimales (una coma menos).
    texto = ("Time (UTC),Open,High,Low,Close,Volume \n"
             "2016-01-04 10:00:00,1,08701,1,08713,1,08698,1,0871,123,45\n"
             "2016-01-04 10:01:00,1,0871,1,0872,1,087,1,08715,250\n")
    tabla = next(formatos.dukascopy_jforex(io.StringIO(texto), RANGO))
    assert tabla.index[1] == pd.Timestamp("2016-01-04 10:01", tz="UTC")
    assert tabla["open"].tolist() == [1.08701, 1.0871]
    assert tabla["close"].tolist() == [1.0871, 1.08715]
    assert tabla["low"].tolist() == [1.08698, 1.087]
    assert tabla["volumen"].tolist() == [123.45, 250.0]


@pytest.mark.parametrize("fila", [
    "2016-01-04 10:00:00,1,08701,1,08713,1,08698,1,0871",                # faltan campos
    "2016-01-04 10:00:00,1,08701,1,08713,1,08698,1,0871,1,2,3",          # sobran
    "2016-01-04 10:00:00,1,08701,1,08713,1,08698,1,0871,12a,4",          # no son digitos
    "2016-01-04 10:00:00,1,08701,108713,1,08698,1,0871,1,4",             # mal partida: precio absurdo
])
def test_dukascopy_con_coma_decimal_rechaza_filas_mal_formadas(fila):
    texto = ("Time (UTC),Open,High,Low,Close,Volume\n"
             "2016-01-04 09:59:00,1,08701,1,08713,1,08698,1,0871,1,5\n" + fila + "\n")
    with pytest.raises((formatos.FormatoError, ValueError)):
        list(formatos.dukascopy_jforex(io.StringIO(texto), RANGO))


@pytest.mark.parametrize("encabezado, fecha", [
    ("Time (UTC),Open,High,Low,Close,Volume", "03.01.2016 22:00:00.000"),
    ("Gmt time,Open,High,Low,Close,Volume", "03.01.2016 22:00:00.000"),
    ("Time (UTC),Open,High,Low,Close,Volume", "2016.01.03 22:00:00"),
    ("Time (UTC);Open;High;Low;Close;Volume", "2016-01-03 22:00:00"),
])
def test_dukascopy_lee_las_variantes_de_la_exportacion(encabezado, fecha):
    sep = ";" if ";" in encabezado else ","
    texto = encabezado + "\n" + sep.join([fecha, "1.08701", "1.08713", "1.08698", "1.08713", "12.5"]) + "\n"
    trozos = list(formatos.dukascopy_jforex(io.StringIO(texto), RANGO))
    assert len(trozos) == 1
    tabla = trozos[0]
    assert tabla.index[0] == pd.Timestamp("2016-01-03 22:00", tz="UTC")
    assert tabla.iloc[0]["high"] == 1.08713 and tabla.iloc[0]["volumen"] == 12.5


@pytest.mark.parametrize("encabezado", ["Time (EET),Open,High,Low,Close,Volume",
                                        "Time,Open,High,Low,Close,Volume",
                                        "Time (UTC),Open,High,Low,Close"])
def test_dukascopy_rechaza_una_hora_sin_zona_declarada_o_columnas_raras(encabezado):
    texto = encabezado + "\n03.01.2016 22:00:00.000,1.1,1.1,1.1,1.1,1\n"
    with pytest.raises(formatos.FormatoError):
        list(formatos.dukascopy_jforex(io.StringIO(texto), RANGO))


def test_dukascopy_no_adivina_entre_dia_y_mes():
    texto = "Time (UTC),Open,High,Low,Close,Volume\n01/02/2016 22:00:00,1.1,1.1,1.1,1.1,1\n"
    with pytest.raises(formatos.FormatoError):
        list(formatos.dukascopy_jforex(io.StringIO(texto), RANGO))


# -----------------------------------------------------------------------------
#  Que barra cuenta
# -----------------------------------------------------------------------------
def _duka(filas):
    idx = pd.date_range("2016-01-04 10:00", periods=len(filas), freq="min", tz="UTC")
    tabla = pd.DataFrame(filas, index=idx, columns=["bid_open", "bid_high", "bid_low", "bid_close",
                                                    "ask_open", "ask_high", "ask_low", "ask_close",
                                                    "bid_volumen", "ask_volumen"])
    for x in ("open", "high", "low", "close"):
        tabla[f"mid_{x}"] = (tabla[f"bid_{x}"] + tabla[f"ask_{x}"]) / 2
    return tabla[cargador.COLUMNAS_DUKASCOPY]


def test_diagnostico_separa_planas_e_invalidas():
    b, a = 1.1000, 1.1001
    tabla = _duka([
        [b, b + 2e-4, b - 1e-4, b + 1e-4, a, a + 2e-4, a - 1e-4, a + 1e-4, 3.0, 2.0],   # sana
        [b, b, b, b, a, a, a, a, 0.0, 0.0],                                             # plana
        [b, b, b - 1e-4, b + 1e-4, a, a + 2e-4, a - 1e-4, a + 1e-4, 3.0, 2.0],          # maximo < cierre
        [b, b + 2e-4, b - 1e-4, b + 1e-4, b, a + 2e-4, a - 1e-4, a + 1e-4, 3.0, 2.0],   # spread 0 en la apertura
        [b, b + 2e-4, b - 1e-4, b + 1e-4, np.nan, np.nan, np.nan, np.nan, 3.0, np.nan],  # falta el ask
    ])
    marcas = cargador.diagnostico(tabla, "dukascopy")
    assert marcas["plana"].tolist() == [False, True, False, False, False]
    assert marcas["invalida"].tolist() == [False, False, True, True, True]
    assert marcas["ohlc_bid"].tolist()[2] and marcas["spread"].tolist()[3]
    assert marcas["falta_lado"].tolist()[4]
    assert list(cargador.limpiar(tabla, "dukascopy").index) == [tabla.index[0]]


def test_en_histdata_no_hay_planas_y_si_barras_invalidas():
    idx = pd.date_range("2016-01-04 10:00", periods=2, freq="min", tz="UTC")
    tabla = pd.DataFrame([[1.1, 1.1, 1.1, 1.1, 0.0], [1.1, 1.0999, 1.0998, 1.1, 0.0]],
                         index=idx, columns=cargador.COLUMNAS_HISTDATA)
    marcas = cargador.diagnostico(tabla, "histdata")
    assert marcas["plana"].tolist() == [False, False]
    assert marcas["invalida"].tolist() == [False, True]


# -----------------------------------------------------------------------------
#  Manifiesto y conversion
# -----------------------------------------------------------------------------
@pytest.fixture
def entorno(tmp_path):
    repo = tmp_path / "repo"
    (repo / "registro").mkdir(parents=True)
    for args in (["init", "-q"], ["config", "user.name", "Prueba"],
                 ["config", "user.email", "prueba@ejemplo.invalid"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    (repo / "registro" / "LEEME.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-q", "-m", "x"],
                   check=True, capture_output=True)
    cfg = ayuda.cfg_prueba(RUTA_CRUDOS=str(tmp_path / "crudos"),
                           RUTA_PROCESADOS=str(tmp_path / "procesados"))
    return cfg, str(repo)


def _zip_histdata(cfg, anio, lineas):
    carpeta = os.path.join(cfg.RUTA_CRUDOS, "histdata")
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, f"HISTDATA_COM_ASCII_EURUSD_M1{anio}.zip")
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr(f"DAT_ASCII_EURUSD_M1_{anio}.csv", "".join(lineas))
        z.writestr(f"DAT_ASCII_EURUSD_M1_{anio}.txt", "informe\n")
    return ruta


def test_el_manifiesto_detecta_un_crudo_modificado(entorno):
    cfg, repo = entorno
    ruta = _zip_histdata(cfg, 2016, [HISTDATA])
    with pytest.raises(manifiesto.ManifiestoError, match="no esta en"):
        manifiesto.verificar(ruta, cfg, repo)
    fila = manifiesto.registrar(ruta, "histdata", "https://ejemplo", cfg=cfg, repo=repo)
    assert fila["archivo"] == "histdata/HISTDATA_COM_ASCII_EURUSD_M12016.zip"
    assert int(fila["tamano_bytes"]) == os.path.getsize(ruta) and len(fila["sha256"]) == 64
    manifiesto.verificar(ruta, cfg, repo)
    with open(ruta, "ab") as f:
        f.write(b"x")
    with pytest.raises(manifiesto.ManifiestoError, match="cambio"):
        manifiesto.verificar(ruta, cfg, repo)


def test_la_conversion_de_histdata_queda_en_utc_y_por_ano(entorno):
    cfg, repo = entorno
    lineas = [HISTDATA, "20161231 165900;1.05;1.05;1.05;1.05;0\n"]
    ruta = _zip_histdata(cfg, 2016, lineas)
    manifiesto.registrar(ruta, "histdata", "https://ejemplo", cfg=cfg, repo=repo)
    resumen, escritos = cargador.convertir("histdata", "2016-01-01", "2016-12-31", cfg=cfg, repo=repo)
    assert list(escritos) == [2016] and escritos[2016][1] == 3
    tabla = pd.read_parquet(escritos[2016][0])
    assert tabla.index[-1] == pd.Timestamp("2016-12-31 21:59", tz="UTC")
    assert list(tabla.columns) == cargador.COLUMNAS_HISTDATA


def test_la_conversion_no_lee_un_crudo_sin_registrar(entorno):
    cfg, repo = entorno
    _zip_histdata(cfg, 2016, [HISTDATA])
    with pytest.raises(manifiesto.ManifiestoError):
        cargador.convertir("histdata", "2016-01-01", "2016-12-31", cfg=cfg, repo=repo)


def test_un_crudo_con_minutos_del_sellado_no_se_convierte(entorno):
    cfg, repo = entorno
    ruta = _zip_histdata(cfg, 2020, ["20201231 185900;1.2;1.2;1.2;1.2;0\n",    # 23:59 UTC
                                     "20201231 190000;1.2;1.2;1.2;1.2;0\n"])   # 2021-01-01 00:00 UTC
    manifiesto.registrar(ruta, "histdata", "x", cfg=cfg, repo=repo)
    with pytest.raises(cargador.CandadoError, match="sellado"):
        cargador.convertir("histdata", "2016-01-01", "2016-12-31", cfg=cfg, repo=repo)


def test_la_conversion_de_dukascopy_junta_bid_y_ask(entorno):
    cfg, repo = entorno
    carpeta = os.path.join(cfg.RUTA_CRUDOS, "dukascopy")
    os.makedirs(carpeta)
    encabezado = "Time (UTC),Open,High,Low,Close,Volume\n"
    filas = {"BID": ["04.01.2016 10:00:00.000,1.1000,1.1002,1.0999,1.1001,2.5\n",
                     "04.01.2016 10:01:00.000,1.1001,1.1001,1.1001,1.1001,0\n"],
             "ASK": ["04.01.2016 10:00:00.000,1.1001,1.1003,1.1000,1.1002,3.5\n",
                     "04.01.2016 10:01:00.000,1.1002,1.1002,1.1002,1.1002,0\n"]}
    for lado, lineas in filas.items():
        ruta = os.path.join(carpeta, f"EURUSD_Candlestick_1_M_{lado}_01.01.2016-31.01.2016.csv")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(encabezado + "".join(lineas))
    manifiesto.registrar_manuales("dukascopy", cfg=cfg, repo=repo)
    _, escritos = cargador.convertir("dukascopy", "2016-01-01", "2016-01-31", cfg=cfg, repo=repo)
    tabla = pd.read_parquet(escritos[2016][0])
    assert list(tabla.columns) == cargador.COLUMNAS_DUKASCOPY
    assert len(tabla) == 2
    assert tabla.iloc[0]["mid_high"] == pytest.approx((1.1002 + 1.1003) / 2, abs=1e-15)
    assert tabla.iloc[0]["ask_volumen"] == 3.5
    marcas = cargador.diagnostico(tabla, "dukascopy")
    assert marcas["plana"].tolist() == [False, True]
    assert not os.path.exists(os.path.join(cfg.RUTA_PROCESADOS, "_partes_dukascopy"))


# -----------------------------------------------------------------------------
#  Proteccion del sellado por el nombre (incidente del 2026-10-01)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("nombre, fin", [
    ("EURUSD_1 Min_Bid_2003.05.04_2020.12.31.csv", "2020-12-31"),
    ("EURUSD_1 Min_Ask_2015.12.31_2016.02.02.csv", "2016-02-02"),
    ("EURUSD_1 Min_Ask_2003.05.04_2026.10.01.csv", "2026-10-01"),
    ("EURUSD_Candlestick_1_M_BID_01.01.2016-31.01.2016.csv", "2016-01-31"),
    ("EURUSD_1 Min_Bid.csv", None),
])
def test_la_fecha_final_sale_del_nombre(nombre, fin):
    esperado = None if fin is None else pd.Timestamp(fin).date()
    assert manifiesto.fecha_final_en_nombre(nombre) == esperado


@pytest.mark.parametrize("nombre", [
    "EURUSD_1 Min_Ask_2003.05.04_2026.10.01.csv",               # el del incidente
    "EURUSD_1 Min_Bid_2020.12.01_2021.01.01.csv",               # un dia del sellado
    "EURUSD_Candlestick_1_M_BID_01.12.2020-01.01.2021.csv",     # formato del exportador web
    "EURUSD_1 Min_Bid.csv",                                     # sin fecha final: tampoco
])
def test_el_registro_rechaza_sin_leerlo_un_crudo_que_llega_al_sellado(entorno, monkeypatch, nombre):
    cfg, repo = entorno
    carpeta = os.path.join(cfg.RUTA_CRUDOS, "dukascopy")
    os.makedirs(carpeta)
    bueno = os.path.join(carpeta, "EURUSD_1 Min_Ask_2003.05.04_2020.12.31.csv")
    malo = os.path.join(carpeta, nombre)
    for ruta in (bueno, malo):
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("Time (UTC),Open,High,Low,Close,Volume\n")

    def prohibido(*args, **kwargs):
        raise AssertionError("se intento leer un crudo que el nombre ya rechazaba")
    monkeypatch.setattr(manifiesto, "sha256", prohibido)
    monkeypatch.setattr(formatos, "dukascopy_jforex", prohibido)

    with pytest.raises(manifiesto.SelladoError, match="sellado"):
        manifiesto.registrar(malo, "dukascopy", "x", cfg=cfg, repo=repo)
    # Si uno de la carpeta llega al sellado, no se registra ninguno.
    with pytest.raises(manifiesto.SelladoError, match="no se registro nada"):
        manifiesto.registrar_manuales("dukascopy", cfg=cfg, repo=repo)
    assert manifiesto.leer(repo) == {}
    # Y el cargador no lo convierte, aunque alguien lo hubiera registrado a mano.
    with pytest.raises(manifiesto.SelladoError):
        cargador.convertir("dukascopy", "2016-01-01", "2016-01-31", cfg=cfg, repo=repo)


def test_un_nombre_hasta_el_31_de_diciembre_de_2020_si_se_registra(entorno):
    cfg, repo = entorno
    carpeta = os.path.join(cfg.RUTA_CRUDOS, "dukascopy")
    os.makedirs(carpeta)
    for lado in ("Bid", "Ask"):
        with open(os.path.join(carpeta, f"EURUSD_1 Min_{lado}_2003.05.04_2020.12.31.csv"), "w") as f:
            f.write("x\n")
    assert len(manifiesto.registrar_manuales("dukascopy", cfg=cfg, repo=repo)) == 2


# -----------------------------------------------------------------------------
#  Primera pasada de Dukascopy: solo horas, antes de leer un precio
# -----------------------------------------------------------------------------
def _csv_dukascopy(cfg, lado, filas, fin="2020.12.31"):
    carpeta = os.path.join(cfg.RUTA_CRUDOS, "dukascopy")
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, f"EURUSD_1 Min_{lado}_2020.12.30_{fin}.csv")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("Time (UTC),Open,High,Low,Close,Volume \n")
        for hora in filas:
            f.write(f"{hora},1,22001,1,22003,1,21999,1,22002,12,5\n")
    return ruta


def test_un_minuto_del_sellado_detiene_la_conversion_sin_leer_precios(entorno, monkeypatch):
    cfg, repo = entorno
    _csv_dukascopy(cfg, "Bid", ["2020-12-31 21:58:00", "2021-01-01 00:00:00"])
    _csv_dukascopy(cfg, "Ask", ["2020-12-31 21:58:00"])
    manifiesto.registrar_manuales("dukascopy", cfg=cfg, repo=repo)
    # 2020 es validacion: la conversion exige el arbol limpio.
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "m"],
                   check=True, capture_output=True)

    def prohibido(*args, **kwargs):
        raise AssertionError("se interpretaron precios antes de revisar las horas")
    monkeypatch.setattr(formatos, "dukascopy_jforex", prohibido)
    with pytest.raises(cargador.CandadoError, match="No se interpreto ningun precio"):
        cargador.convertir("dukascopy", "2020-12-01", "2020-12-31", cfg=cfg, repo=repo)


def test_la_primera_pasada_cuenta_los_minutos_que_estan_en_un_solo_lado(entorno):
    cfg, repo = entorno
    bid = _csv_dukascopy(cfg, "Bid", ["2016-01-04 10:00:00", "2016-01-04 10:01:00",
                                      "2016-01-04 10:02:00"])
    ask = _csv_dukascopy(cfg, "Ask", ["2016-01-04 10:00:00", "2016-01-04 10:02:00",
                                      "2016-01-04 10:03:00", "2016-01-04 10:04:00"])
    por_archivo, minutos = cargador.revisar_minutos_dukascopy([bid, ask], cfg)
    fila = minutos.iloc[0]
    assert (fila["anio"], fila["minutos_bid"], fila["minutos_ask"]) == (2016, 3, 4)
    assert (fila["solo_bid"], fila["solo_ask"]) == (1, 2)
    assert por_archivo["ultima_utc"].tolist() == [pd.Timestamp("2016-01-04 10:02", tz="UTC"),
                                                  pd.Timestamp("2016-01-04 10:04", tz="UTC")]


def test_histdata_con_zona_lee_la_hora_de_nueva_york_con_horario_de_verano():
    texto = "20160103 170000;1.1;1.1;1.1;1.1;0\n20160703 170000;1.1;1.1;1.1;1.1;0\n"
    fija = formatos.histdata_m1(io.StringIO(texto), 5)
    ny = formatos.histdata_m1(io.StringIO(texto), 5, zona="America/New_York")
    # En enero las dos reglas coinciden; en julio la de Nueva York es una hora antes.
    assert list(fija.index) == [pd.Timestamp("2016-01-03 22:00", tz="UTC"),
                                pd.Timestamp("2016-07-03 22:00", tz="UTC")]
    assert list(ny.index) == [pd.Timestamp("2016-01-03 22:00", tz="UTC"),
                              pd.Timestamp("2016-07-03 21:00", tz="UTC")]
    # Una hora que no existe en Nueva York (el adelanto de marzo) no se adivina.
    with pytest.raises(Exception):
        formatos.histdata_m1(io.StringIO("20160313 023000;1.1;1.1;1.1;1.1;0\n"), 5,
                             zona="America/New_York")

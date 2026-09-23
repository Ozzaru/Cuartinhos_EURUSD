# -*- coding: utf-8 -*-
"""
MERCADO — generador de precios artificiales sin memoria.

La idea es tener un mercado donde, por construccion, NO hay nada que
descubrir: ningun ingrediente mira precios pasados para decidir hacia donde ir.
Cualquier efecto que el motor encuentre aqui es un falso positivo, y contarlos
es justamente el control negativo.

Que si tiene, porque son cosas que el EUR/USD tiene de verdad y que podrian
confundir al motor si no estuvieran:

  - una semana de mercado: de domingo 17:00 a viernes 17:00, hora de Nueva
    York, con el fin de semana cerrado;
  - volatilidad que cambia con la hora de Londres: baja de madrugada, sube en
    la apertura, maxima en el solape con Nueva York, baja de nuevo al final;
  - un regimen de volatilidad lento, un AR(1) diario, para que haya epocas
    tranquilas y epocas movidas y los deciles de volatilidad tengan sentido;
  - spread bid-ask, mas ancho de noche;
  - anuncios macro que multiplican la volatilidad por un rato, SIN empujar el
    precio hacia ningun lado.

Lo que NO tiene: tendencia, reversion a la media, memoria de volatilidad
dentro del dia, ni ninguna relacion entre el pasado y la direccion futura.

El precio medio es un paseo aleatorio en logaritmos con varios subpasos por
minuto, y de esos subpasos salen la apertura, el maximo, el minimo y el cierre.
Sin subpasos, el maximo y el minimo del minuto serian siempre la apertura o el
cierre, y las rupturas se detectarian mal.
"""
import numpy as np
import pandas as pd

from motor import tiempo

COLUMNAS = ["bid_open", "bid_high", "bid_low", "bid_close",
            "ask_open", "ask_high", "ask_low", "ask_close"]

TAMANO_TROZO = 400_000       # minutos por trozo, para no llenar la memoria


def minutos_operables(inicio, anios, cfg):
    """
    Los minutos en que el mercado esta abierto, en UTC.

    La semana va de domingo 17:00 a viernes 17:00 hora de Nueva York. Se define
    en esa zona a proposito: es la convencion del mercado de divisas, y al
    pasarla a UTC se corre una hora segun el horario de verano, igual que en la
    realidad.
    """
    fin = pd.Timestamp(inicio, tz="UTC") + pd.DateOffset(years=int(anios))
    todos = pd.date_range(pd.Timestamp(inicio, tz="UTC"), fin, freq="min",
                          inclusive="left")
    ny = todos.tz_convert(cfg.ZONA_MERCADO)
    dia, hora = ny.dayofweek, ny.hour          # lunes = 0 ... domingo = 6
    cerrado = ((dia == 4) & (hora >= 17)) | (dia == 5) | ((dia == 6) & (hora < 17))
    return todos[~cerrado]


def calendario_noticias(indice, cfg):
    """
    Anuncios macro simulados, con los horarios tipicos de los de verdad:

      empleo  primer viernes de cada mes, 13:30 UTC
      ipc     dia 12 de cada mes, 13:30 UTC
      fomc    tercer miercoles de ocho meses al ano, 19:00 UTC

    El dia 12 puede caer sabado o domingo. En ese caso el anuncio se corre al
    siguiente dia con mercado abierto, igual que pasa en la realidad: las
    oficinas de estadistica no publican en fin de semana. Antes se dejaba caer
    en el minuto cerrado y se perdia, lo que restaba alrededor de un 15% de la
    muestra tratada de H4 sin ninguna razon.
    """
    inicio, fin = indice[0], indice[-1]
    meses = pd.date_range(inicio.normalize().replace(day=1), fin, freq="MS", tz="UTC")
    fechas, tipos = [], []

    meses_fomc = {1, 3, 4, 6, 7, 9, 11, 12}
    for mes in meses:
        dias = pd.date_range(mes, mes + pd.Timedelta(days=27), freq="D")
        viernes = [d for d in dias if d.dayofweek == 4]
        if viernes:
            fechas.append(viernes[0] + pd.Timedelta(hours=13, minutes=30))
            tipos.append("empleo")
        fechas.append(mes + pd.Timedelta(days=11, hours=13, minutes=30))
        tipos.append("ipc")
        if mes.month in meses_fomc:
            miercoles = [d for d in dias if d.dayofweek == 2]
            if len(miercoles) >= 3:
                fechas.append(miercoles[2] + pd.Timedelta(hours=19))
                tipos.append("fomc")

    momentos = [_al_dia_habil(t, indice) for t in pd.DatetimeIndex(fechas)]
    tabla = pd.DataFrame({"t_utc": pd.DatetimeIndex(momentos), "tipo": tipos})
    tabla = tabla[(tabla["t_utc"] >= inicio) & (tabla["t_utc"] <= fin)]
    return tabla.sort_values("t_utc").reset_index(drop=True)


def _al_dia_habil(momento, indice, dias_max=4):
    """
    Corre un anuncio al siguiente dia con mercado abierto, a la misma hora.

    Si despues de varios dias sigue sin haber mercado, se devuelve el momento
    original: es preferible un anuncio que no afecta a nadie que uno colocado
    en una fecha arbitraria.
    """
    for salto in range(dias_max + 1):
        candidato = momento + pd.Timedelta(days=salto)
        if indice.get_indexer([candidato])[0] >= 0:
            return candidato
    return momento


def _multiplicadores(indice, noticias, cfg, rng):
    """
    Cuanto se mueve cada minuto, en veces la volatilidad tipica.

    Tres factores que se multiplican: la hora de Londres, el regimen del dia y
    el rato posterior a un anuncio.
    """
    londres = indice.tz_convert(cfg.ZONA)
    perfil = np.asarray(cfg.PERFIL_HORARIO_VOL, dtype=float)[londres.hour.to_numpy()]

    # Regimen diario: un AR(1) en logaritmos, asi que nunca se vuelve negativo.
    dias = pd.DatetimeIndex(londres.normalize()).tz_localize(None)
    codigo, unicos = pd.factorize(dias, sort=True)
    estado = np.empty(len(unicos))
    estado[0] = rng.normal(0.0, cfg.AR1_SIGMA_DIARIA)
    choques = rng.normal(0.0, cfg.AR1_SIGMA_DIARIA, len(unicos))
    for d in range(1, len(unicos)):
        estado[d] = cfg.AR1_VOL_DIARIA * estado[d - 1] + choques[d]
    regimen = np.exp(estado)[codigo]

    # Anuncios: mas volatilidad por unos minutos, sin empujar el precio.
    salto = np.ones(len(indice))
    if len(noticias):
        t_anuncio = tiempo.a_ns(pd.DatetimeIndex(noticias["t_utc"]))
        minuto_ns = tiempo.a_ns(indice)
        desde = np.searchsorted(minuto_ns, t_anuncio, side="left")
        hasta = np.searchsorted(minuto_ns,
                                t_anuncio + cfg.NOTICIA_DURACION_MIN * tiempo.NS_MIN,
                                side="left")
        for a, b in zip(desde, hasta):
            salto[a:b] = cfg.NOTICIA_FACTOR_VOL
    return perfil * regimen * salto


def _camino(sigma, rng, precio_inicial, subpasos):
    """
    El paseo aleatorio, con varios subpasos por minuto, en trozos para no
    llenar la memoria.

    Devuelve apertura, maximo, minimo y cierre del precio MEDIO de cada minuto.
    """
    n = len(sigma)
    apertura = np.empty(n)
    maximo = np.empty(n)
    minimo = np.empty(n)
    cierre = np.empty(n)
    log_precio = np.log(precio_inicial)

    for desde in range(0, n, TAMANO_TROZO):
        hasta = min(desde + TAMANO_TROZO, n)
        tramo = sigma[desde:hasta]
        pasos = rng.normal(0.0, 1.0, (len(tramo), subpasos))
        pasos *= (tramo / np.sqrt(subpasos))[:, None]
        recorrido = np.cumsum(pasos, axis=1)

        # El nivel al empezar cada minuto es el cierre del minuto anterior.
        inicio_minuto = log_precio + np.concatenate([[0.0], np.cumsum(recorrido[:-1, -1])])
        camino = inicio_minuto[:, None] + recorrido

        apertura[desde:hasta] = np.exp(inicio_minuto)
        cierre[desde:hasta] = np.exp(camino[:, -1])
        maximo[desde:hasta] = np.exp(np.maximum(camino.max(axis=1), inicio_minuto))
        minimo[desde:hasta] = np.exp(np.minimum(camino.min(axis=1), inicio_minuto))
        log_precio = camino[-1, -1]

    return apertura, maximo, minimo, cierre


def generar(anios, semilla, cfg, inicio="2013-01-01"):
    """
    Devuelve (datos, noticias) listos para el motor.

    `datos` trae las ocho columnas de bid y ask con indice UTC por minuto, y
    `noticias` el calendario de anuncios con columnas t_utc y tipo.

    La volatilidad queda calibrada para que el mercado tenga VOL_ANUAL_SIMULACION
    de volatilidad anual: se calcula la constante que hace que la suma de las
    varianzas de un ano de sus minutos de exactamente ese numero.
    """
    rng = np.random.default_rng(semilla)
    indice = minutos_operables(inicio, anios, cfg)
    noticias = calendario_noticias(indice, cfg)

    multiplicador = _multiplicadores(indice, noticias, cfg, rng)
    # Calibracion: k tal que la varianza acumulada de un ano sea VOL_ANUAL^2.
    varianza_por_anio = np.sum(multiplicador ** 2) / anios
    k = cfg.VOL_ANUAL_SIMULACION / np.sqrt(varianza_por_anio)
    sigma = k * multiplicador

    apertura, maximo, minimo, cierre = _camino(
        sigma, rng, cfg.PRECIO_INICIAL, cfg.SUBPASOS_POR_MINUTO)

    # Spread: mas ancho en la franja nocturna de UTC, que es cuando el mercado
    # esta mas fino.
    hora_utc = indice.hour.to_numpy()
    h0, h1 = cfg.SPREAD_HORAS_NOCTURNAS
    ancho = np.where((hora_utc >= h0) & (hora_utc < h1),
                     cfg.SPREAD_BASE_PIPS * cfg.SPREAD_FACTOR_NOCTURNO,
                     cfg.SPREAD_BASE_PIPS) * cfg.PIP
    medio = ancho / 2.0

    datos = pd.DataFrame(index=indice)
    for nombre, valores in [("open", apertura), ("high", maximo),
                            ("low", minimo), ("close", cierre)]:
        datos[f"bid_{nombre}"] = valores - medio
        datos[f"ask_{nombre}"] = valores + medio
    return datos[COLUMNAS], noticias


def resumen(datos, cfg):
    """Unos pocos numeros para revisar que el mercado salio como se esperaba."""
    mid = (datos["bid_close"] + datos["ask_close"]) / 2.0
    ret = np.diff(np.log(mid.to_numpy()))
    minutos_por_anio = len(datos) / ((datos.index[-1] - datos.index[0]).days / 365.25)
    return {
        "minutos": len(datos),
        "precio_inicial": float(mid.iloc[0]),
        "precio_final": float(mid.iloc[-1]),
        "vol_anual": float(np.std(ret, ddof=1) * np.sqrt(minutos_por_anio)),
        "spread_medio_pips": float(((datos["ask_close"] - datos["bid_close"]).mean())
                                   / cfg.PIP),
    }

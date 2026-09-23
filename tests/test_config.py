# -*- coding: utf-8 -*-
"""
Pruebas de humo de la configuracion: que el archivo cargue y que los valores
que el resto del codigo da por sentados esten donde se espera.
"""
import config as cfg


def test_franjas_son_cuatro_de_seis_horas():
    assert cfg.LIMITES_HORAS == [0, 6, 12, 18, 24]
    horas = [b - a for a, b in zip(cfg.LIMITES_HORAS, cfg.LIMITES_HORAS[1:])]
    assert horas == [6, 6, 6, 6]


def test_horizontes_incluyen_fin_de_franja():
    assert cfg.HORIZONTES == cfg.HORIZONTES_MIN + ["fin_franja"]
    assert cfg.HORIZONTE_PRINCIPAL in cfg.HORIZONTES_MIN


def test_el_horizonte_de_120_es_descriptivo_y_no_confirma():
    # Sale de la familia principal porque en el control negativo rechaza entre
    # el 14% y el 16% bajo la nula. Se sigue midiendo y reportando.
    assert 120 in cfg.HORIZONTES, "se sigue calculando"
    assert 120 in cfg.HORIZONTES_DESCRIPTIVOS
    assert 120 not in cfg.HORIZONTES_CONFIRMATORIOS
    assert 120 not in {h for _, h, _, _ in cfg.FAMILIA_PRINCIPAL}
    # Pero sigue en las otras dos familias, que si estan calibradas.
    assert 120 in {h for _, h, _, _ in cfg.FAMILIA_MODERADORES}
    assert 120 in {h for _, h, _, _ in cfg.FAMILIA_H4}


def test_familias_de_pruebas_bien_formadas():
    # Familia principal: H1 y H2, una cola cada una, en los horizontes
    # confirmatorios.
    assert len(cfg.FAMILIA_PRINCIPAL) == 2 * len(cfg.HORIZONTES_CONFIRMATORIOS)
    assert len(cfg.FAMILIA_PRINCIPAL) == 6
    tipos = {t for t, _, _, _ in cfg.FAMILIA_PRINCIPAL}
    assert tipos == {"sostenida", "reingreso"}
    colas = {t: c for t, _, _, c in cfg.FAMILIA_PRINCIPAL}
    assert colas["sostenida"] == "mayor" and colas["reingreso"] == "menor"
    # Familia de moderadores (H3): dos tipos x horizontes x moderadores
    # PROBADOS, a dos colas. `noticia` no esta: se prueba en FAMILIA_H4.
    assert len(cfg.FAMILIA_MODERADORES) == 2 * len(cfg.HORIZONTES) * len(cfg.MODERADORES_PROBADOS)
    assert {c for _, _, _, c in cfg.FAMILIA_MODERADORES} == {"dos"}
    assert "noticia" not in {coef for _, _, coef, _ in cfg.FAMILIA_MODERADORES}
    assert "noticia" in cfg.MODERADORES, "sigue como control de la regresion"
    # Familia H4: dos tipos x horizontes, a una cola "mayor".
    assert len(cfg.FAMILIA_H4) == 2 * len(cfg.HORIZONTES)
    assert {c for _, _, _, c in cfg.FAMILIA_H4} == {"mayor"}
    # "ruptura" es descriptivo: no entra en ninguna familia corregida.
    assert "ruptura" not in tipos
    assert "ruptura" in cfg.TIPOS_DESCRIPTIVOS


def test_cortes_de_muestra_no_se_solapan():
    assert cfg.DESARROLLO_HASTA < cfg.VALIDACION[0] < cfg.VALIDACION[1] < cfg.SELLADO[0]
    assert cfg.SELLADO[0] < cfg.SELLADO[1]


def test_perfil_horario_cubre_el_dia():
    assert len(cfg.PERFIL_HORARIO_VOL) == 24
    assert all(v > 0 for v in cfg.PERFIL_HORARIO_VOL)

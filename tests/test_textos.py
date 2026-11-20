"""Testes para quebra, posicionamento, desenho e máscara dos textos do anúncio."""

import numpy as np
import pytest
from PIL import Image, ImageFont

from anuncio.imagens import fundo_radial
from anuncio.layout import (
    CANVAS,
    FONTE_BLACK,
    SUB_COR,
    SUB_DESLOC,
    SUB_ENTRELINHA,
    SUB_TAM,
    TITULO_COR,
    TITULO_DESLOC,
    TITULO_ENTRELINHA,
    TITULO_LARG_MAX,
    TITULO_TAM,
)
from anuncio.textos import (
    Textos,
    desenhar_textos,
    mascara_textos,
    posicionar_textos,
    quebrar_titulo,
    textos_fora_canvas,
)


def _fonte_titulo(tam: int = TITULO_TAM) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTE_BLACK), tam)


def test_quebra_equilibrada():
    f132 = _fonte_titulo(132)
    assert quebrar_titulo("Puxador de Porta", f132) == ["Puxador", "de Porta"]


def test_uma_palavra():
    f132 = _fonte_titulo(132)
    assert quebrar_titulo("Retrovisor", f132) == ["Retrovisor"]


def test_quebra_normaliza_espacos():
    f132 = _fonte_titulo(132)
    assert quebrar_titulo("  Puxador   de   Porta  ", f132) == ["Puxador", "de Porta"]
    assert quebrar_titulo("  Retrovisor  ", f132) == ["Retrovisor"]


def test_baselines_padrao():
    t = posicionar_textos(
        283,
        "Puxador de Porta",
        ["compatível com", "new fiesta sedan", "2011 a 2017"],
    )
    assert isinstance(t, Textos)
    assert t.linhas_titulo == ["Puxador", "de Porta"]
    assert t.tam_titulo == 132
    assert t.tam_sub == 40
    assert t.baselines_titulo == [395, 521]
    assert t.baselines_sub == [577, 625, 673]
    assert t.linhas_sub == ["COMPATÍVEL COM", "NEW FIESTA SEDAN", "2011 A 2017"]


def test_titulo_longo_reduz():
    t = posicionar_textos(283, "Maçaneta Interna Dianteira Esquerda", [])
    fonte = _fonte_titulo(t.tam_titulo)
    assert t.tam_titulo < 132
    assert max(fonte.getlength(linha) for linha in t.linhas_titulo) <= TITULO_LARG_MAX
    assert t.linhas_sub == []
    assert t.baselines_sub == []


def test_palavra_longa_reduz():
    t = posicionar_textos(283, "Retrovisor-Elétrico-Completo", [])
    largura = _fonte_titulo(t.tam_titulo).getlength(t.linhas_titulo[0])
    assert len(t.linhas_titulo) == 1
    assert len(t.baselines_titulo) == 1
    assert t.tam_titulo < 132
    assert largura <= TITULO_LARG_MAX


def test_quatro_linhas_erro():
    with pytest.raises(ValueError, match="3 linhas"):
        posicionar_textos(283, "X Y", ["a", "b", "c", "d"])


def test_linhas_vazias_ignoradas():
    t = posicionar_textos(283, "X Y", ["a", "", "b"])
    assert len(t.linhas_sub) == 2
    assert t.linhas_sub == ["A", "B"]

    t_espacos = posicionar_textos(283, "X Y", ["  a  ", "   ", "b", "", "c"])
    assert t_espacos.linhas_sub == ["A", "B", "C"]


def test_titulo_vazio_erro():
    with pytest.raises(ValueError, match="Título obrigatório"):
        posicionar_textos(283, "", ["a"])

    with pytest.raises(ValueError, match="Título obrigatório"):
        posicionar_textos(283, "   \t\n ", [])


def test_escalonamento_baselines_titulo_reduzido():
    t = posicionar_textos(
        283,
        "Maçaneta Interna Dianteira Esquerda",
        ["linha um", "linha dois"],
    )
    assert t.tam_titulo < TITULO_TAM
    assert t.tam_sub == SUB_TAM

    s_t = t.tam_titulo / TITULO_TAM
    b1 = round(283 + TITULO_DESLOC * s_t)
    b2 = round(b1 + TITULO_ENTRELINHA * s_t)
    assert t.baselines_titulo == [b1, b2]

    sb0 = round(b2 + SUB_DESLOC)
    sb1 = round(sb0 + SUB_ENTRELINHA)
    assert t.baselines_sub == [sb0, sb1]


def test_escalonamento_baselines_subtitulo_reduzido():
    t = posicionar_textos(
        283,
        "Puxador de Porta",
        ["linha um", "linha dois", "linha tres"],
        tam_sub=30,
    )
    assert t.tam_titulo == TITULO_TAM
    assert t.tam_sub == 30
    assert t.baselines_titulo == [395, 521]

    s_s = 30 / SUB_TAM
    sb0 = round(521 + SUB_DESLOC * s_s)
    sb1 = round(sb0 + SUB_ENTRELINHA * s_s)
    sb2 = round(sb0 + 2 * SUB_ENTRELINHA * s_s)
    assert t.baselines_sub == [sb0, sb1, sb2]


def test_uma_palavra_com_subtitulo():
    t = posicionar_textos(283, "Tampa", ["lado esquerdo", "original"])
    assert t.linhas_titulo == ["Tampa"]
    assert t.tam_titulo == 132
    assert t.baselines_titulo == [395]
    assert t.baselines_sub == [451, 499]


def test_titulo_extremo_respeita_piso():
    t = posicionar_textos(283, "Supercalifragilisticexpialidocious" * 3, [])
    assert t.tam_titulo == 8
    assert len(t.linhas_titulo) == 1


def test_mascara_textos_forma_e_pixels():
    t = posicionar_textos(
        283,
        "Puxador de Porta",
        ["compatível com", "new fiesta"],
    )
    m_titulo, m_sub = mascara_textos(t)

    assert m_titulo.shape == (CANVAS, CANVAS)
    assert m_sub.shape == (CANVAS, CANVAS)
    assert m_titulo.dtype == np.bool_
    assert m_sub.dtype == np.bool_
    assert m_titulo.any()
    assert m_sub.any()
    assert not (m_titulo & m_sub).any()

    ys_t = np.flatnonzero(m_titulo.any(axis=1))
    ys_s = np.flatnonzero(m_sub.any(axis=1))
    assert ys_t.max() < ys_s.min()

    t_sem_sub = posicionar_textos(283, "Retrovisor", [])
    m_t2, m_s2 = mascara_textos(t_sem_sub)
    assert m_t2.any()
    assert not m_s2.any()


def test_desenhar_textos_rgb_e_rgba():
    t = posicionar_textos(
        283,
        "Puxador de Porta",
        ["compatível com", "new fiesta"],
    )
    m_titulo, m_sub = mascara_textos(t)

    canvas_branco = Image.new("RGB", (CANVAS, CANVAS), (255, 255, 255))
    desenhar_textos(canvas_branco, t)
    arr_branco = np.asarray(canvas_branco)
    alterados = (arr_branco < 255).any(axis=2)
    assert np.array_equal(alterados, m_titulo | m_sub)

    pixels_titulo = arr_branco[m_titulo]
    pixels_sub = arr_branco[m_sub]
    assert np.any(np.all(pixels_titulo == TITULO_COR, axis=1))
    assert np.any(np.all(pixels_sub == SUB_COR, axis=1))

    cv_rgb = fundo_radial()
    cv_rgba = cv_rgb.convert("RGBA")
    desenhar_textos(cv_rgb, t)
    desenhar_textos(cv_rgba, t)

    arr_rgb = np.asarray(cv_rgb)
    arr_rgba = np.asarray(cv_rgba)
    assert cv_rgba.mode == "RGBA"
    assert np.array_equal(arr_rgb, arr_rgba[..., :3])
    assert np.all(arr_rgba[..., 3] == 255)


def test_textos_fora_canvas_detecta_gap_na_borda():
    t_ok = posicionar_textos(283, "Puxador de Porta", ["compatível com", "new fiesta"])
    assert textos_fora_canvas(t_ok) == (False, False)

    t_sub_gap = posicionar_textos(
        283,
        "Puxador de Porta",
        ["COMPATÍVEL COM NEW FIESTA SEDAN TITANIUM PLUS 2015 A 2020"],
    )
    _, m_sub = mascara_textos(t_sub_gap)
    assert not m_sub[:, -1].any()
    assert textos_fora_canvas(t_sub_gap) == (False, True)

    t_titulo_baixo = posicionar_textos(1000, "Puxador", [])
    assert textos_fora_canvas(t_titulo_baixo) == (True, False)


def test_posicionar_textos_sem_titulo():
    t = posicionar_textos(
        283,
        "",
        ["compatível com", "new fiesta"],
        usar_titulo=False,
    )
    assert t.linhas_titulo == []
    assert t.baselines_titulo == []
    assert t.linhas_sub == ["COMPATÍVEL COM", "NEW FIESTA"]
    assert t.baselines_sub == [283 + 56, 283 + 56 + 48]


def test_posicionar_textos_sem_subtitulo():
    t = posicionar_textos(
        283,
        "Puxador de Porta",
        ["qualquer", "linha"],
        usar_subtitulo=False,
    )
    assert t.linhas_titulo == ["Puxador", "de Porta"]
    assert t.linhas_sub == []
    assert t.baselines_sub == []


def test_posicionar_textos_largura_max_personalizada():
    titulo = "Retrovisor Externo"
    t_estreito = posicionar_textos(283, titulo, [], larg_max_titulo=560)
    t_largo = posicionar_textos(283, titulo, [], larg_max_titulo=952)
    assert t_estreito.tam_titulo < 132
    assert t_largo.tam_titulo == 132
    assert t_largo.tam_titulo > t_estreito.tam_titulo

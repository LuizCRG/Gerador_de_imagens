"""Testes para detecção da área da foto, recorte, cartão do print e etiqueta."""

import numpy as np
from PIL import Image

from anuncio.cartao import (
    desenhar_cartao,
    desenhar_etiqueta,
    detectar_area_foto,
    normalizar_recorte,
)
from anuncio.imagens import fundo_radial
from anuncio.layout import (
    CARTAO_POS,
    ETIQ_ALT,
    ETIQ_COR,
    ETIQ_POS,
    PRINT_TAM,
)


def test_area_sem_barras(img_print):
    l, t, r, b = detectar_area_foto(img_print)
    assert t >= 120 and b <= 1400 and l == 0 and r == 720


def test_area_uniforme_fallback():
    im = Image.new("RGB", (300, 500), (128, 128, 128))
    assert detectar_area_foto(im) == (0, 0, 300, 500)


def test_area_barras_laterais():
    arr = np.full((200, 300, 3), 255, dtype=np.uint8)
    arr[20:180, :30] = 0
    arr[20:180, 270:] = 0
    rng = np.random.default_rng(7)
    arr[20:180, 30:270] = rng.integers(60, 220, size=(160, 240, 3), dtype=np.uint8)
    im = Image.fromarray(arr, mode="RGB")
    assert detectar_area_foto(im) == (30, 20, 270, 180)


def test_recorte_inicial_proporcao(img_print):
    area = detectar_area_foto(img_print)
    l, t, r, b = normalizar_recorte(None, img_print.size, area)
    assert abs((r - l) / (b - t) - PRINT_TAM[0] / PRINT_TAM[1]) < 0.01
    assert t >= 120 and b <= 1400


def test_recorte_fora_da_imagem():
    recorte = normalizar_recorte((-50, -50, 300, 300), (720, 1600), (0, 0, 720, 1600))
    l, t, r, b = recorte
    assert l >= 0 and t >= 0 and r <= 720 and b <= 1600
    assert abs((r - l) / (b - t) - PRINT_TAM[0] / PRINT_TAM[1]) < 0.01


def test_recorte_proporcao_corrigida():
    l, t, r, b = normalizar_recorte((0, 0, 350, 400), (720, 1600), (0, 0, 720, 1600))
    assert abs((r - l) / (b - t) - PRINT_TAM[0] / PRINT_TAM[1]) < 0.01


def test_recorte_maior_que_imagem():
    l, t, r, b = normalizar_recorte((-100, -100, 1200, 1200), (720, 1600), (0, 0, 720, 1600))
    assert 0 <= l < r <= 720 and 0 <= t < b <= 1600
    assert abs((r - l) / (b - t) - PRINT_TAM[0] / PRINT_TAM[1]) < 0.01


def test_cartao_borda_branca(img_print):
    cv = fundo_radial()
    recorte = normalizar_recorte(None, img_print.size, detectar_area_foto(img_print))
    caixa = desenhar_cartao(cv, img_print, recorte)
    assert caixa == (40, 712, 406, 983)
    assert cv.getpixel((44, 847))[:3] == (255, 255, 255)


def test_cartao_foto(img_print):
    cv = fundo_radial()
    recorte = normalizar_recorte(None, img_print.size, detectar_area_foto(img_print))
    desenhar_cartao(cv, img_print, recorte)
    cor_centro = cv.getpixel((48 + 175, 720 + 127))[:3]
    esperada = (
        img_print.crop(recorte)
        .resize(PRINT_TAM, Image.Resampling.LANCZOS)
        .getpixel((175, 127))[:3]
    )
    assert cor_centro != (255, 255, 255) and cor_centro == esperada


def test_cartao_canto_arredondado(img_print):
    fundo = fundo_radial()
    cv = fundo.copy()
    recorte = normalizar_recorte(None, img_print.size, detectar_area_foto(img_print))
    desenhar_cartao(cv, img_print, recorte)
    p_cartao = cv.getpixel((41, 713))[:3]
    p_fundo = fundo.getpixel((41, 713))[:3]
    assert all(abs(a - b) < 12 for a, b in zip(p_cartao, p_fundo))


def test_cartao_sombra(img_print):
    fundo = fundo_radial()
    cv = fundo.copy()
    recorte = normalizar_recorte(None, img_print.size, detectar_area_foto(img_print))
    desenhar_cartao(cv, img_print, recorte)
    p_sombra = cv.getpixel((220, 990))[:3]
    p_fundo = fundo.getpixel((220, 990))[:3]
    assert all(a < b for a, b in zip(p_sombra, p_fundo))


def test_etiqueta_azul():
    cv = fundo_radial()
    desenhar_etiqueta(cv, "aplicação na porta")
    assert cv.getpixel((74, 712))[:3] == ETIQ_COR


def test_etiqueta_contorno():
    cv = fundo_radial()
    x0, y0, x1, y1 = desenhar_etiqueta(cv, "aplicação na porta")
    assert (x0, y0) == ETIQ_POS
    assert cv.getpixel(((x0 + x1) // 2, y0 + 1))[:3] == (255, 255, 255) and y1 - y0 == ETIQ_ALT


def test_etiqueta_maiusculas_e_texto_branco():
    cv_min = fundo_radial()
    cv_mai = fundo_radial()
    box_min = desenhar_etiqueta(cv_min, "aplicação na porta")
    box_mai = desenhar_etiqueta(cv_mai, "APLICAÇÃO NA PORTA")
    assert box_min == box_mai
    assert np.array_equal(np.asarray(cv_min), np.asarray(cv_mai))
    regiao = np.asarray(cv_min.crop(box_min))
    assert np.any((regiao[..., 0] == 255) & (regiao[..., 1] == 255) & (regiao[..., 2] == 255))


def test_cartao_e_etiqueta_canvas_rgba(img_print):
    cv_rgb = fundo_radial()
    cv_rgba = cv_rgb.convert("RGBA")
    recorte = normalizar_recorte(None, img_print.size, detectar_area_foto(img_print))

    box_c_rgb = desenhar_cartao(cv_rgb, img_print, recorte)
    box_c_rgba = desenhar_cartao(cv_rgba, img_print, recorte)
    box_e_rgb = desenhar_etiqueta(cv_rgb, "aplicação na porta")
    box_e_rgba = desenhar_etiqueta(cv_rgba, "aplicação na porta")

    assert box_c_rgb == box_c_rgba == (CARTAO_POS[0], CARTAO_POS[1], 406, 983)
    assert box_e_rgb == box_e_rgba
    assert cv_rgba.mode == "RGBA"
    assert cv_rgba.getpixel((44, 847))[:3] == (255, 255, 255)
    assert cv_rgba.getpixel((74, 712))[:3] == ETIQ_COR


def test_desenhar_cartao_largura_personalizada(img_print):
    cv = fundo_radial()
    recorte = normalizar_recorte(None, img_print.size, detectar_area_foto(img_print))
    box = desenhar_cartao(cv, img_print, recorte, largura=420)
    esp_ph = round(420 * 255 / 350)
    assert box == (40, 983 - (esp_ph + 16), 40 + 420 + 16, 983)


def test_desenhar_etiqueta_tamanho_e_posicao():
    cv = fundo_radial()
    box = desenhar_etiqueta(cv, "porta", tam_fonte=30, pos=(62, 632))
    assert box[0] == 62 and box[1] == 632
    assert box[3] - box[1] == round(ETIQ_ALT * 30 / 24)

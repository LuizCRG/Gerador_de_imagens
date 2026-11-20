"""Testes para recorte do carro e composição multiply no canvas."""

from PIL import Image, ImageDraw

from anuncio.imagens import aplicar_multiply, fundo_radial, recortar_carro
from anuncio.layout import CARRO_ALT_MAX, CARRO_LARG, CARRO_POS


def test_recorte_largura():
    im = Image.new("RGB", (900, 600), (255, 255, 255))
    ImageDraw.Draw(im).rectangle([150, 220, 749, 369], fill=(50, 50, 50))
    c = recortar_carro(im)
    assert c.width == CARRO_LARG and c.height < CARRO_ALT_MAX


def test_recorte_margem(img_carro):
    c = recortar_carro(img_carro)
    assert c.height == CARRO_ALT_MAX and c.width == round(570 * CARRO_ALT_MAX / 330)


def test_carro_largo():
    im = Image.new("RGB", (1000, 100), (50, 50, 50))
    c = recortar_carro(im)
    assert c.width == CARRO_LARG and c.height < CARRO_ALT_MAX


def test_carro_png_transparente():
    im = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([100, 50, 299, 149], fill=(40, 40, 40, 255))
    c = recortar_carro(im)
    assert c.mode == "RGB" and c.getpixel((0, 0)) == (255, 255, 255)


def test_carro_totalmente_branco():
    im = Image.new("RGB", (400, 200), (255, 255, 255))
    c = recortar_carro(im)
    assert c.mode == "RGB" and c.width <= CARRO_LARG and c.height <= CARRO_ALT_MAX


def test_multiply_branco_some(img_carro):
    cv = fundo_radial()
    aplicar_multiply(cv, recortar_carro(img_carro), CARRO_POS)
    assert cv.getpixel((26, 10)) == fundo_radial().getpixel((26, 10))


def test_multiply_escuro_fica(img_carro):
    cv = fundo_radial()
    x0, y0, x1, y1 = aplicar_multiply(cv, recortar_carro(img_carro), CARRO_POS)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    assert max(cv.getpixel((cx, cy))) < 80


def test_multiply_caixa(img_carro):
    cv = fundo_radial()
    c = recortar_carro(img_carro)
    caixa = aplicar_multiply(cv, c, CARRO_POS)
    assert caixa == (CARRO_POS[0], CARRO_POS[1], CARRO_POS[0] + c.width, CARRO_POS[1] + c.height)


def test_multiply_canvas_rgba(img_carro):
    cv = fundo_radial().convert("RGBA")
    c = recortar_carro(img_carro)
    x0, y0, x1, y1 = aplicar_multiply(cv, c, CARRO_POS)
    assert cv.getpixel((26, 10))[:3] == fundo_radial().getpixel((26, 10))
    assert max(cv.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))[:3]) < 80

"""Testes para abertura, remoção de fundo branco, encaixe e glow da peça."""

import io

import numpy as np
from PIL import Image, ImageDraw

from anuncio.imagens import (
    abrir_imagem,
    compor_peca,
    encaixar_peca,
    fundo_radial,
    remover_fundo_branco,
)
from conftest import CENTRO_FURO, PONTO_PRETO


def test_branco_vira_transparente(img_peca):
    r = remover_fundo_branco(img_peca)
    assert r.getpixel((5, 5))[3] == 0


def test_preto_fica_opaco(img_peca):
    assert remover_fundo_branco(img_peca).getpixel(PONTO_PRETO)[3] == 255


def test_furo_transparente(img_peca):
    assert remover_fundo_branco(img_peca).getpixel(CENTRO_FURO)[3] == 0


def test_borda_suave(img_peca):
    a = np.array(remover_fundo_branco(img_peca))[..., 3]
    assert ((a > 0) & (a < 255)).sum() > 0


def test_png_transparente_preservado():
    im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rectangle([25, 25, 74, 74], fill=(255, 255, 255, 255))

    r = remover_fundo_branco(im)
    assert r.getpixel((50, 50)) == (255, 255, 255, 255)
    assert r.getpixel((5, 5))[3] == 0


def test_encaixar_alta(img_peca):
    p, (x, y) = encaixar_peca(remover_fundo_branco(img_peca))
    assert p.height == 1000 and y == 12 and 420 <= x and x + p.width <= 1000


def test_encaixar_larga():
    peca = Image.new("RGBA", (1200, 200), (0, 0, 0, 255))
    p, (x, y) = encaixar_peca(peca)
    assert p.width == 580 and x == 420 and abs((y + p.height / 2) - 512) <= 1


def test_encaixar_escala(img_peca):
    rgba = remover_fundo_branco(img_peca)
    p, _ = encaixar_peca(rgba, escala=0.9)
    assert p.height == 900


def test_glow_azul_perto_da_peca(img_peca):
    peca, pos = encaixar_peca(remover_fundo_branco(img_peca))
    canvas = fundo_radial().convert("RGBA")
    compor_peca(canvas, peca, pos)

    r, _, b, _ = canvas.getpixel((pos[0] - 10, pos[1] + peca.height - 50))
    assert b > r + 15


def test_glow_some_longe(img_peca):
    fundo = fundo_radial()
    peca, pos = encaixar_peca(remover_fundo_branco(img_peca))
    canvas = fundo.convert("RGBA")
    compor_peca(canvas, peca, pos)

    assert canvas.getpixel((100, 100))[:3] == fundo.getpixel((100, 100))


def test_exif_rotacao(tmp_path):
    caminho = tmp_path / "rotacionada.jpg"
    im = Image.new("RGB", (100, 50), (20, 40, 60))
    exif = im.getexif()
    exif[274] = 6  # Orientation = Rotate 90 CW (270 CCW in Pillow)
    im.save(caminho, format="JPEG", exif=exif)

    aberta = abrir_imagem(caminho)
    assert aberta.size == (50, 100) and aberta.mode == "RGB"


def test_cmyk_vira_rgb(tmp_path):
    caminho_cmyk = tmp_path / "cmyk.jpg"
    im = Image.new("CMYK", (40, 40), (0, 128, 128, 0))
    im.save(caminho_cmyk, format="JPEG")

    assert abrir_imagem(caminho_cmyk).mode == "RGB"


def test_abrir_bytes_str_e_transparencia(tmp_path):
    im_rgba = Image.new("RGBA", (30, 20), (0, 0, 0, 0))
    buf = io.BytesIO()
    im_rgba.save(buf, format="PNG")
    assert abrir_imagem(buf.getvalue()).mode == "RGBA"

    caminho_paleta = tmp_path / "paleta_transp.png"
    im_p = Image.new("P", (30, 20), 0)
    im_p.putpalette([255, 0, 0, 0, 255, 0])
    im_p.save(caminho_paleta, format="PNG", transparency=0)
    aberta_p = abrir_imagem(str(caminho_paleta))
    assert aberta_p.mode == "RGBA" and aberta_p.getpixel((0, 0))[3] == 0


def test_encaixar_vazia():
    vazia = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    p, (x, y) = encaixar_peca(vazia)
    assert p.size[0] >= 1 and p.size[1] >= 1
    assert 420 <= x <= 1000 and 12 <= y <= 1012

"""Testes para o fundo radial do anúncio."""

from anuncio.imagens import fundo_radial


def test_fundo_centro_branco():
    assert fundo_radial().getpixel((760, 480)) == (255, 255, 255)


def test_fundo_borda():
    assert fundo_radial().getpixel((0, 1023)) == (228, 234, 243)  # dist 934 > 700


def test_fundo_meio():
    # (410, 480) está a 350 px -> metade do caminho
    p = fundo_radial().getpixel((410, 480))
    assert all(abs(a - b) <= 1 for a, b in zip(p, (241.5, 244.5, 249)))


def test_fundo_tamanho():
    im = fundo_radial()
    assert im.size == (1024, 1024) and im.mode == "RGB"

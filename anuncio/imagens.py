"""Funções de geração e processamento de imagens do anúncio."""

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps
from scipy.ndimage import maximum_filter

from anuncio.layout import (
    CAIXA_PECA,
    CANVAS,
    CARRO_ALT_MAX,
    CARRO_LARG,
    CARRO_MARGEM,
    FUNDO_CENTRO,
    FUNDO_COR_BORDA,
    FUNDO_COR_CENTRO,
    FUNDO_RAIO,
    GLOW,
)

_BRANCO_ALFA_CORTE = 250
_LUMINANCIA_OPACA = 215.0
_LUMINANCIA_TRANSP = 247.0
_CARRO_LIMIAR_BRANCO = 245


def fundo_radial() -> Image.Image:
    """Gera o fundo radial 1024x1024 RGB interpolando do centro branco até a borda."""
    yy, xx = np.ogrid[:CANVAS, :CANVAS]
    cx, cy = FUNDO_CENTRO
    dist = np.hypot(xx - cx, yy - cy)
    t = np.clip(dist / FUNDO_RAIO, 0.0, 1.0)[..., None]

    centro = np.array(FUNDO_COR_CENTRO, dtype=np.float64)
    borda = np.array(FUNDO_COR_BORDA, dtype=np.float64)
    arr = np.rint(centro + (borda - centro) * t).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


def abrir_imagem(dados: bytes | str | Path) -> Image.Image:
    """Abre imagem de bytes ou caminho, corrige orientação EXIF e converte para RGBA ou RGB."""
    origem = io.BytesIO(dados) if isinstance(dados, (bytes, bytearray, memoryview)) else dados
    with Image.open(origem) as im:
        corrigida = ImageOps.exif_transpose(im)
        return corrigida.convert("RGBA" if im.has_transparency_data else "RGB")


def remover_fundo_branco(img: Image.Image) -> Image.Image:
    """Remove fundo branco por luminosidade, preservando alfa preexistente quando houver."""
    if img.has_transparency_data:
        rgba = img.convert("RGBA")
        if (np.asarray(rgba.getchannel("A")) < _BRANCO_ALFA_CORTE).any():
            return rgba

    rgb = np.asarray(img.convert("RGB"), dtype=np.float64)
    luminancia = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    alfa = np.clip(
        (_LUMINANCIA_TRANSP - luminancia) / (_LUMINANCIA_TRANSP - _LUMINANCIA_OPACA),
        0.0,
        1.0,
    )

    alfa_u8 = np.rint(alfa * 255.0).astype(np.uint8)
    alfa_suave = Image.fromarray(alfa_u8, mode="L").filter(ImageFilter.GaussianBlur(0.6))
    a = np.asarray(alfa_suave, dtype=np.float64)[..., None] / 255.0

    # Descontamina halo branco residual nas bordas semitransparentes
    a_seguro = np.where(a > 0.0, a, 1.0)
    rgb_limpo = np.where(
        a > 0.0,
        np.clip((rgb - 255.0 * (1.0 - a)) / a_seguro, 0.0, 255.0),
        0.0,
    )

    saida = np.dstack([np.rint(rgb_limpo).astype(np.uint8), np.asarray(alfa_suave)])
    return Image.fromarray(saida, mode="RGBA")


def encaixar_peca(peca: Image.Image, escala: float = 1.0) -> tuple[Image.Image, tuple[int, int]]:
    """Recorta a peça ao bbox do alfa e redimensiona proporcionalmente para caber em CAIXA_PECA * escala."""
    rgba = peca if peca.mode == "RGBA" else peca.convert("RGBA")
    x0, y0, x1, y1 = CAIXA_PECA
    caixa_w = x1 - x0
    caixa_h = y1 - y0

    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        cx = x0 + caixa_w // 2
        cy = y0 + caixa_h // 2
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), (cx, cy)

    recortada = rgba.crop(bbox)
    w, h = recortada.size
    fator = min((caixa_w * escala) / w, (caixa_h * escala) / h)
    nova_w = max(1, round(w * fator))
    nova_h = max(1, round(h * fator))

    redimensionada = recortada.resize((nova_w, nova_h), Image.Resampling.LANCZOS)
    pos_x = x0 + (caixa_w - nova_w) // 2
    pos_y = y0 + (caixa_h - nova_h) // 2
    return redimensionada, (pos_x, pos_y)


def compor_peca(canvas: Image.Image, peca: Image.Image, pos: tuple[int, int]) -> None:
    """Compõe o glow em 3 camadas e a peça no canvas RGBA em memória (in-place)."""
    if canvas.mode != "RGBA":
        raise ValueError(f"canvas deve estar no modo RGBA, recebido: {canvas.mode}")

    peca_rgba = peca if peca.mode == "RGBA" else peca.convert("RGBA")
    mascara_base = Image.new("L", canvas.size, 0)
    mascara_base.paste(peca_rgba.getchannel("A"), pos)
    alfa_base = np.asarray(mascara_base)

    for cor, dilat, blur, opac in GLOW:
        dilatada = maximum_filter(alfa_base, size=dilat, mode="constant", cval=0)
        borrada = Image.fromarray(dilatada, mode="L").filter(ImageFilter.GaussianBlur(blur))
        alfa_camada = np.rint(np.asarray(borrada, dtype=np.float64) * opac).astype(np.uint8)

        camada = Image.new("RGBA", canvas.size, (*cor, 0))
        camada.putalpha(Image.fromarray(alfa_camada, mode="L"))
        canvas.alpha_composite(camada)

    canvas.alpha_composite(peca_rgba, dest=pos)


def recortar_carro(img: Image.Image) -> Image.Image:
    """Recorta o carro ao bbox não-branco com margem e redimensiona para CARRO_LARG x CARRO_ALT_MAX."""
    if img.has_transparency_data:
        rgba = img.convert("RGBA")
        fundo_branco = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        rgb = Image.alpha_composite(fundo_branco, rgba).convert("RGB")
    elif img.mode != "RGB":
        rgb = img.convert("RGB")
    else:
        rgb = img

    arr = np.asarray(rgb)
    ys, xs = np.where(arr.min(axis=2) < _CARRO_LIMIAR_BRANCO)
    if xs.size == 0:
        recorte = rgb
    else:
        x0 = max(0, int(xs.min()) - CARRO_MARGEM)
        y0 = max(0, int(ys.min()) - CARRO_MARGEM)
        x1 = min(rgb.width, int(xs.max()) + 1 + CARRO_MARGEM)
        y1 = min(rgb.height, int(ys.max()) + 1 + CARRO_MARGEM)
        recorte = rgb.crop((x0, y0, x1, y1))

    crop_w, crop_h = recorte.size
    nova_w = CARRO_LARG
    nova_h = max(1, round(crop_h * CARRO_LARG / crop_w))
    if nova_h > CARRO_ALT_MAX:
        nova_h = CARRO_ALT_MAX
        nova_w = max(1, round(crop_w * CARRO_ALT_MAX / crop_h))
    return recorte.resize((nova_w, nova_h), Image.Resampling.LANCZOS)


def aplicar_multiply(
    canvas: Image.Image,
    img: Image.Image,
    pos: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Compõe a imagem sobre o canvas com blend multiply e devolve a caixa (x0, y0, x1, y1)."""
    x0, y0 = pos
    x1 = x0 + img.width
    y1 = y0 + img.height
    regiao_rgb = canvas.crop((x0, y0, x1, y1)).convert("RGB")
    img_rgb = img if img.mode == "RGB" else img.convert("RGB")
    multiplicada = ImageChops.multiply(regiao_rgb, img_rgb)
    canvas.paste(multiplicada, pos)
    return (x0, y0, x1, y1)

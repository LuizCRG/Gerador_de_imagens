"""Funções de geração e processamento de imagens do anúncio."""

import numpy as np
from PIL import Image

from anuncio.layout import (
    CANVAS,
    FUNDO_CENTRO,
    FUNDO_COR_BORDA,
    FUNDO_COR_CENTRO,
    FUNDO_RAIO,
)


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

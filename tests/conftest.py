"""Fixtures compartilhadas para os testes da suíte anuncio."""

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PONTO_PRETO = (270, 200)
CENTRO_FURO = (300, 450)


@pytest.fixture
def img_carro() -> Image.Image:
    """Foto sintética de carro em fundo branco (900x600 RGB)."""
    im = Image.new("RGB", (900, 600), (255, 255, 255))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([200, 150, 699, 419], radius=24, fill=(60, 60, 60))
    draw.rectangle([180, 420, 719, 449], fill=(180, 180, 180))
    return im


@pytest.fixture
def img_peca() -> Image.Image:
    """Peça sintética em L com furo circular branco em fundo branco (400x900 RGB)."""
    im = Image.new("RGB", (400, 900), (255, 255, 255))
    draw = ImageDraw.Draw(im)
    draw.rectangle([250, 20, 349, 879], fill=(0, 0, 0))
    draw.rectangle([50, 750, 349, 879], fill=(0, 0, 0))
    draw.ellipse([280, 430, 320, 470], fill=(255, 255, 255))
    return im


@pytest.fixture
def img_print() -> Image.Image:
    """Print sintético de celular (720x1600 RGB) com topo preto, foto e barra inferior."""
    arr = np.zeros((1600, 720, 3), dtype=np.uint8)
    rng = np.random.default_rng(42)

    # Foto texturizada e colorida em y 120..1400 (media >= 25 e std >= 6 em toda linha/coluna)
    y_idx = np.arange(1280)[:, None, None]
    x_idx = np.arange(720)[None, :, None]
    base = np.zeros((1280, 720, 3), dtype=np.int16)
    base[..., 0] = (80 + (x_idx[..., 0] % 120))
    base[..., 1] = (100 + (y_idx[..., 0] % 110))
    base[..., 2] = (90 + ((x_idx[..., 0] + y_idx[..., 0]) % 100))
    noise = rng.integers(-40, 41, size=(1280, 720, 3), dtype=np.int16)
    arr[120:1400] = np.clip(base + noise, 0, 255).astype(np.uint8)

    # Barra de navegacao inferior uniforme em y 1400..1600
    arr[1400:1600] = (40, 40, 40)
    return Image.fromarray(arr, mode="RGB")

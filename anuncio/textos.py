"""Quebra, posicionamento, desenho e máscaras dos textos do anúncio."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from anuncio.layout import (
    CANVAS,
    FONTE_BLACK,
    FONTE_EXTRABOLD,
    SUB_COR,
    SUB_DESLOC,
    SUB_ENTRELINHA,
    SUB_TAM,
    SUB_X,
    TITULO_COR,
    TITULO_DESLOC,
    TITULO_ENTRELINHA,
    TITULO_LARG_MAX,
    TITULO_TAM,
    TITULO_X,
)

_TITULO_PASSO = 2
_TITULO_TAM_MIN = 8
_SUB_MAX_LINHAS = 3


@dataclass
class Textos:
    """Posicionamento e tipografia calculados para título e subtítulo."""

    linhas_titulo: list[str]
    baselines_titulo: list[int]
    tam_titulo: int
    linhas_sub: list[str]
    baselines_sub: list[int]
    tam_sub: int


def _carregar_fonte(caminho: Path, tamanho: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(caminho), tamanho)


def _cor_para_modo(cor: tuple[int, int, int], mode: str) -> tuple[int, ...]:
    return (*cor, 255) if mode == "RGBA" else cor


def _desenhar_bloco(
    draw: ImageDraw.ImageDraw,
    linhas: list[str],
    baselines: list[int],
    x: int,
    caminho_fonte: Path,
    tamanho: int,
    cor: tuple[int, ...] | int,
) -> None:
    if not linhas:
        return
    fonte = _carregar_fonte(caminho_fonte, tamanho)
    for linha, y in zip(linhas, baselines, strict=True):
        draw.text((x, y), linha, font=fonte, fill=cor, anchor="ls")


def _mascara_bloco(
    linhas: list[str],
    baselines: list[int],
    x: int,
    caminho_fonte: Path,
    tamanho: int,
) -> np.ndarray:
    img = Image.new("L", (CANVAS, CANVAS), 0)
    _desenhar_bloco(ImageDraw.Draw(img), linhas, baselines, x, caminho_fonte, tamanho, 255)
    return np.asarray(img) > 0


def quebrar_titulo(titulo: str, fonte: ImageFont.FreeTypeFont) -> list[str]:
    """Quebra o título em até 2 linhas equilibradas pela menor largura máxima."""
    palavras = titulo.split()
    if not palavras:
        return []
    if len(palavras) == 1:
        return [palavras[0]]

    melhor_linhas: list[str] = []
    melhor_custo: tuple[float, float] | None = None
    for i in range(1, len(palavras)):
        l1 = " ".join(palavras[:i])
        l2 = " ".join(palavras[i:])
        w1 = fonte.getlength(l1)
        w2 = fonte.getlength(l2)
        custo = (max(w1, w2), abs(w1 - w2))
        if melhor_custo is None or custo < melhor_custo:
            melhor_custo = custo
            melhor_linhas = [l1, l2]
    return melhor_linhas


def posicionar_textos(
    base_carro: int,
    titulo: str,
    subtitulo: list[str],
    tam_titulo: int = TITULO_TAM,
    tam_sub: int = SUB_TAM,
) -> Textos:
    """Calcula quebras, redução de fonte do título e baselines de título e subtítulo."""
    if not titulo.strip():
        raise ValueError("Título obrigatório")

    linhas_sub = [linha.strip().upper() for linha in subtitulo if linha.strip()]
    if len(linhas_sub) > _SUB_MAX_LINHAS:
        raise ValueError("Subtítulo tem mais de 3 linhas")

    tam_atual = tam_titulo
    fonte_titulo = _carregar_fonte(FONTE_BLACK, tam_atual)
    linhas_titulo = quebrar_titulo(titulo, fonte_titulo)

    while (
        tam_atual > _TITULO_TAM_MIN
        and max(fonte_titulo.getlength(linha) for linha in linhas_titulo) > TITULO_LARG_MAX
    ):
        tam_atual = max(_TITULO_TAM_MIN, tam_atual - _TITULO_PASSO)
        fonte_titulo = _carregar_fonte(FONTE_BLACK, tam_atual)

    s_t = tam_atual / TITULO_TAM
    b1 = round(base_carro + TITULO_DESLOC * s_t)
    baselines_titulo = [b1]
    if len(linhas_titulo) == 2:
        baselines_titulo.append(round(b1 + TITULO_ENTRELINHA * s_t))

    baselines_sub: list[int] = []
    if linhas_sub:
        s_s = tam_sub / SUB_TAM
        sb0 = round(baselines_titulo[-1] + SUB_DESLOC * s_s)
        baselines_sub = [
            round(sb0 + i * SUB_ENTRELINHA * s_s) for i in range(len(linhas_sub))
        ]

    return Textos(
        linhas_titulo=linhas_titulo,
        baselines_titulo=baselines_titulo,
        tam_titulo=tam_atual,
        linhas_sub=linhas_sub,
        baselines_sub=baselines_sub,
        tam_sub=tam_sub,
    )


def desenhar_textos(canvas: Image.Image, t: Textos) -> None:
    """Desenha título e subtítulo alinhados à esquerda pelas baselines no canvas (in-place)."""
    draw = ImageDraw.Draw(canvas)
    _desenhar_bloco(
        draw,
        t.linhas_titulo,
        t.baselines_titulo,
        TITULO_X,
        FONTE_BLACK,
        t.tam_titulo,
        _cor_para_modo(TITULO_COR, canvas.mode),
    )
    _desenhar_bloco(
        draw,
        t.linhas_sub,
        t.baselines_sub,
        SUB_X,
        FONTE_EXTRABOLD,
        t.tam_sub,
        _cor_para_modo(SUB_COR, canvas.mode),
    )


def mascara_textos(t: Textos) -> tuple[np.ndarray, np.ndarray]:
    """Renderiza máscaras booleanas 1024x1024 da tinta do título e do subtítulo."""
    m_titulo = _mascara_bloco(
        t.linhas_titulo,
        t.baselines_titulo,
        TITULO_X,
        FONTE_BLACK,
        t.tam_titulo,
    )
    m_sub = _mascara_bloco(
        t.linhas_sub,
        t.baselines_sub,
        SUB_X,
        FONTE_EXTRABOLD,
        t.tam_sub,
    )
    return m_titulo, m_sub

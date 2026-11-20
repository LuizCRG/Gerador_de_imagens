"""Montagem completa do anúncio com verificação de colisões e autocorreção."""

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFont
from scipy.ndimage import maximum_filter

from anuncio.cartao import (
    desenhar_cartao,
    desenhar_etiqueta,
    detectar_area_foto,
    normalizar_recorte,
)
from anuncio.imagens import (
    aplicar_multiply,
    compor_peca,
    encaixar_peca,
    fundo_radial,
    recortar_carro,
    remover_fundo_branco,
)
from anuncio.layout import (
    CANVAS,
    CARRO_POS,
    CARTAO_BORDA,
    CARTAO_POS,
    ETIQ_ALT,
    ETIQ_PAD,
    ETIQ_POS,
    ETIQ_TAM,
    FONTE_EXTRABOLD,
    PRINT_TAM,
    SUB_TAM,
    TITULO_TAM,
)
from anuncio.textos import Textos, desenhar_textos, mascara_textos, posicionar_textos

_PECA_ALFA_CORTE = 32
_PECA_DILAT_TAM = 13
_CARRO_LIMIAR_BRANCO = 245
_ETIQ_MARGEM_SUB = 6

_MAX_ITER = 80
_TITULO_MIN_CORRECAO = 72
_TITULO_PASSO = 2
_SUB_MIN_CORRECAO = 26
_SUB_PASSO = 2
_ESCALA_MIN = 0.5
_ESCALA_PASSO = 0.03


@dataclass
class Entrada:
    """Dados de entrada para a montagem de um anúncio."""

    carro: Image.Image
    peca: Image.Image
    print_img: Image.Image
    titulo: str
    subtitulo: list[str]
    etiqueta: str
    recorte_print: tuple[int, int, int, int] | None = None


@dataclass
class Resultado:
    """Resultado da montagem final com imagem RGB, avisos e parâmetros ajustados."""

    imagem: Image.Image
    avisos: list[str]
    tam_titulo: int
    tam_sub: int
    escala_peca: float
    recorte_print: tuple[int, int, int, int]


def _caixa_tinta_carro(carro_rec: Image.Image) -> tuple[int, int, int, int]:
    cx, cy = CARRO_POS
    arr = np.asarray(carro_rec)
    ys, xs = np.where(arr.min(axis=2) < _CARRO_LIMIAR_BRANCO)
    if xs.size == 0:
        return (cx, cy, cx + carro_rec.width, cy + carro_rec.height)
    return (
        cx + int(xs.min()),
        cy + int(ys.min()),
        cx + int(xs.max()) + 1,
        cy + int(ys.max()) + 1,
    )


def _caixa_cartao() -> tuple[int, int, int, int]:
    x0, y0 = CARTAO_POS
    larg = PRINT_TAM[0] + 2 * CARTAO_BORDA
    alt = PRINT_TAM[1] + 2 * CARTAO_BORDA
    return (x0, y0, x0 + larg, y0 + alt)


def _caixa_etiqueta(texto: str) -> tuple[int, int, int, int]:
    fonte = ImageFont.truetype(str(FONTE_EXTRABOLD), ETIQ_TAM)
    larg = max(ETIQ_ALT, round(fonte.getlength(texto.upper()) + ETIQ_PAD))
    x0, y0 = ETIQ_POS
    return (x0, y0, x0 + larg, y0 + ETIQ_ALT)


def _mascara_peca(peca: Image.Image, pos: tuple[int, int]) -> np.ndarray:
    px, py = pos
    alfa = np.asarray(peca.getchannel("A")) > _PECA_ALFA_CORTE
    base = np.zeros((CANVAS, CANVAS), dtype=bool)
    dx0 = max(0, px)
    dy0 = max(0, py)
    dx1 = min(CANVAS, px + peca.width)
    dy1 = min(CANVAS, py + peca.height)
    if dx0 < dx1 and dy0 < dy1:
        base[dy0:dy1, dx0:dx1] = alfa[dy0 - py : dy1 - py, dx0 - px : dx1 - px]
    return maximum_filter(base, size=_PECA_DILAT_TAM, mode="constant", cval=0)


def _caixa_toca_mascara(
    mascara: np.ndarray,
    caixa: tuple[int, int, int, int],
) -> bool:
    x0, y0, x1, y1 = caixa
    cx0 = max(0, x0)
    cy0 = max(0, y0)
    cx1 = min(mascara.shape[1], x1)
    cy1 = min(mascara.shape[0], y1)
    if cx0 >= cx1 or cy0 >= cy1:
        return False
    return bool(mascara[cy0:cy1, cx0:cx1].any())


def _caixa_fora_canvas(caixa: tuple[int, int, int, int]) -> bool:
    x0, y0, x1, y1 = caixa
    return x0 < 0 or y0 < 0 or x1 > CANVAS or y1 > CANVAS


def _toca_borda(mascara: np.ndarray) -> bool:
    return bool(
        mascara[0, :].any()
        or mascara[-1, :].any()
        or mascara[:, 0].any()
        or mascara[:, -1].any()
    )


def verificar(
    mascara_peca: np.ndarray,
    m_titulo: np.ndarray,
    m_sub: np.ndarray,
    caixa_carro_tinta: tuple[int, int, int, int],
    caixa_cartao: tuple[int, int, int, int],
    caixa_etiqueta: tuple[int, int, int, int],
) -> list[str]:
    """Verifica colisões entre elementos e extravasamento do canvas."""
    problemas: list[str] = []

    if (m_titulo & mascara_peca).any():
        problemas.append("titulo_x_peca")
    if (m_sub & mascara_peca).any():
        problemas.append("sub_x_peca")

    limite_sub_y = max(0, caixa_etiqueta[1] - _ETIQ_MARGEM_SUB)
    if m_sub[limite_sub_y:, :].any():
        problemas.append("sub_x_etiqueta")

    if _caixa_toca_mascara(mascara_peca, caixa_carro_tinta):
        problemas.append("carro_x_peca")
    if _caixa_toca_mascara(mascara_peca, caixa_cartao):
        problemas.append("cartao_x_peca")

    fora_caixas = any(
        _caixa_fora_canvas(caixa)
        for caixa in (caixa_carro_tinta, caixa_cartao, caixa_etiqueta)
    )
    fora_mascaras = any(
        _toca_borda(mascara)
        for mascara in (mascara_peca, m_titulo, m_sub)
    )
    if fora_caixas or fora_mascaras:
        problemas.append("fora_do_canvas")

    return problemas


def _proximo_ajuste(
    problemas: list[str],
    tam_t: int,
    tam_s: int,
    escala: float,
) -> tuple[int, int, float, bool]:
    sub_colide = "sub_x_peca" in problemas or "sub_x_etiqueta" in problemas
    if "titulo_x_peca" in problemas and tam_t > _TITULO_MIN_CORRECAO:
        return max(_TITULO_MIN_CORRECAO, tam_t - _TITULO_PASSO), tam_s, escala, True
    if sub_colide and tam_t > _TITULO_MIN_CORRECAO:
        return max(_TITULO_MIN_CORRECAO, tam_t - _TITULO_PASSO), tam_s, escala, True
    if sub_colide and tam_s > _SUB_MIN_CORRECAO:
        return tam_t, max(_SUB_MIN_CORRECAO, tam_s - _SUB_PASSO), escala, True
    if escala > _ESCALA_MIN:
        return tam_t, tam_s, max(_ESCALA_MIN, round(escala - _ESCALA_PASSO, 4)), True
    return tam_t, tam_s, escala, False


def _gerar_avisos(
    tam_titulo: int,
    tam_sub: int,
    escala: float,
    problemas: list[str],
) -> list[str]:
    avisos: list[str] = []
    if tam_titulo < TITULO_TAM:
        avisos.append(f"Título reduzido de {TITULO_TAM} para {tam_titulo} px")
    if tam_sub < SUB_TAM:
        avisos.append(f"Subtítulo reduzido de {SUB_TAM} para {tam_sub} px")
    if escala < 1.0:
        avisos.append(f"Peça reduzida para {round(escala * 100)}%")
    for cod in problemas:
        avisos.append(f"Não foi possível eliminar: {cod}")
    return avisos


def montar(e: Entrada) -> Resultado:
    """Executa recorte, verificação/autocorreção em laço e composição final do anúncio."""
    peca_sem_fundo = remover_fundo_branco(e.peca)
    carro_rec = recortar_carro(e.carro)
    base_carro = CARRO_POS[1] + carro_rec.height
    area = detectar_area_foto(e.print_img)
    recorte = normalizar_recorte(e.recorte_print, e.print_img.size, area)

    caixa_carro_tinta = _caixa_tinta_carro(carro_rec)
    caixa_cartao = _caixa_cartao()
    caixa_etiqueta = _caixa_etiqueta(e.etiqueta)

    tam_t = TITULO_TAM
    tam_s = SUB_TAM
    escala = 1.0
    escala_cache: float | None = None
    peca_encaixada: Image.Image | None = None
    pos_peca = (0, 0)
    mascara_peca = np.zeros((CANVAS, CANVAS), dtype=bool)
    textos: Textos | None = None
    problemas: list[str] = []

    def _avaliar() -> tuple[Textos, list[str]]:
        nonlocal escala_cache, peca_encaixada, pos_peca, mascara_peca, tam_t, tam_s
        if escala != escala_cache:
            peca_encaixada, pos_peca = encaixar_peca(peca_sem_fundo, escala=escala)
            mascara_peca = _mascara_peca(peca_encaixada, pos_peca)
            escala_cache = escala
        t = posicionar_textos(
            base_carro,
            e.titulo,
            e.subtitulo,
            tam_titulo=tam_t,
            tam_sub=tam_s,
        )
        tam_t = t.tam_titulo
        tam_s = t.tam_sub
        m_titulo, m_sub = mascara_textos(t)
        probs = verificar(
            mascara_peca,
            m_titulo,
            m_sub,
            caixa_carro_tinta,
            caixa_cartao,
            caixa_etiqueta,
        )
        return t, probs

    for _ in range(_MAX_ITER):
        textos, problemas = _avaliar()
        if not problemas:
            break
        tam_t, tam_s, escala, ajustou = _proximo_ajuste(problemas, tam_t, tam_s, escala)
        if not ajustou:
            break
    else:
        textos, problemas = _avaliar()

    assert peca_encaixada is not None and textos is not None
    canvas = fundo_radial().convert("RGBA")
    compor_peca(canvas, peca_encaixada, pos_peca)
    aplicar_multiply(canvas, carro_rec, CARRO_POS)
    desenhar_textos(canvas, textos)
    desenhar_cartao(canvas, e.print_img, recorte)
    desenhar_etiqueta(canvas, e.etiqueta)

    return Resultado(
        imagem=canvas.convert("RGB"),
        avisos=_gerar_avisos(textos.tam_titulo, textos.tam_sub, escala, problemas),
        tam_titulo=textos.tam_titulo,
        tam_sub=textos.tam_sub,
        escala_peca=escala,
        recorte_print=recorte,
    )

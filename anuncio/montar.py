"""Montagem completa do anúncio com verificação de colisões e autocorreção."""

from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy.ndimage import maximum_filter

from anuncio.cartao import (
    caixa_cartao as _caixa_cartao_layout,
    caixa_etiqueta as _caixa_etiqueta_layout,
    desenhar_cartao,
    desenhar_etiqueta,
    detectar_area_foto,
    normalizar_recorte,
    pos_etiqueta_no_cartao,
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
    CAIXA_PECA,
    CANVAS,
    CARRO_ALT_MAX,
    CARRO_LARG,
    CARRO_POS,
    ETIQ_TAM,
    PRINT_TAM,
    SUB_TAM,
    TITULO_LARG_MAX,
    TITULO_TAM,
    TITULO_X,
)
from anuncio.textos import (
    Textos,
    desenhar_textos,
    mascara_textos,
    posicionar_textos,
    textos_fora_canvas,
)

_PECA_ALFA_CORTE = 32
_PECA_DILAT_TAM = 13
_CARRO_LIMIAR_BRANCO = 245
_ETIQ_MARGEM_SUB = 6
_CARTAO_MARGEM_SUB = 14
_TOPO_SEM_CARRO = 20
_MARGEM_LIVRE = 24
_ALT_MIN_CAIXA_PECA = 120

_MAX_ITER = 80
_TITULO_MIN_CORRECAO = 72
_TITULO_PASSO = 2
_SUB_MIN_CORRECAO = 26
_SUB_PASSO = 2
_ESCALA_MIN = 0.5
_ESCALA_PASSO = 0.03
_PROBLEMAS_PECA = frozenset({
    "titulo_x_peca",
    "sub_x_peca",
    "carro_x_peca",
    "cartao_x_peca",
})


@dataclass
class Entrada:
    """Dados de entrada para a montagem de um anúncio."""

    carro: Image.Image | None = None
    peca: Image.Image | None = None
    print_img: Image.Image | None = None
    titulo: str = ""
    subtitulo: list[str] = field(default_factory=list)
    etiqueta: str = ""
    recorte_print: tuple[int, int, int, int] | None = None
    recorte_carro: tuple[int, int, int, int] | None = None
    recorte_peca: tuple[int, int, int, int] | None = None
    usar_carro: bool = True
    usar_peca: bool = True
    usar_print: bool = True
    usar_etiqueta: bool = True
    usar_titulo: bool = True
    usar_subtitulo: bool = True
    largura_carro: int = CARRO_LARG
    escala_peca: float = 1.0
    largura_print: int = PRINT_TAM[0]
    tam_titulo: int = TITULO_TAM
    tam_sub: int = SUB_TAM
    tam_etiqueta: int = ETIQ_TAM


@dataclass
class Resultado:
    """Resultado da montagem final com imagem RGB, avisos e parâmetros ajustados."""

    imagem: Image.Image
    avisos: list[str]
    tam_titulo: int
    tam_sub: int
    escala_peca: float
    recorte_print: tuple[int, int, int, int] | None
    recorte_carro: tuple[int, int, int, int] | None = None
    recorte_peca: tuple[int, int, int, int] | None = None


def _recortar_entrada(
    img: Image.Image,
    recorte: tuple[int, int, int, int] | None,
) -> tuple[Image.Image, tuple[int, int, int, int] | None]:
    """Normaliza um retângulo livre dentro da imagem e aplica crop quando informado."""
    if recorte is None:
        return img, None
    img_w, img_h = img.size
    if img_w <= 0 or img_h <= 0:
        return img, (0, 0, img_w, img_h)
    l0, t0, r0, b0 = recorte
    l, r = (l0, r0) if l0 <= r0 else (r0, l0)
    t, b = (t0, b0) if t0 <= b0 else (b0, t0)
    l = max(0, min(l, img_w - 1))
    t = max(0, min(t, img_h - 1))
    r = max(l + 1, min(r, img_w))
    b = max(t + 1, min(b, img_h))
    caixa = (l, t, r, b)
    return img.crop(caixa), caixa


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


def _area_peca_na_caixa(peca: Image.Image, caixa: tuple[int, int, int, int]) -> int:
    bbox = peca.getchannel("A").getbbox()
    if bbox is None:
        return 0
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    cw = max(1, caixa[2] - caixa[0])
    ch = max(1, caixa[3] - caixa[1])
    fator = min(cw / w, ch / h)
    return max(1, round(w * fator)) * max(1, round(h * fator))


def _escolher_caixa_peca(
    peca_sem_fundo: Image.Image,
    e: Entrada,
    y_esq_fim: int,
    caixa_cart: tuple[int, int, int, int],
    caixa_etiq: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    ha_topo_esq = e.usar_carro or e.usar_titulo or e.usar_subtitulo
    if not ha_topo_esq and not e.usar_print:
        return (_MARGEM_LIVRE, _MARGEM_LIVRE, CANVAS - _MARGEM_LIVRE, CANVAS - _MARGEM_LIVRE)

    candidatos = [CAIXA_PECA]
    if not e.usar_print:
        y_livre_inf = max(_MARGEM_LIVRE, y_esq_fim + _MARGEM_LIVRE)
        if CANVAS - _MARGEM_LIVRE - y_livre_inf >= _ALT_MIN_CAIXA_PECA:
            candidatos.append((_MARGEM_LIVRE, y_livre_inf, CANVAS - _MARGEM_LIVRE, CANVAS - _MARGEM_LIVRE))
    elif not ha_topo_esq:
        topo_print = caixa_etiq[1] if e.usar_etiqueta else caixa_cart[1]
        y_livre_sup = min(CANVAS - _MARGEM_LIVRE, topo_print - _MARGEM_LIVRE)
        if y_livre_sup - _MARGEM_LIVRE >= _ALT_MIN_CAIXA_PECA:
            candidatos.append((_MARGEM_LIVRE, _MARGEM_LIVRE, CANVAS - _MARGEM_LIVRE, y_livre_sup))

    return max(candidatos, key=lambda cx: _area_peca_na_caixa(peca_sem_fundo, cx))


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
    titulo_fora: bool = False,
    sub_fora: bool = False,
    *,
    usar_peca: bool = True,
    usar_carro: bool = True,
    usar_print: bool = True,
    usar_etiqueta: bool = True,
    usar_titulo: bool = True,
    usar_subtitulo: bool = True,
) -> list[str]:
    """Verifica colisões entre elementos ativos e extravasamento do canvas."""
    problemas: list[str] = []

    if usar_peca:
        if usar_titulo and (m_titulo & mascara_peca).any():
            problemas.append("titulo_x_peca")
        if usar_subtitulo and (m_sub & mascara_peca).any():
            problemas.append("sub_x_peca")

    if usar_subtitulo and usar_print:
        if usar_etiqueta:
            limite_sub_y = max(0, caixa_etiqueta[1] - _ETIQ_MARGEM_SUB)
        else:
            limite_sub_y = max(0, caixa_cartao[1] - _CARTAO_MARGEM_SUB)
        if m_sub[limite_sub_y:, :].any():
            problemas.append("sub_x_etiqueta")

    if usar_peca:
        if usar_carro and _caixa_toca_mascara(mascara_peca, caixa_carro_tinta):
            problemas.append("carro_x_peca")
        if usar_print and _caixa_toca_mascara(mascara_peca, caixa_cartao):
            problemas.append("cartao_x_peca")

    caixas_ativas: list[tuple[int, int, int, int]] = []
    if usar_carro:
        caixas_ativas.append(caixa_carro_tinta)
    if usar_print:
        caixas_ativas.append(caixa_cartao)
        if usar_etiqueta:
            caixas_ativas.append(caixa_etiqueta)

    mascaras_ativas: list[np.ndarray] = []
    if usar_peca:
        mascaras_ativas.append(mascara_peca)
    if usar_titulo:
        mascaras_ativas.append(m_titulo)
    if usar_subtitulo:
        mascaras_ativas.append(m_sub)

    fora_caixas = any(_caixa_fora_canvas(caixa) for caixa in caixas_ativas)
    fora_mascaras = any(_toca_borda(mascara) for mascara in mascaras_ativas)
    if fora_caixas or fora_mascaras or (usar_titulo and titulo_fora) or (usar_subtitulo and sub_fora):
        problemas.append("fora_do_canvas")

    return problemas


def _proximo_ajuste(
    problemas: list[str],
    tam_t: int,
    tam_s: int,
    escala: float,
    mascara_peca: np.ndarray,
    m_titulo: np.ndarray,
    m_sub: np.ndarray,
    titulo_fora: bool = False,
    sub_fora: bool = False,
    *,
    usar_titulo: bool = True,
    usar_subtitulo: bool = True,
    usar_peca: bool = True,
) -> tuple[int, int, float, bool]:
    sub_colide = "sub_x_peca" in problemas or "sub_x_etiqueta" in problemas
    fora = "fora_do_canvas" in problemas
    titulo_extravasa = titulo_fora or _toca_borda(m_titulo)
    sub_extravasa = sub_fora or _toca_borda(m_sub)
    peca_envolvida = usar_peca and (
        any(p in _PROBLEMAS_PECA for p in problemas) or (fora and _toca_borda(mascara_peca))
    )

    if (
        usar_titulo
        and ("titulo_x_peca" in problemas or (fora and titulo_extravasa))
        and tam_t > _TITULO_MIN_CORRECAO
    ):
        return max(_TITULO_MIN_CORRECAO, tam_t - _TITULO_PASSO), tam_s, escala, True
    if usar_titulo and sub_colide and tam_t > _TITULO_MIN_CORRECAO:
        return max(_TITULO_MIN_CORRECAO, tam_t - _TITULO_PASSO), tam_s, escala, True
    if usar_subtitulo and (sub_colide or (fora and sub_extravasa)) and tam_s > _SUB_MIN_CORRECAO:
        return tam_t, max(_SUB_MIN_CORRECAO, tam_s - _SUB_PASSO), escala, True
    if peca_envolvida and escala > _ESCALA_MIN:
        return tam_t, tam_s, max(_ESCALA_MIN, round(escala - _ESCALA_PASSO, 4)), True
    return tam_t, tam_s, escala, False


def _gerar_avisos(
    tam_titulo: int,
    tam_sub: int,
    escala: float,
    problemas: list[str],
    *,
    tam_titulo_inicial: int = TITULO_TAM,
    tam_sub_inicial: int = SUB_TAM,
    escala_inicial: float = 1.0,
    usar_titulo: bool = True,
    usar_subtitulo: bool = True,
    usar_peca: bool = True,
) -> list[str]:
    avisos: list[str] = []
    if usar_titulo and tam_titulo < tam_titulo_inicial:
        avisos.append(f"Título reduzido de {tam_titulo_inicial} para {tam_titulo} px")
    if usar_subtitulo and tam_sub < tam_sub_inicial:
        avisos.append(f"Subtítulo reduzido de {tam_sub_inicial} para {tam_sub} px")
    if usar_peca and escala < escala_inicial:
        if round(escala_inicial, 4) == 1.0:
            avisos.append(f"Peça reduzida para {round(escala * 100)}%")
        else:
            avisos.append(
                f"Peça reduzida de {round(escala_inicial * 100)}% para {round(escala * 100)}%"
            )
    for cod in problemas:
        avisos.append(f"Não foi possível eliminar: {cod}")
    return avisos


def montar(e: Entrada) -> Resultado:
    """Executa recorte, verificação/autocorreção em laço e composição final do anúncio."""
    if not any((e.usar_carro, e.usar_peca, e.usar_print, e.usar_titulo, e.usar_subtitulo)):
        raise ValueError("Ative pelo menos um elemento para gerar o anúncio.")
    if e.usar_carro and e.carro is None:
        raise ValueError("Envie a foto do carro")
    if e.usar_peca and e.peca is None:
        raise ValueError("Envie a foto da peça")
    if e.usar_print and e.print_img is None:
        raise ValueError("Envie o print de aplicação")

    if e.usar_peca and e.peca is not None:
        img_peca, rec_peca = _recortar_entrada(e.peca, e.recorte_peca)
        peca_sem_fundo = remover_fundo_branco(img_peca)
    else:
        rec_peca = None
        peca_sem_fundo = None

    if e.usar_carro and e.carro is not None:
        img_carro, rec_carro = _recortar_entrada(e.carro, e.recorte_carro)
        altura_max_carro = max(1, round(CARRO_ALT_MAX * e.largura_carro / CARRO_LARG))
        carro_rec = recortar_carro(img_carro, largura=e.largura_carro, altura_max=altura_max_carro)
        base_carro = CARRO_POS[1] + carro_rec.height
        caixa_carro_tinta = _caixa_tinta_carro(carro_rec)
    else:
        rec_carro = None
        carro_rec = None
        base_carro = _TOPO_SEM_CARRO
        caixa_carro_tinta = (0, 0, 0, 0)

    if e.usar_print and e.print_img is not None:
        area = (
            detectar_area_foto(e.print_img)
            if e.recorte_print is None
            else (0, 0, e.print_img.width, e.print_img.height)
        )
        recorte: tuple[int, int, int, int] | None = normalizar_recorte(
            e.recorte_print, e.print_img.size, area
        )
        caixa_cartao = _caixa_cartao_layout(e.largura_print)
        pos_etiq = pos_etiqueta_no_cartao(caixa_cartao, tam_fonte=e.tam_etiqueta)
        caixa_etiqueta = (
            _caixa_etiqueta_layout(e.etiqueta, tam_fonte=e.tam_etiqueta, pos=pos_etiq)
            if e.usar_etiqueta
            else (0, 0, 0, 0)
        )
    else:
        recorte = None
        pos_etiq = (0, 0)
        caixa_cartao = (0, 0, 0, 0)
        caixa_etiqueta = (0, 0, 0, 0)

    larg_max_sem_peca = CANVAS - TITULO_X - 36
    larg_max_titulo = larg_max_sem_peca if not e.usar_peca else TITULO_LARG_MAX

    textos_prev = posicionar_textos(
        base_carro,
        e.titulo,
        e.subtitulo,
        tam_titulo=e.tam_titulo,
        tam_sub=e.tam_sub,
        usar_titulo=e.usar_titulo,
        usar_subtitulo=e.usar_subtitulo,
        larg_max_titulo=larg_max_titulo,
    )
    y_esq_fim = base_carro if e.usar_carro else 0
    if textos_prev.baselines_titulo:
        y_esq_fim = max(y_esq_fim, textos_prev.baselines_titulo[-1] + round(0.25 * textos_prev.tam_titulo))
    if textos_prev.baselines_sub:
        y_esq_fim = max(y_esq_fim, textos_prev.baselines_sub[-1] + round(0.25 * textos_prev.tam_sub))

    if peca_sem_fundo is not None:
        caixa_peca = _escolher_caixa_peca(
            peca_sem_fundo, e, y_esq_fim, caixa_cartao, caixa_etiqueta
        )
        if caixa_peca[0] < CAIXA_PECA[0] and caixa_peca[1] > y_esq_fim:
            larg_max_titulo = larg_max_sem_peca
            textos_larg = posicionar_textos(
                base_carro,
                e.titulo,
                e.subtitulo,
                tam_titulo=e.tam_titulo,
                tam_sub=e.tam_sub,
                usar_titulo=e.usar_titulo,
                usar_subtitulo=e.usar_subtitulo,
                larg_max_titulo=larg_max_titulo,
            )
            y_esq_largo = base_carro if e.usar_carro else 0
            if textos_larg.baselines_titulo:
                y_esq_largo = max(
                    y_esq_largo,
                    textos_larg.baselines_titulo[-1] + round(0.25 * textos_larg.tam_titulo),
                )
            if textos_larg.baselines_sub:
                y_esq_largo = max(
                    y_esq_largo,
                    textos_larg.baselines_sub[-1] + round(0.25 * textos_larg.tam_sub),
                )
            y_livre_inf = max(_MARGEM_LIVRE, y_esq_largo + _MARGEM_LIVRE)
            if CANVAS - _MARGEM_LIVRE - y_livre_inf >= _ALT_MIN_CAIXA_PECA:
                caixa_peca = (_MARGEM_LIVRE, y_livre_inf, CANVAS - _MARGEM_LIVRE, CANVAS - _MARGEM_LIVRE)
    else:
        caixa_peca = CAIXA_PECA

    tam_t = e.tam_titulo
    tam_s = e.tam_sub
    escala = e.escala_peca
    escala_cache: float | None = None
    peca_encaixada: Image.Image | None = None
    pos_peca = (0, 0)
    mascara_peca = np.zeros((CANVAS, CANVAS), dtype=bool)
    textos: Textos | None = None
    problemas: list[str] = []

    def _avaliar() -> tuple[Textos, list[str], np.ndarray, np.ndarray, bool, bool]:
        nonlocal escala_cache, peca_encaixada, pos_peca, mascara_peca, tam_t, tam_s
        if peca_sem_fundo is not None and escala != escala_cache:
            peca_encaixada, pos_peca = encaixar_peca(
                peca_sem_fundo, escala=escala, caixa=caixa_peca
            )
            mascara_peca = _mascara_peca(peca_encaixada, pos_peca)
            escala_cache = escala
        t = posicionar_textos(
            base_carro,
            e.titulo,
            e.subtitulo,
            tam_titulo=tam_t,
            tam_sub=tam_s,
            usar_titulo=e.usar_titulo,
            usar_subtitulo=e.usar_subtitulo,
            larg_max_titulo=larg_max_titulo,
        )
        tam_t = t.tam_titulo
        tam_s = t.tam_sub
        m_titulo, m_sub = mascara_textos(t)
        titulo_fora, sub_fora = textos_fora_canvas(t)
        probs = verificar(
            mascara_peca,
            m_titulo,
            m_sub,
            caixa_carro_tinta,
            caixa_cartao,
            caixa_etiqueta,
            titulo_fora=titulo_fora,
            sub_fora=sub_fora,
            usar_peca=e.usar_peca,
            usar_carro=e.usar_carro,
            usar_print=e.usar_print,
            usar_etiqueta=e.usar_etiqueta,
            usar_titulo=e.usar_titulo,
            usar_subtitulo=e.usar_subtitulo,
        )
        return t, probs, m_titulo, m_sub, titulo_fora, sub_fora

    for _ in range(_MAX_ITER):
        textos, problemas, m_titulo, m_sub, titulo_fora, sub_fora = _avaliar()
        if not problemas:
            break
        tam_t, tam_s, escala, ajustou = _proximo_ajuste(
            problemas,
            tam_t,
            tam_s,
            escala,
            mascara_peca,
            m_titulo,
            m_sub,
            titulo_fora=titulo_fora,
            sub_fora=sub_fora,
            usar_titulo=e.usar_titulo,
            usar_subtitulo=e.usar_subtitulo,
            usar_peca=e.usar_peca,
        )
        if not ajustou:
            break
    else:
        textos, problemas, _, _, _, _ = _avaliar()

    assert textos is not None
    canvas = fundo_radial().convert("RGBA")
    if peca_encaixada is not None:
        compor_peca(canvas, peca_encaixada, pos_peca)
    if carro_rec is not None:
        aplicar_multiply(canvas, carro_rec, CARRO_POS)
    desenhar_textos(canvas, textos)
    if e.usar_print and e.print_img is not None and recorte is not None:
        desenhar_cartao(canvas, e.print_img, recorte, largura=e.largura_print)
        if e.usar_etiqueta:
            desenhar_etiqueta(canvas, e.etiqueta, tam_fonte=e.tam_etiqueta, pos=pos_etiq)

    return Resultado(
        imagem=canvas.convert("RGB"),
        avisos=_gerar_avisos(
            textos.tam_titulo,
            textos.tam_sub,
            escala,
            problemas,
            tam_titulo_inicial=e.tam_titulo,
            tam_sub_inicial=e.tam_sub,
            escala_inicial=e.escala_peca,
            usar_titulo=e.usar_titulo,
            usar_subtitulo=e.usar_subtitulo,
            usar_peca=e.usar_peca,
        ),
        tam_titulo=textos.tam_titulo,
        tam_sub=textos.tam_sub,
        escala_peca=escala,
        recorte_print=recorte,
        recorte_carro=rec_carro,
        recorte_peca=rec_peca,
    )

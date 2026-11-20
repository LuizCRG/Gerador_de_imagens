"""Detecção de área da foto no print, normalização de recorte, cartão e etiqueta."""

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from anuncio.layout import (
    CARTAO_BORDA,
    CARTAO_POS,
    CARTAO_RAIO,
    ETIQ_ALT,
    ETIQ_CONTORNO,
    ETIQ_COR,
    ETIQ_PAD,
    ETIQ_POS,
    ETIQ_TAM,
    FONTE_EXTRABOLD,
    PRINT_RAIO,
    PRINT_TAM,
    SOMBRA_BLUR,
    SOMBRA_DY,
    SOMBRA_OPAC,
)

_AREA_MEDIA_MIN = 25.0
_AREA_STD_MIN = 6.0
_SUPERSAMPLE = 4


def _faixa_valida(valores: np.ndarray, eixo: int) -> tuple[int, int] | None:
    medias = valores.mean(axis=eixo)
    desvios = valores.std(axis=eixo)
    validos = np.flatnonzero((medias >= _AREA_MEDIA_MIN) & (desvios >= _AREA_STD_MIN))
    if validos.size == 0:
        return None
    return int(validos[0]), int(validos[-1]) + 1


def _ajustar_proporcao_na_caixa(max_w: int, max_h: int) -> tuple[int, int]:
    pw, ph = PRINT_TAM
    if max_w * ph >= max_h * pw:
        h = max_h
        w = min(max_w, max(1, round(h * pw / ph)))
    else:
        w = max_w
        h = min(max_h, max(1, round(w * ph / pw)))
    return w, h


def _mascara_arredondada(tamanho: tuple[int, int], raio: int) -> Image.Image:
    w, h = tamanho
    sw, sh = w * _SUPERSAMPLE, h * _SUPERSAMPLE
    mascara = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [0, 0, sw - 1, sh - 1],
        radius=raio * _SUPERSAMPLE,
        fill=255,
    )
    return mascara.resize((w, h), Image.Resampling.BOX)


def _compor_camada(
    canvas: Image.Image,
    camada: Image.Image,
    pos: tuple[int, int] = (0, 0),
) -> None:
    x0, y0 = pos
    dest_x0 = max(0, x0)
    dest_y0 = max(0, y0)
    dest_x1 = min(canvas.width, x0 + camada.width)
    dest_y1 = min(canvas.height, y0 + camada.height)
    if dest_x0 >= dest_x1 or dest_y0 >= dest_y1:
        return

    src_box = (dest_x0 - x0, dest_y0 - y0, dest_x1 - x0, dest_y1 - y0)
    recorte_camada = (
        camada if src_box == (0, 0, camada.width, camada.height) else camada.crop(src_box)
    )

    if canvas.mode == "RGBA":
        canvas.alpha_composite(recorte_camada, dest=(dest_x0, dest_y0))
        return

    caixa = (dest_x0, dest_y0, dest_x1, dest_y1)
    base_rgba = canvas.crop(caixa).convert("RGBA")
    composta = Image.alpha_composite(base_rgba, recorte_camada)
    canvas.paste(composta.convert(canvas.mode), (dest_x0, dest_y0))


def detectar_area_foto(img: Image.Image) -> tuple[int, int, int, int]:
    """Remove faixas escuras ou uniformes a partir das bordas e devolve (l, t, r, b)."""
    w, h = img.size
    if w <= 0 or h <= 0:
        return (0, 0, w, h)

    cinza = np.asarray(img.convert("L"), dtype=np.float64)
    faixa_y = _faixa_valida(cinza, eixo=1)
    if faixa_y is None:
        return (0, 0, w, h)
    t, b = faixa_y

    faixa_x = _faixa_valida(cinza[t:b, :], eixo=0)
    if faixa_x is None:
        return (0, 0, w, h)
    l, r = faixa_x

    if l >= r or t >= b:
        return (0, 0, w, h)
    return (l, t, r, b)


def normalizar_recorte(
    recorte: tuple[int, int, int, int] | None,
    img_size: tuple[int, int],
    area: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    """Inicializa ou corrige o recorte para a proporção 350:255 dentro dos limites da imagem."""
    img_w, img_h = img_size
    if img_w <= 0 or img_h <= 0:
        return (0, 0, img_w, img_h)

    pw, ph = PRINT_TAM

    if recorte is None:
        al, at, ar, ab = area
        al = max(0, min(al, img_w))
        at = max(0, min(at, img_h))
        ar = max(0, min(ar, img_w))
        ab = max(0, min(ab, img_h))
        if al >= ar or at >= ab:
            al, at, ar, ab = 0, 0, img_w, img_h

        aw, ah = ar - al, ab - at
        w, h = _ajustar_proporcao_na_caixa(aw, ah)
        x0 = al + (aw - w) // 2
        y0 = at + (ah - h) // 2
        return (x0, y0, x0 + w, y0 + h)

    l, t, r, b = recorte
    cx = (l + r) / 2
    cy = (t + b) / 2
    w = max(1, round(abs(r - l)))
    h = max(1, round(w * ph / pw))

    if w > img_w or h > img_h:
        w, h = _ajustar_proporcao_na_caixa(img_w, img_h)

    x0 = max(0, min(round(cx - w / 2), img_w - w))
    y0 = max(0, min(round(cy - h / 2), img_h - h))
    return (x0, y0, x0 + w, y0 + h)


def caixa_cartao(largura: int = PRINT_TAM[0]) -> tuple[int, int, int, int]:
    """Calcula a caixa (x0, y0, x1, y1) do cartão branco ancorado na base inferior esquerda."""
    pw = max(1, int(largura))
    ph = max(1, round(pw * PRINT_TAM[1] / PRINT_TAM[0]))
    cw = pw + 2 * CARTAO_BORDA
    ch = ph + 2 * CARTAO_BORDA
    y_base = CARTAO_POS[1] + PRINT_TAM[1] + 2 * CARTAO_BORDA
    x0 = CARTAO_POS[0]
    y0 = y_base - ch
    return (x0, y0, x0 + cw, y0 + ch)


def pos_etiqueta_no_cartao(
    caixa: tuple[int, int, int, int],
    tam_fonte: int = ETIQ_TAM,
) -> tuple[int, int]:
    """Calcula a posição (x, y) da etiqueta centrada sobre a borda superior do cartão."""
    alt = max(16, round(ETIQ_ALT * tam_fonte / ETIQ_TAM))
    dx = ETIQ_POS[0] - CARTAO_POS[0]
    return (caixa[0] + dx, caixa[1] - alt // 2)


def caixa_etiqueta(
    texto: str,
    tam_fonte: int = ETIQ_TAM,
    pos: tuple[int, int] | None = None,
) -> tuple[int, int, int, int]:
    """Calcula a caixa (x0, y0, x1, y1) da etiqueta em pílula sem desenhar."""
    alt = max(16, round(ETIQ_ALT * tam_fonte / ETIQ_TAM))
    pad = round(ETIQ_PAD * tam_fonte / ETIQ_TAM)
    fonte = ImageFont.truetype(str(FONTE_EXTRABOLD), tam_fonte)
    larg = max(alt, round(fonte.getlength(texto.upper()) + pad))
    x0, y0 = ETIQ_POS if pos is None else pos
    return (x0, y0, x0 + larg, y0 + alt)


def desenhar_cartao(
    canvas: Image.Image,
    img_print: Image.Image,
    recorte: tuple[int, int, int, int],
    largura: int = PRINT_TAM[0],
) -> tuple[int, int, int, int]:
    """Desenha sombra, cartão branco e foto recortada do print no canvas; devolve caixa."""
    x0, y0, x1, y1 = caixa_cartao(largura)
    cw = x1 - x0
    ch = y1 - y0
    pw = cw - 2 * CARTAO_BORDA
    ph = ch - 2 * CARTAO_BORDA
    print_tam = (pw, ph)
    raio_cartao = min(CARTAO_RAIO, cw // 2, ch // 2)
    raio_print = min(PRINT_RAIO, pw // 2, ph // 2)

    pad = SOMBRA_BLUR * 4
    sombra = Image.new("RGBA", (cw + 2 * pad, ch + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle(
        [pad, pad, pad + cw - 1, pad + ch - 1],
        radius=raio_cartao,
        fill=(0, 0, 0, round(SOMBRA_OPAC * 255)),
    )
    if SOMBRA_BLUR > 0:
        sombra = sombra.filter(ImageFilter.GaussianBlur(SOMBRA_BLUR))
    _compor_camada(canvas, sombra, (x0 - pad, y0 + SOMBRA_DY - pad))

    cartao = Image.new("RGBA", (cw, ch), (255, 255, 255, 255))
    cartao.putalpha(_mascara_arredondada((cw, ch), raio_cartao))

    recortada = img_print.crop(recorte)
    tem_transp = img_print.has_transparency_data
    foto = (
        recortada.convert("RGBA" if tem_transp else "RGB")
        .resize(print_tam, Image.Resampling.LANCZOS)
        .convert("RGBA")
    )
    mascara_foto = _mascara_arredondada(print_tam, raio_print)
    if tem_transp:
        foto.putalpha(ImageChops.multiply(foto.getchannel("A"), mascara_foto))
    else:
        foto.putalpha(mascara_foto)

    cartao.alpha_composite(foto, dest=(CARTAO_BORDA, CARTAO_BORDA))
    _compor_camada(canvas, cartao, (x0, y0))
    return (x0, y0, x1, y1)


def desenhar_etiqueta(
    canvas: Image.Image,
    texto: str,
    tam_fonte: int = ETIQ_TAM,
    pos: tuple[int, int] | None = None,
) -> tuple[int, int, int, int]:
    """Desenha a etiqueta em pílula com contorno branco e texto branco centrado; devolve caixa."""
    texto_upper = texto.upper()
    fonte = ImageFont.truetype(str(FONTE_EXTRABOLD), tam_fonte)
    x0, y0, x1, y1 = caixa_etiqueta(texto, tam_fonte=tam_fonte, pos=pos)
    larg = x1 - x0
    alt = y1 - y0
    raio = alt // 2
    contorno = max(2, round(ETIQ_CONTORNO * tam_fonte / ETIQ_TAM))

    etiqueta = Image.new("RGBA", (larg, alt), (255, 255, 255, 255))
    etiqueta.putalpha(_mascara_arredondada((larg, alt), raio))

    larg_int = max(1, larg - 2 * contorno)
    alt_int = max(1, alt - 2 * contorno)
    miolo = Image.new("RGBA", (larg_int, alt_int), (*ETIQ_COR, 255))
    miolo.putalpha(_mascara_arredondada((larg_int, alt_int), max(0, raio - contorno)))
    etiqueta.alpha_composite(miolo, dest=(contorno, contorno))

    ImageDraw.Draw(etiqueta).text(
        (larg / 2, alt / 2),
        texto_upper,
        font=fonte,
        fill=(255, 255, 255, 255),
        anchor="mm",
    )

    _compor_camada(canvas, etiqueta, (x0, y0))
    return (x0, y0, x1, y1)

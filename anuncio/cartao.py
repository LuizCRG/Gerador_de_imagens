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


def desenhar_cartao(
    canvas: Image.Image,
    img_print: Image.Image,
    recorte: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    """Desenha sombra, cartão branco e foto recortada do print no canvas; devolve caixa."""
    pw, ph = PRINT_TAM
    cw = pw + 2 * CARTAO_BORDA
    ch = ph + 2 * CARTAO_BORDA
    x0, y0 = CARTAO_POS

    pad = SOMBRA_BLUR * 4
    sombra = Image.new("RGBA", (cw + 2 * pad, ch + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle(
        [pad, pad, pad + cw - 1, pad + ch - 1],
        radius=CARTAO_RAIO,
        fill=(0, 0, 0, round(SOMBRA_OPAC * 255)),
    )
    if SOMBRA_BLUR > 0:
        sombra = sombra.filter(ImageFilter.GaussianBlur(SOMBRA_BLUR))
    _compor_camada(canvas, sombra, (x0 - pad, y0 + SOMBRA_DY - pad))

    cartao = Image.new("RGBA", (cw, ch), (255, 255, 255, 255))
    cartao.putalpha(_mascara_arredondada((cw, ch), CARTAO_RAIO))

    recortada = img_print.crop(recorte)
    tem_transp = img_print.has_transparency_data
    foto = (
        recortada.convert("RGBA" if tem_transp else "RGB")
        .resize(PRINT_TAM, Image.Resampling.LANCZOS)
        .convert("RGBA")
    )
    mascara_foto = _mascara_arredondada(PRINT_TAM, PRINT_RAIO)
    if tem_transp:
        foto.putalpha(ImageChops.multiply(foto.getchannel("A"), mascara_foto))
    else:
        foto.putalpha(mascara_foto)

    cartao.alpha_composite(foto, dest=(CARTAO_BORDA, CARTAO_BORDA))
    _compor_camada(canvas, cartao, (x0, y0))
    return (x0, y0, x0 + cw, y0 + ch)


def desenhar_etiqueta(canvas: Image.Image, texto: str) -> tuple[int, int, int, int]:
    """Desenha a etiqueta em pílula com contorno branco e texto branco centrado; devolve caixa."""
    texto_upper = texto.upper()
    fonte = ImageFont.truetype(str(FONTE_EXTRABOLD), ETIQ_TAM)
    larg = max(ETIQ_ALT, round(fonte.getlength(texto_upper) + ETIQ_PAD))
    alt = ETIQ_ALT
    raio = alt // 2

    etiqueta = Image.new("RGBA", (larg, alt), (255, 255, 255, 255))
    etiqueta.putalpha(_mascara_arredondada((larg, alt), raio))

    larg_int = larg - 2 * ETIQ_CONTORNO
    alt_int = alt - 2 * ETIQ_CONTORNO
    miolo = Image.new("RGBA", (larg_int, alt_int), (*ETIQ_COR, 255))
    miolo.putalpha(_mascara_arredondada((larg_int, alt_int), max(0, raio - ETIQ_CONTORNO)))
    etiqueta.alpha_composite(miolo, dest=(ETIQ_CONTORNO, ETIQ_CONTORNO))

    ImageDraw.Draw(etiqueta).text(
        (larg / 2, alt / 2),
        texto_upper,
        font=fonte,
        fill=(255, 255, 255, 255),
        anchor="mm",
    )

    x0, y0 = ETIQ_POS
    _compor_camada(canvas, etiqueta, (x0, y0))
    return (x0, y0, x0 + larg, y0 + alt)

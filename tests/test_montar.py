"""Testes para verificação de layout, autocorreção e montagem final do anúncio."""

import numpy as np
from PIL import Image, ImageFont
from scipy.ndimage import maximum_filter

from anuncio.cartao import desenhar_etiqueta
from anuncio.imagens import encaixar_peca, recortar_carro, remover_fundo_branco
from anuncio.layout import (
    CANVAS,
    CARRO_POS,
    CARTAO_BORDA,
    CARTAO_POS,
    ETIQ_ALT,
    ETIQ_COR,
    ETIQ_PAD,
    ETIQ_POS,
    ETIQ_TAM,
    FONTE_EXTRABOLD,
    PRINT_TAM,
    SUB_TAM,
    TITULO_TAM,
)
from anuncio.montar import Entrada, Resultado, montar, verificar
from anuncio.textos import mascara_textos, posicionar_textos


def _entradas_padrao(img_carro, img_peca, img_print, **overrides) -> Entrada:
    dados = {
        "carro": img_carro,
        "peca": img_peca,
        "print_img": img_print,
        "titulo": "Puxador de Porta",
        "subtitulo": ["compatível com", "new fiesta sedan", "2011 a 2017"],
        "etiqueta": "aplicação na porta",
    }
    dados.update(overrides)
    return Entrada(**dados)


def _problemas_finais(entrada: Entrada, resultado: Resultado) -> list[str]:
    carro_rec = recortar_carro(entrada.carro)
    arr = np.asarray(carro_rec)
    ys, xs = np.where(arr.min(axis=2) < 245)
    caixa_carro = (
        CARRO_POS[0] + int(xs.min()),
        CARRO_POS[1] + int(ys.min()),
        CARRO_POS[0] + int(xs.max()) + 1,
        CARRO_POS[1] + int(ys.max()) + 1,
    )
    peca_enc, pos_peca = encaixar_peca(
        remover_fundo_branco(entrada.peca),
        escala=resultado.escala_peca,
    )
    mb = np.zeros((CANVAS, CANVAS), dtype=bool)
    mb[
        pos_peca[1] : pos_peca[1] + peca_enc.height,
        pos_peca[0] : pos_peca[0] + peca_enc.width,
    ] = np.asarray(peca_enc.getchannel("A")) > 32
    mascara_peca = maximum_filter(mb, size=13, mode="constant", cval=0)

    textos = posicionar_textos(
        CARRO_POS[1] + carro_rec.height,
        entrada.titulo,
        entrada.subtitulo,
        tam_titulo=resultado.tam_titulo,
        tam_sub=resultado.tam_sub,
    )
    m_titulo, m_sub = mascara_textos(textos)
    caixa_cartao = (
        CARTAO_POS[0],
        CARTAO_POS[1],
        CARTAO_POS[0] + PRINT_TAM[0] + 2 * CARTAO_BORDA,
        CARTAO_POS[1] + PRINT_TAM[1] + 2 * CARTAO_BORDA,
    )
    fonte_etiq = ImageFont.truetype(str(FONTE_EXTRABOLD), ETIQ_TAM)
    larg_etiq = max(ETIQ_ALT, round(fonte_etiq.getlength(entrada.etiqueta.upper()) + ETIQ_PAD))
    caixa_etiqueta = (ETIQ_POS[0], ETIQ_POS[1], ETIQ_POS[0] + larg_etiq, ETIQ_POS[1] + ETIQ_ALT)
    return verificar(mascara_peca, m_titulo, m_sub, caixa_carro, caixa_cartao, caixa_etiqueta)


def test_montar_padrao(img_carro, img_peca, img_print):
    r = montar(_entradas_padrao(img_carro, img_peca, img_print))
    assert isinstance(r, Resultado)
    assert r.imagem.size == (CANVAS, CANVAS)
    assert r.imagem.mode == "RGB"
    assert r.avisos == []
    assert r.tam_titulo == TITULO_TAM
    assert r.tam_sub == SUB_TAM
    assert r.escala_peca == 1.0


def test_peca_larga_corrigida(img_carro, img_print):
    peca_larga = Image.new("RGB", (1200, 700), (0, 0, 0))
    entrada = _entradas_padrao(img_carro, peca_larga, img_print)
    r = montar(entrada)

    assert any("reduzid" in a for a in r.avisos)
    assert not any("Não foi possível" in a for a in r.avisos)
    assert r.tam_titulo < TITULO_TAM or r.tam_sub < SUB_TAM or r.escala_peca < 1.0
    assert _problemas_finais(entrada, r) == []


def test_subtitulo_longo_corrigido(img_carro, img_peca, img_print):
    entrada = _entradas_padrao(
        img_carro,
        img_peca,
        img_print,
        subtitulo=["COMPATÍVEL COM TODAS AS VERSÕES", "new fiesta sedan", "2011 a 2017"],
    )
    r = montar(entrada)

    assert any("reduzid" in a for a in r.avisos)
    assert not any("Não foi possível" in a for a in r.avisos)
    assert r.tam_sub < SUB_TAM or r.escala_peca < 1.0
    assert _problemas_finais(entrada, r) == []


def test_carro_x_peca_reduz_peca(img_carro, img_print):
    peca_cheia = Image.new("RGB", (580, 1000), (0, 0, 0))
    entrada = _entradas_padrao(img_carro, peca_cheia, img_print)
    r = montar(entrada)

    assert r.escala_peca < 1.0
    assert any(a.startswith("Peça reduzida para ") and a.endswith("%") for a in r.avisos)
    assert not any("Não foi possível" in a for a in r.avisos)
    assert _problemas_finais(entrada, r) == []


def test_verificar_detecta():
    vazia = np.zeros((CANVAS, CANVAS), dtype=bool)
    caixa_carro_ok = (36, 20, 487, 271)
    caixa_cartao_ok = (
        CARTAO_POS[0],
        CARTAO_POS[1],
        CARTAO_POS[0] + PRINT_TAM[0] + 2 * CARTAO_BORDA,
        CARTAO_POS[1] + PRINT_TAM[1] + 2 * CARTAO_BORDA,
    )
    caixa_etiq_ok = (ETIQ_POS[0], ETIQ_POS[1], ETIQ_POS[0] + 280, ETIQ_POS[1] + 46)

    assert verificar(vazia, vazia, vazia, caixa_carro_ok, caixa_cartao_ok, caixa_etiq_ok) == []

    m_peca = vazia.copy()
    m_peca[100:150, 500:550] = True
    m_titulo = vazia.copy()
    m_titulo[120:140, 520:540] = True
    assert "titulo_x_peca" in verificar(
        m_peca, m_titulo, vazia, caixa_carro_ok, caixa_cartao_ok, caixa_etiq_ok
    )

    m_sub = vazia.copy()
    m_sub[110:130, 510:530] = True
    assert "sub_x_peca" in verificar(
        m_peca, vazia, m_sub, caixa_carro_ok, caixa_cartao_ok, caixa_etiq_ok
    )

    m_sub_baixa = vazia.copy()
    m_sub_baixa[ETIQ_POS[1] - 4, 50] = True
    assert "sub_x_etiqueta" in verificar(
        vazia, vazia, m_sub_baixa, caixa_carro_ok, caixa_cartao_ok, caixa_etiq_ok
    )

    m_peca_carro = vazia.copy()
    m_peca_carro[100, 450] = True
    assert "carro_x_peca" in verificar(
        m_peca_carro, vazia, vazia, caixa_carro_ok, caixa_cartao_ok, caixa_etiq_ok
    )

    m_peca_cartao = vazia.copy()
    m_peca_cartao[800, 390] = True
    assert "cartao_x_peca" in verificar(
        m_peca_cartao, vazia, vazia, caixa_carro_ok, caixa_cartao_ok, caixa_etiq_ok
    )

    assert "fora_do_canvas" in verificar(
        vazia, vazia, vazia, caixa_carro_ok, caixa_cartao_ok, (62, 689, 1050, 735)
    )

    m_borda = vazia.copy()
    m_borda[500, CANVAS - 1] = True
    assert "fora_do_canvas" in verificar(
        vazia, vazia, m_borda, caixa_carro_ok, caixa_cartao_ok, caixa_etiq_ok
    )


def test_recorte_devolvido(img_carro, img_peca, img_print):
    r = montar(_entradas_padrao(img_carro, img_peca, img_print))
    l, t, r_x, b = r.recorte_print
    assert abs((r_x - l) / (b - t) - PRINT_TAM[0] / PRINT_TAM[1]) < 0.01

    r2 = montar(
        _entradas_padrao(
            img_carro,
            img_peca,
            img_print,
            recorte_print=(-20, 150, 380, 700),
        )
    )
    l2, t2, r2_x, b2 = r2.recorte_print
    assert 0 <= l2 < r2_x <= img_print.width
    assert 0 <= t2 < b2 <= img_print.height
    assert abs((r2_x - l2) / (b2 - t2) - PRINT_TAM[0] / PRINT_TAM[1]) < 0.01


def test_aviso_nao_foi_possivel_eliminar(img_carro, img_peca, img_print):
    r = montar(
        _entradas_padrao(
            img_carro,
            img_peca,
            img_print,
            etiqueta="ETIQUETA EXTREMAMENTE LONGA QUE ULTRAPASSA O LIMITE DO CANVAS INTEIRO",
        )
    )

    assert "Não foi possível eliminar: fora_do_canvas" in r.avisos


def test_titulo_longo_emite_aviso(img_carro, img_peca, img_print):
    r = montar(
        _entradas_padrao(
            img_carro,
            img_peca,
            img_print,
            titulo="Maçaneta Interna Dianteira Esquerda",
            subtitulo=[],
        )
    )

    assert r.tam_titulo < TITULO_TAM
    assert f"Título reduzido de {TITULO_TAM} para {r.tam_titulo} px" in r.avisos


def test_composicao_ordem_etiqueta_sobre_cartao(img_carro, img_peca, img_print):
    r = montar(_entradas_padrao(img_carro, img_peca, img_print))
    assert r.imagem.getpixel((74, 712)) == ETIQ_COR
    # Verifica que o cartão foi desenhado e a etiqueta ficou na camada superior
    temp = Image.new("RGB", (CANVAS, CANVAS), (255, 255, 255))
    box = desenhar_etiqueta(temp, "aplicação na porta")
    assert r.imagem.getpixel((box[0] + 10, box[1] + 23)) == ETIQ_COR

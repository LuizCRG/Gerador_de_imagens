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
from anuncio.montar import Entrada, Resultado, _proximo_ajuste, montar, verificar
from anuncio.textos import mascara_textos, posicionar_textos, textos_fora_canvas


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
    titulo_fora, sub_fora = textos_fora_canvas(textos)
    caixa_cartao = (
        CARTAO_POS[0],
        CARTAO_POS[1],
        CARTAO_POS[0] + PRINT_TAM[0] + 2 * CARTAO_BORDA,
        CARTAO_POS[1] + PRINT_TAM[1] + 2 * CARTAO_BORDA,
    )
    fonte_etiq = ImageFont.truetype(str(FONTE_EXTRABOLD), ETIQ_TAM)
    larg_etiq = max(ETIQ_ALT, round(fonte_etiq.getlength(entrada.etiqueta.upper()) + ETIQ_PAD))
    caixa_etiqueta = (ETIQ_POS[0], ETIQ_POS[1], ETIQ_POS[0] + larg_etiq, ETIQ_POS[1] + ETIQ_ALT)
    return verificar(
        mascara_peca,
        m_titulo,
        m_sub,
        caixa_carro,
        caixa_cartao,
        caixa_etiqueta,
        titulo_fora=titulo_fora,
        sub_fora=sub_fora,
    )


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

    assert r.escala_peca == 1.0
    assert r.tam_titulo == TITULO_TAM
    assert r.tam_sub == SUB_TAM
    assert r.avisos == ["Não foi possível eliminar: fora_do_canvas"]
    assert not any("Peça reduzida" in a for a in r.avisos)


def _peca_sem_tinta_no_meio() -> Image.Image:
    im = Image.new("RGBA", (100, 1000), (0, 0, 0, 0))
    im.paste((0, 0, 0, 255), (0, 0, 100, 150))
    im.paste((0, 0, 0, 255), (0, 850, 100, 1000))
    return im


def test_fora_do_canvas_subtitulo_corrige_sem_reduzir_peca(img_carro, img_print):
    r = montar(
        _entradas_padrao(
            img_carro,
            _peca_sem_tinta_no_meio(),
            img_print,
            subtitulo=["COMPATÍVEL COM TODAS AS VERSÕES DO MODELO NOVO"],
        )
    )

    assert r.escala_peca == 1.0
    assert r.tam_titulo == TITULO_TAM
    assert r.tam_sub < SUB_TAM
    assert not any("Peça reduzida" in a for a in r.avisos)
    assert not any("Não foi possível" in a for a in r.avisos)


def test_fora_do_canvas_subtitulo_extremo_nao_reduz_peca(img_carro, img_print):
    r = montar(
        _entradas_padrao(
            img_carro,
            _peca_sem_tinta_no_meio(),
            img_print,
            subtitulo=["W" * 50],
        )
    )

    assert r.escala_peca == 1.0
    assert r.tam_sub == 26
    assert not any("Peça reduzida" in a for a in r.avisos)
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


def test_proximo_ajuste_guarda_escala_peca():
    vazia = np.zeros((CANVAS, CANVAS), dtype=bool)
    assert _proximo_ajuste(["sub_x_etiqueta"], 72, 26, 1.0, vazia, vazia, vazia) == (
        72,
        26,
        1.0,
        False,
    )

    m_peca_borda = vazia.copy()
    m_peca_borda[500, CANVAS - 1] = True
    assert _proximo_ajuste(["fora_do_canvas"], 132, 40, 1.0, m_peca_borda, vazia, vazia) == (
        132,
        40,
        0.97,
        True,
    )


def test_montar_recorte_explicito_nao_chama_detectar_area_foto(
    monkeypatch, img_carro, img_peca, img_print
):
    def _falhar(_img):
        raise AssertionError("detectar_area_foto não deveria rodar quando recorte_print existe")

    monkeypatch.setattr("anuncio.montar.detectar_area_foto", _falhar)
    r = montar(
        _entradas_padrao(
            img_carro,
            img_peca,
            img_print,
            recorte_print=(100, 300, 450, 555),
        )
    )
    assert r.recorte_print == (100, 300, 450, 555)


def test_subtitulo_gap_na_borda_reduz_sem_truncar(img_carro, img_print):
    entrada = _entradas_padrao(
        img_carro,
        _peca_sem_tinta_no_meio(),
        img_print,
        subtitulo=["COMPATÍVEL COM NEW FIESTA SEDAN TITANIUM PLUS 2015 A 2020"],
    )
    r = montar(entrada)

    assert r.tam_sub < SUB_TAM
    assert r.escala_peca == 1.0
    assert any("Subtítulo reduzido" in a for a in r.avisos)
    assert not any("Não foi possível" in a for a in r.avisos)
    assert _problemas_finais(entrada, r) == []


def test_subtitulo_extremo_com_gap_na_borda_emite_aviso(img_carro, img_print):
    entrada = _entradas_padrao(
        img_carro,
        _peca_sem_tinta_no_meio(),
        img_print,
        subtitulo=["COMPATÍVEL COM NEW FIESTA SEDAN TITANIUM PLUS COMPLETO AUTOMÁTICO 2015 A 2020"],
    )
    r = montar(entrada)

    assert r.tam_sub == 26
    assert r.escala_peca == 1.0
    assert "Não foi possível eliminar: fora_do_canvas" in r.avisos


def test_montar_sem_print_libera_espaco_inferior(img_carro, img_peca):
    r = montar(
        Entrada(
            carro=img_carro,
            peca=img_peca,
            print_img=None,
            titulo="Puxador de Porta",
            subtitulo=["linha 1", "linha 2", "linha 3"],
            etiqueta="",
            usar_print=False,
            tam_sub=64,
        )
    )
    assert r.avisos == []
    assert r.recorte_print is None
    assert r.tam_sub == 64


def test_montar_sem_print_peca_larga_usa_espaco_inferior(img_carro):
    peca_larga = Image.new("RGB", (1200, 400), (0, 0, 0))
    r = montar(
        Entrada(
            carro=img_carro,
            peca=peca_larga,
            print_img=None,
            titulo="Puxador de Porta",
            subtitulo=["compatível com", "new fiesta sedan", "2011 a 2017"],
            etiqueta="",
            usar_print=False,
        )
    )
    assert r.avisos == []
    assert r.escala_peca == 1.0
    # A peça larga deve aparecer na faixa inferior (x < 200, y > 750)
    assert r.imagem.getpixel((120, 850)) == (0, 0, 0)


def test_montar_sem_carro_sobe_titulo(img_peca, img_print):
    r = montar(
        Entrada(
            carro=None,
            peca=img_peca,
            print_img=img_print,
            titulo="Puxador de Porta",
            subtitulo=["compatível com", "new fiesta"],
            etiqueta="aplicação",
            usar_carro=False,
        )
    )
    assert r.avisos == []
    # Sem carro, o título deve aparecer no terço superior (y < 150)
    arr = np.asarray(r.imagem)
    regiao_topo = arr[20:150, 36:400]
    assert np.any(regiao_topo.max(axis=2) < 30)


def test_montar_sem_peca_titulo_usa_largura_total(img_carro, img_print):
    r = montar(
        Entrada(
            carro=img_carro,
            peca=None,
            print_img=img_print,
            titulo="Retrovisor Externo",
            subtitulo=[],
            etiqueta="aplicação",
            usar_peca=False,
        )
    )
    assert r.avisos == []
    assert r.tam_titulo == TITULO_TAM


def test_montar_sem_etiqueta_permite_subtitulo_ate_cartao(img_carro, img_peca, img_print):
    r = montar(
        Entrada(
            carro=img_carro,
            peca=img_peca,
            print_img=img_print,
            titulo="Puxador de Porta",
            subtitulo=["linha 1", "linha 2", "linha 3"],
            etiqueta="aplicação",
            usar_etiqueta=False,
        )
    )
    assert r.avisos == []
    # Topo da pílula original em (74, 700) permanece como fundo/cartão (sem azul ETIQ_COR)
    assert r.imagem.getpixel((74, 700)) != ETIQ_COR


def test_montar_sem_titulo_sobe_subtitulo(img_carro, img_peca, img_print):
    r = montar(
        Entrada(
            carro=img_carro,
            peca=img_peca,
            print_img=img_print,
            titulo="",
            subtitulo=["COMPATÍVEL COM NEW FIESTA"],
            etiqueta="aplicação",
            usar_titulo=False,
        )
    )
    assert r.avisos == []
    arr = np.asarray(r.imagem)
    assert np.any(arr[290:360, 40:400].max(axis=2) < 80)


def test_montar_tamanhos_personalizados_sem_falso_aviso(img_carro, img_peca, img_print):
    r = montar(
        Entrada(
            carro=img_carro,
            peca=img_peca,
            print_img=img_print,
            titulo="Puxador",
            subtitulo=["compatível com"],
            etiqueta="porta",
            largura_carro=380,
            escala_peca=0.8,
            largura_print=280,
            tam_titulo=96,
            tam_sub=32,
            tam_etiqueta=20,
        )
    )
    assert r.avisos == []
    assert r.tam_titulo == 96
    assert r.tam_sub == 32
    assert r.escala_peca == 0.8


def test_montar_tudo_desativado_erro():
    import pytest

    with pytest.raises(ValueError, match="Ative pelo menos um elemento"):
        montar(
            Entrada(
                carro=None,
                peca=None,
                print_img=None,
                usar_carro=False,
                usar_peca=False,
                usar_print=False,
                usar_titulo=False,
                usar_subtitulo=False,
            )
        )


def test_montar_respeita_recorte_carro_e_peca():
    from PIL import ImageDraw

    carro = Image.new("RGB", (400, 200), (255, 255, 255))
    dc = ImageDraw.Draw(carro)
    dc.rectangle([20, 40, 150, 160], fill=(0, 140, 0))
    dc.rectangle([250, 40, 380, 160], fill=(220, 20, 20))

    peca = Image.new("RGB", (400, 200), (255, 255, 255))
    dp = ImageDraw.Draw(peca)
    dp.rectangle([20, 40, 140, 160], fill=(20, 40, 210))
    dp.rectangle([260, 40, 380, 160], fill=(240, 180, 10))

    r = montar(
        Entrada(
            carro=carro,
            peca=peca,
            print_img=None,
            titulo="Teste",
            subtitulo=[],
            etiqueta="",
            usar_print=False,
            recorte_carro=(0, 0, 200, 200),
            recorte_peca=(220, 0, 400, 200),
        )
    )
    assert r.recorte_carro == (0, 0, 200, 200)
    assert r.recorte_peca == (220, 0, 400, 200)

    arr = np.asarray(r.imagem)
    topo_carro = arr[:450, :600]
    assert np.any((topo_carro[..., 1] > topo_carro[..., 0] + 60))
    assert not np.any((topo_carro[..., 0] > 180) & (topo_carro[..., 1] < 60))

    lado_peca = arr[:, 560:]
    assert np.any((lado_peca[..., 0] > 190) & (lado_peca[..., 2] < 60))
    assert not np.any((lado_peca[..., 2] > 160) & (lado_peca[..., 0] < 60))


def test_montar_recorte_carro_peca_limites_e_vazio():
    branco_c = Image.new("RGB", (300, 180), (255, 255, 255))
    branco_p = Image.new("RGBA", (300, 180), (255, 255, 255, 0))

    r = montar(
        Entrada(
            carro=branco_c,
            peca=branco_p,
            print_img=None,
            titulo="Teste",
            usar_print=False,
            recorte_carro=(-10, -20, 9999, 9999),
            recorte_peca=(280, 170, 20, 30),
        )
    )
    assert r.recorte_carro == (0, 0, 300, 180)
    assert r.recorte_peca == (20, 30, 280, 170)
    assert r.imagem.size == (1024, 1024)

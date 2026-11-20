"""Testes do servidor Flask (app.py)."""

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image
import pytest

from app import criar_app


def _para_upload(img: Image.Image, nome: str = "imagem.png") -> tuple[BytesIO, str]:
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return (buf, nome)


def _subir_tres_imagens(client, img_carro, img_peca, img_print) -> None:
    for tipo, img in (("carro", img_carro), ("peca", img_peca), ("print", img_print)):
        resp = client.post(
            f"/api/imagem/{tipo}",
            data={"arquivo": _para_upload(img, f"{tipo}.png")},
        )
        assert resp.status_code == 200


@pytest.fixture
def app_e_client(tmp_path: Path):
    app = criar_app(pasta_saida=tmp_path)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield app, client


@pytest.fixture
def client(app_e_client):
    return app_e_client[1]


def test_upload_print_devolve_recorte(client, img_print):
    r = client.post(
        "/api/imagem/print",
        data={"arquivo": _para_upload(img_print, "print.png")},
    )
    assert r.status_code == 200
    assert set(r.json) >= {"largura", "altura", "area", "recorte"}
    assert r.json["largura"] == img_print.width
    assert r.json["altura"] == img_print.height
    assert len(r.json["area"]) == 4
    assert len(r.json["recorte"]) == 4


def test_tipo_invalido(client, img_carro):
    r = client.post(
        "/api/imagem/xyz",
        data={"arquivo": _para_upload(img_carro, "carro.png")},
    )
    assert r.status_code == 404


def test_arquivo_invalido(client):
    r = client.post(
        "/api/imagem/carro",
        data={"arquivo": (BytesIO(b"lixo"), "a.png")},
    )
    assert r.status_code == 400
    assert "erro" in r.json


def test_upload_sem_arquivo(client):
    r = client.post("/api/imagem/carro", data={})
    assert r.status_code == 400
    assert "erro" in r.json


def test_upload_decompression_bomb_retorna_400(client, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    img_pequena = Image.new("RGB", (10, 10), (100, 120, 140))
    r = client.post(
        "/api/imagem/carro",
        data={"arquivo": _para_upload(img_pequena, "gigante.png")},
    )
    assert r.status_code == 400
    assert "erro" in r.json
    assert "grande demais" in r.json["erro"].lower()


def test_previa_sem_imagens(client, img_carro, img_peca):
    payload = {
        "titulo": "Puxador de Porta",
        "subtitulo": ["Dianteiro"],
        "etiqueta": "ORIGINAL",
        "recorte_print": None,
    }
    r = client.post("/api/previa", json=payload)
    assert r.status_code == 400
    assert "carro" in r.json["erro"].lower()

    client.post("/api/imagem/carro", data={"arquivo": _para_upload(img_carro)})
    r2 = client.post("/api/previa", json=payload)
    assert r2.status_code == 400
    assert "peça" in r2.json["erro"].lower()

    client.post("/api/imagem/peca", data={"arquivo": _para_upload(img_peca)})
    r3 = client.post("/api/previa", json=payload)
    assert r3.status_code == 400
    assert "print" in r3.json["erro"].lower()


def test_previa_erros_validacao_titulo_subtitulo_recorte(client, img_carro, img_peca, img_print):
    _subir_tres_imagens(client, img_carro, img_peca, img_print)

    r_titulo = client.post(
        "/api/previa",
        json={"titulo": "   ", "subtitulo": ["Linha 1"], "etiqueta": "NOVO", "recorte_print": None},
    )
    assert r_titulo.status_code == 400
    assert "erro" in r_titulo.json

    r_sub = client.post(
        "/api/previa",
        json={
            "titulo": "Puxador de Porta",
            "subtitulo": ["L1", "L2", "L3", "L4"],
            "etiqueta": "NOVO",
            "recorte_print": None,
        },
    )
    assert r_sub.status_code == 400
    assert "erro" in r_sub.json

    r_rec = client.post(
        "/api/previa",
        json={
            "titulo": "Puxador de Porta",
            "subtitulo": ["L1"],
            "etiqueta": "NOVO",
            "recorte_print": [10, 20],
        },
    )
    assert r_rec.status_code == 400
    assert "erro" in r_rec.json


def test_previa_ok(client, img_carro, img_peca, img_print):
    _subir_tres_imagens(client, img_carro, img_peca, img_print)

    r = client.post(
        "/api/previa",
        json={
            "titulo": "Puxador de Porta",
            "subtitulo": ["Dianteiro Esquerdo", "2015 a 2020"],
            "etiqueta": "ORIGINAL",
            "recorte_print": None,
        },
    )
    assert r.status_code == 200
    assert set(r.json) >= {"png", "avisos", "recorte_print"}
    png = base64.b64decode(r.json["png"])
    with Image.open(BytesIO(png)) as im:
        assert im.size == (1024, 1024)
        assert im.mode == "RGB"
    assert len(r.json["recorte_print"]) == 4


def test_previa_respeita_recorte_print_explicito(client, img_carro, img_peca, img_print):
    _subir_tres_imagens(client, img_carro, img_peca, img_print)

    base_payload = {
        "titulo": "Puxador de Porta",
        "subtitulo": ["Dianteiro Esquerdo"],
        "etiqueta": "ORIGINAL",
    }
    r_auto = client.post("/api/previa", json={**base_payload, "recorte_print": None})
    assert r_auto.status_code == 200

    recorte_explicito = [100, 300, 450, 555]
    r = client.post("/api/previa", json={**base_payload, "recorte_print": recorte_explicito})
    assert r.status_code == 200
    assert r.json["recorte_print"] == recorte_explicito
    assert r.json["recorte_print"] != r_auto.json["recorte_print"]
    assert r.json["png"] != r_auto.json["png"]

    png = base64.b64decode(r.json["png"])
    with Image.open(BytesIO(png)) as im:
        cor_centro = im.getpixel((48 + 175, 720 + 127))[:3]
    esperada = (
        img_print.crop(tuple(recorte_explicito))
        .resize((350, 255), Image.Resampling.LANCZOS)
        .getpixel((175, 127))[:3]
    )
    assert cor_centro == esperada


def test_salvar_grava_arquivo(client, tmp_path, img_carro, img_peca, img_print):
    _subir_tres_imagens(client, img_carro, img_peca, img_print)

    r = client.post(
        "/api/salvar",
        json={
            "titulo": "Puxador de Porta",
            "subtitulo": ["Dianteiro"],
            "etiqueta": "ORIGINAL",
            "recorte_print": None,
        },
    )
    assert r.status_code == 200
    destino = tmp_path / "puxador-de-porta.png"
    assert destino.exists()
    assert r.mimetype == "image/png"
    assert "attachment" in r.headers.get("Content-Disposition", "")
    with Image.open(destino) as im:
        assert im.size == (1024, 1024)


def test_salvar_nao_sobrescreve(client, tmp_path, img_carro, img_peca, img_print):
    _subir_tres_imagens(client, img_carro, img_peca, img_print)
    payload = {
        "titulo": "Puxador de Porta",
        "subtitulo": ["Dianteiro"],
        "etiqueta": "ORIGINAL",
        "recorte_print": None,
    }

    r1 = client.post("/api/salvar", json=payload)
    r2 = client.post("/api/salvar", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert (tmp_path / "puxador-de-porta.png").exists()
    assert (tmp_path / "puxador-de-porta-2.png").exists()


def test_salvar_slug_acentos_e_fallback(client, tmp_path, img_carro, img_peca, img_print):
    _subir_tres_imagens(client, img_carro, img_peca, img_print)

    r1 = client.post(
        "/api/salvar",
        json={
            "titulo": "Maçaneta & Puxadôr de Pórta!",
            "subtitulo": [],
            "etiqueta": "NOVO",
            "recorte_print": None,
        },
    )
    assert r1.status_code == 200
    assert (tmp_path / "macaneta-puxador-de-porta.png").exists()

    r2 = client.post(
        "/api/salvar",
        json={
            "titulo": "!!!",
            "subtitulo": [],
            "etiqueta": "NOVO",
            "recorte_print": None,
        },
    )
    assert r2.status_code == 200
    assert (tmp_path / "anuncio.png").exists()


def test_pagina_inicial(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.content_type
    html = r.get_data(as_text=True)
    assert "Gerador de Anúncio" in html
    assert "/static/style.css" in html
    assert "/static/app.js" in html
    assert "Baixar PNG" in html
    for marcador in (
        'data-tipo="carro"',
        'data-tipo="peca"',
        'data-tipo="print"',
        'id="crop-canvas"',
        'id="usar-carro"',
        'id="usar-peca"',
        'id="usar-print"',
        'id="usar-etiqueta"',
        'id="usar-titulo"',
        'id="usar-subtitulo"',
        'id="largura-carro"',
        'id="escala-peca"',
        'id="largura-print"',
        'id="tam-titulo"',
        'id="tam-sub"',
        'id="tam-etiqueta"',
        'id="btn-restaurar-tamanhos"',
    ):
        assert marcador in html


def test_get_raiz_limpa_imagens(app_e_client, img_carro, img_peca, img_print):
    app, client = app_e_client
    _subir_tres_imagens(client, img_carro, img_peca, img_print)
    assert set(app.config["IMAGENS"]) == {"carro", "peca", "print"}

    r = client.get("/")
    assert r.status_code == 200
    assert app.config["IMAGENS"] == {}

    r_previa = client.post(
        "/api/previa",
        json={
            "titulo": "Puxador de Porta",
            "subtitulo": [],
            "etiqueta": "ORIGINAL",
            "recorte_print": None,
        },
    )
    assert r_previa.status_code == 400
    assert "carro" in r_previa.json["erro"].lower()


def test_ativos_estaticos_e_offline(client):
    for rota in ("/", "/static/style.css", "/static/app.js"):
        r = client.get(rota)
        assert r.status_code == 200
        conteudo = r.get_data(as_text=True).lower()
        assert "http://" not in conteudo
        assert "https://" not in conteudo


def test_previa_sem_print_e_sem_carro_nao_exige_fotos_desativadas(client, img_peca):
    client.post("/api/imagem/peca", data={"arquivo": _para_upload(img_peca)})
    r = client.post(
        "/api/previa",
        json={
            "titulo": "Puxador de Porta",
            "subtitulo": ["Linha 1"],
            "etiqueta": "",
            "recorte_print": None,
            "usar_carro": False,
            "usar_print": False,
            "usar_etiqueta": False,
            "escala_peca": 0.9,
            "tam_titulo": 110,
            "tam_sub": 36,
        },
    )
    assert r.status_code == 200
    assert r.json["recorte_print"] is None
    assert r.json["avisos"] == []


def test_previa_sem_titulo_permite_titulo_vazio_e_salvar_usa_anuncio(client, tmp_path, img_peca):
    client.post("/api/imagem/peca", data={"arquivo": _para_upload(img_peca)})
    r = client.post(
        "/api/salvar",
        json={
            "titulo": "",
            "subtitulo": [],
            "etiqueta": "",
            "recorte_print": None,
            "usar_carro": False,
            "usar_print": False,
            "usar_titulo": False,
            "usar_subtitulo": False,
        },
    )
    assert r.status_code == 200
    assert (tmp_path / "anuncio.png").exists()


def test_previa_dimensoes_invalidas_retorna_400(client, img_peca):
    client.post("/api/imagem/peca", data={"arquivo": _para_upload(img_peca)})
    r = client.post(
        "/api/previa",
        json={
            "titulo": "Teste",
            "subtitulo": [],
            "etiqueta": "",
            "recorte_print": None,
            "usar_carro": "sim",
            "usar_print": False,
        },
    )
    assert r.status_code == 400
    assert "usar_carro" in r.json["erro"].lower()

    r2 = client.post(
        "/api/previa",
        json={
            "titulo": "Teste",
            "subtitulo": [],
            "etiqueta": "",
            "recorte_print": None,
            "usar_carro": False,
            "usar_print": False,
            "tam_titulo": 9999,
        },
    )
    assert r2.status_code == 400
    assert "tam_titulo" in r2.json["erro"].lower()



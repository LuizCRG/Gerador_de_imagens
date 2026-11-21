"""Testes unitários para remoção de fundo via Poof API (anuncio.ia_fundo)."""

import io
from types import SimpleNamespace

from PIL import Image, ImageDraw
import pytest
import requests

from anuncio.ia_fundo import (
    ENDPOINT_POOF_API,
    obter_chave_api,
    remover_fundo_ia,
    salvar_chave_api,
)


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"", text: str = ""):
        self.status_code = status_code
        self.content = content
        self.text = text


def test_obter_e_salvar_chave_env(tmp_path, monkeypatch):
    monkeypatch.delenv("POOF_API_KEY", raising=False)
    env_file = tmp_path / ".env"

    assert obter_chave_api(env_path=env_file) == ""

    salvar_chave_api("  pk_teste123  ", env_path=env_file)
    assert "POOF_API_KEY=pk_teste123" in env_file.read_text(encoding="utf-8")
    assert obter_chave_api(env_path=env_file) == "pk_teste123"

    # Variável de ambiente tem prioridade sobre .env
    monkeypatch.setenv("POOF_API_KEY", "pk_override")
    assert obter_chave_api(env_path=env_file) == "pk_override"


def test_salvar_chave_preserva_outras_linhas_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OUTRA_VAR=abc\nPOOF_API_KEY=antiga\n", encoding="utf-8")

    salvar_chave_api("nova_chave", env_path=env_file)
    conteudo = env_file.read_text(encoding="utf-8")
    assert "OUTRA_VAR=abc" in conteudo
    assert "POOF_API_KEY=nova_chave" in conteudo
    assert "antiga" not in conteudo


def test_remover_fundo_sem_chave_erro(tmp_path, monkeypatch):
    monkeypatch.delenv("POOF_API_KEY", raising=False)
    im = Image.new("RGB", (64, 64), (100, 100, 100))
    with pytest.raises(ValueError, match="POOF_API_KEY"):
        remover_fundo_ia(im, env_path=tmp_path / ".env")


def test_remover_fundo_ia_envia_multipart_poof_e_normaliza_rgba_oculto():
    entrada = Image.new("RGB", (120, 80), (40, 120, 40))
    ImageDraw.Draw(entrada).rectangle([30, 20, 89, 59], fill=(30, 120, 200))

    # Saída RGBA simulada da Poof com RGB residual oculto sob alpha=0
    saida_poof = Image.new("RGBA", (120, 80), (20, 40, 60, 0))
    ImageDraw.Draw(saida_poof).rectangle([30, 20, 89, 59], fill=(30, 120, 200, 255))
    saida_poof.putpixel((29, 20), (30, 120, 200, 128))
    conteudo_png = _png_bytes(saida_poof)

    chamadas = []

    def fake_post(url, *, headers=None, files=None, timeout=None):
        chamadas.append(
            SimpleNamespace(url=url, headers=headers, files=files, timeout=timeout)
        )
        return _FakeResponse(status_code=200, content=conteudo_png)

    resultado = remover_fundo_ia(
        entrada,
        tipo="carro",
        api_key="pk_teste",
        http_post=fake_post,
    )

    assert len(chamadas) == 1
    req = chamadas[0]
    assert req.url == ENDPOINT_POOF_API == "https://api.poof.bg/v1/remove"
    assert req.headers == {"x-api-key": "pk_teste"}
    assert req.timeout == 60
    assert "file" in req.files

    assert resultado.mode == "RGBA"
    assert resultado.size == (120, 80)
    # Pixel 100% transparente tem RGB zerado para branco transparente
    assert resultado.getpixel((0, 0)) == (255, 255, 255, 0)
    # Sujeito opaco e borda semitransparente preservados
    assert resultado.getpixel((40, 30)) == (30, 120, 200, 255)
    assert resultado.getpixel((29, 20)) == (30, 120, 200, 128)


def test_remover_fundo_ia_redimensiona_imagem_gigante_e_limpa_fallback_rgb():
    gigante = Image.new("RGB", (3000, 1500), (180, 190, 200))

    saida_rgb = Image.new("RGB", (120, 80), (249, 249, 249))
    ImageDraw.Draw(saida_rgb).rectangle([25, 15, 94, 64], fill=(20, 20, 20))
    ImageDraw.Draw(saida_rgb).rectangle([50, 30, 69, 49], fill=(249, 249, 249))
    conteudo_png = _png_bytes(saida_rgb)

    tamanhos_enviados = []

    def fake_post(_url, *, headers=None, files=None, timeout=None):
        _nome, dados_bytes, _mime = files["file"]
        enviada = Image.open(io.BytesIO(dados_bytes))
        tamanhos_enviados.append(enviada.size)
        return _FakeResponse(status_code=200, content=conteudo_png)

    resultado = remover_fundo_ia(
        gigante,
        tipo="peca",
        api_key="pk_teste",
        http_post=fake_post,
    )

    assert len(tamanhos_enviados) == 1
    assert max(tamanhos_enviados[0]) <= 2048
    assert resultado.mode == "RGB"
    assert resultado.getpixel((0, 0)) == (255, 255, 255)
    assert resultado.getpixel((58, 38)) == (249, 249, 249)


def test_remover_fundo_ia_traduz_erros_http_poof():
    im = Image.new("RGB", (64, 64), (100, 100, 100))

    casos = [
        (401, '{"message":"Invalid API key"}', "inválida"),
        (403, '{"message":"Forbidden"}', "permissão"),
        (402, '{"message":"Insufficient credits"}', "Créditos"),
        (429, '{"message":"Too many requests"}', "Limite"),
        (400, '{"message":"Invalid image format"}', "Poof API"),
        (503, "Service Unavailable", "indisponível"),
    ]
    for status, corpo, esperado in casos:
        def fake_post(_url, **_kwargs):
            return _FakeResponse(status_code=status, text=corpo)

        with pytest.raises(RuntimeError, match=esperado):
            remover_fundo_ia(im, api_key="pk_teste", http_post=fake_post)


def test_remover_fundo_ia_erros_rede_timeout_e_bytes_invalidos():
    im = Image.new("RGB", (64, 64), (100, 100, 100))

    def levantar_timeout(_url, **_kwargs):
        raise requests.Timeout("timed out")

    with pytest.raises(RuntimeError, match="Tempo limite"):
        remover_fundo_ia(im, api_key="pk_teste", http_post=levantar_timeout)

    def levantar_conexao(_url, **_kwargs):
        raise requests.ConnectionError("dns fail")

    with pytest.raises(RuntimeError, match="conexão"):
        remover_fundo_ia(im, api_key="pk_teste", http_post=levantar_conexao)

    def retornar_lixo(_url, **_kwargs):
        return _FakeResponse(status_code=200, content=b'{"error": "not an image"}')

    with pytest.raises(RuntimeError, match="imagem válida"):
        remover_fundo_ia(im, api_key="pk_teste", http_post=retornar_lixo)

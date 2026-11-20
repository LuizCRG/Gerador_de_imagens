"""Testes unitários para remoção de fundo via Nano Banana (anuncio.ia_fundo)."""

import base64
import io
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw
import pytest

from anuncio.ia_fundo import (
    MODELO_NANO_BANANA,
    obter_chave_api,
    remover_fundo_ia,
    salvar_chave_api,
)


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakeInteractions:
    def __init__(self, resposta):
        self.chamadas = []
        self._resposta = resposta

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        if isinstance(self._resposta, Exception):
            raise self._resposta
        return self._resposta


class _FakeClient:
    def __init__(self, resposta):
        self.interactions = _FakeInteractions(resposta)


def test_obter_e_salvar_chave_env(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env_file = tmp_path / ".env"

    assert obter_chave_api(env_path=env_file) == ""

    salvar_chave_api("  AQ.teste123  ", env_path=env_file)
    assert "GEMINI_API_KEY=AQ.teste123" in env_file.read_text(encoding="utf-8")
    assert obter_chave_api(env_path=env_file) == "AQ.teste123"

    # Variável de ambiente tem prioridade sobre .env
    monkeypatch.setenv("GEMINI_API_KEY", "AQ.override")
    assert obter_chave_api(env_path=env_file) == "AQ.override"


def test_salvar_chave_preserva_outras_linhas_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OUTRA_VAR=abc\nGEMINI_API_KEY=antiga\n", encoding="utf-8")

    salvar_chave_api("nova_chave", env_path=env_file)
    conteudo = env_file.read_text(encoding="utf-8")
    assert "OUTRA_VAR=abc" in conteudo
    assert "GEMINI_API_KEY=nova_chave" in conteudo
    assert "antiga" not in conteudo


def test_remover_fundo_sem_chave_erro(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    im = Image.new("RGB", (64, 64), (100, 100, 100))
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        remover_fundo_ia(im, env_path=tmp_path / ".env")


def test_remover_fundo_ia_chama_modelo_e_limpa_borda_branca():
    entrada = Image.new("RGB", (120, 80), (40, 120, 40))
    ImageDraw.Draw(entrada).rectangle([30, 20, 89, 59], fill=(20, 20, 20))

    # Saída simulada da IA com fundo quase-branco (249) na borda e detalhe branco interno (249)
    saida_ia = Image.new("RGB", (120, 80), (249, 249, 249))
    ImageDraw.Draw(saida_ia).rectangle([25, 15, 94, 64], fill=(20, 20, 20))
    ImageDraw.Draw(saida_ia).rectangle([50, 30, 69, 49], fill=(249, 249, 249))

    b64 = base64.b64encode(_png_bytes(saida_ia)).decode("utf-8")
    fake_client = _FakeClient(
        SimpleNamespace(
            status="completed",
            output_image=SimpleNamespace(data=b64, mime_type="image/png"),
        )
    )

    resultado = remover_fundo_ia(entrada, tipo="carro", client=fake_client)

    assert len(fake_client.interactions.chamadas) == 1
    req = fake_client.interactions.chamadas[0]
    assert req["model"] == MODELO_NANO_BANANA == "gemini-nano-banana-2.1"
    assert req["store"] is False
    assert req["response_format"] == {"type": "image"}
    assert "vehicle" in req["input"][0]["text"].lower()
    assert req["input"][1]["type"] == "image"

    assert resultado.mode == "RGB"
    assert resultado.size == (120, 80)
    # Borda conectada foi normalizada para branco puro (255, 255, 255)
    assert resultado.getpixel((0, 0)) == (255, 255, 255)
    # Interior branco isolado pela peça escura NÃO foi forçado para 255
    assert resultado.getpixel((58, 38)) == (249, 249, 249)
    assert resultado.getpixel((30, 20)) == (20, 20, 20)


def test_remover_fundo_ia_prompt_peca_e_redimensiona_imagem_gigante():
    gigante = Image.new("RGB", (3000, 1500), (180, 190, 200))
    saida = Image.new("RGB", (1024, 512), (255, 255, 255))
    b64 = base64.b64encode(_png_bytes(saida)).decode("utf-8")
    fake_client = _FakeClient(
        SimpleNamespace(
            status="completed",
            output_image=SimpleNamespace(data=b64, mime_type="image/png"),
        )
    )

    remover_fundo_ia(gigante, tipo="peca", client=fake_client)
    req = fake_client.interactions.chamadas[0]
    assert "product" in req["input"][0]["text"].lower()
    enviada = Image.open(io.BytesIO(base64.b64decode(req["input"][1]["data"])))
    assert max(enviada.size) <= 2048


def test_remover_fundo_ia_erro_quando_sem_imagem_ou_excecao():
    im = Image.new("RGB", (64, 64), (100, 100, 100))
    sem_img = _FakeClient(SimpleNamespace(status="completed", output_image=None))
    with pytest.raises(RuntimeError, match="não retornou uma imagem"):
        remover_fundo_ia(im, client=sem_img)

    com_erro = _FakeClient(RuntimeError("falha remota"))
    with pytest.raises(RuntimeError, match="Nano Banana"):
        remover_fundo_ia(im, client=com_erro)


def test_remover_fundo_ia_cria_client_sem_sleep_infinito(monkeypatch):
    capturado = {}

    class _ClientStub:
        def __init__(self, *, api_key=None, http_options=None):
            capturado["api_key"] = api_key
            capturado["http_options"] = http_options
            saida = Image.new("RGB", (32, 32), (255, 255, 255))
            b64 = base64.b64encode(_png_bytes(saida)).decode("utf-8")
            self.interactions = _FakeInteractions(
                SimpleNamespace(
                    status="completed",
                    output_image=SimpleNamespace(data=b64, mime_type="image/png"),
                )
            )

    monkeypatch.setattr("anuncio.ia_fundo.genai.Client", _ClientStub)
    im = Image.new("RGB", (64, 64), (100, 100, 100))
    remover_fundo_ia(im, api_key="AQ.chave_teste")

    assert capturado["api_key"] == "AQ.chave_teste"
    opts = capturado["http_options"]
    assert opts is not None
    assert opts.timeout == 60_000
    assert opts.retry_options is not None
    assert opts.retry_options.attempts == 1


def test_remover_fundo_ia_traduz_erro_cota_free_tier_e_chave_invalida():
    im = Image.new("RGB", (64, 64), (100, 100, 100))

    RateLimitError = type("RateLimitError", (Exception,), {"status_code": 429})
    free_tier = _FakeClient(
        RateLimitError(
            "Error code: 429 - limit: 0 input tokens per minute on Free Tier"
        )
    )
    with pytest.raises(RuntimeError, match="Free Tier"):
        remover_fundo_ia(im, client=free_tier)

    AuthError = type("AuthenticationError", (Exception,), {"status_code": 401})
    invalida = _FakeClient(AuthError("API_KEY_INVALID"))
    with pytest.raises(RuntimeError, match="inválida"):
        remover_fundo_ia(im, client=invalida)

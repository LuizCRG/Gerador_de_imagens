"""Remoção de fundo de fotos sob demanda via Nano Banana (google-genai)."""

import base64
import io
import os
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
import numpy as np
from PIL import Image
from scipy.ndimage import label

from anuncio.layout import RAIZ_PROJETO

MODELO_NANO_BANANA = "gemini-nano-banana-2.1"
_ARQUIVO_ENV_PADRAO = RAIZ_PROJETO / ".env"
_NOME_CHAVE = "GEMINI_API_KEY"
_LADO_MAX_ENVIO = 2048
_LIMIAR_BRANCO_BORDA = 245
_TIMEOUT_REQUISICAO_MS = 60_000

_PROMPT_CARRO = (
    "Remove the entire background behind the main vehicle. "
    "Isolate ONLY the vehicle cleanly on a pure solid white (#FFFFFF) background, "
    "preserving its natural soft ground contact shadow directly under the tires. "
    "Keep the exact vehicle appearance, angles, colors, reflections, proportions, "
    "and details completely unchanged without adding or modifying any car parts."
)

_PROMPT_PECA = (
    "Remove the entire background behind the main automotive part/product. "
    "Isolate ONLY the product cleanly on a pure solid white (#FFFFFF) background, "
    "including clean interior holes or cutouts showing pure white (#FFFFFF). "
    "Keep the exact product shape, texture, colors, proportions, and details "
    "completely unchanged without adding text, shadows, or altering the part."
)


def _ler_env(env_path: Path) -> str:
    if not env_path.is_file():
        return ""
    for linha in env_path.read_text(encoding="utf-8").splitlines():
        texto = linha.strip()
        if not texto or texto.startswith("#") or "=" not in texto:
            continue
        chave, valor = texto.split("=", 1)
        if chave.strip() == _NOME_CHAVE:
            return valor.strip().strip('"').strip("'")
    return ""


def obter_chave_api(env_path: Path = _ARQUIVO_ENV_PADRAO) -> str:
    """Lê a chave da API do ambiente ou do arquivo .env local."""
    do_ambiente = os.environ.get(_NOME_CHAVE, "").strip()
    if do_ambiente:
        return do_ambiente
    return _ler_env(Path(env_path))


def salvar_chave_api(chave: str, env_path: Path = _ARQUIVO_ENV_PADRAO) -> None:
    """Salva ou atualiza GEMINI_API_KEY no arquivo .env local preservando outras linhas."""
    limpa = chave.strip()
    if not limpa or "\n" in limpa or "\r" in limpa:
        raise ValueError("Chave da API inválida")

    caminho = Path(env_path)
    linhas_existentes = (
        caminho.read_text(encoding="utf-8").splitlines() if caminho.is_file() else []
    )
    novas_linhas: list[str] = []
    substituiu = False
    for linha in linhas_existentes:
        texto = linha.strip()
        if texto and not texto.startswith("#") and "=" in texto:
            nome, _ = texto.split("=", 1)
            if nome.strip() == _NOME_CHAVE:
                novas_linhas.append(f"{_NOME_CHAVE}={limpa}")
                substituiu = True
                continue
        novas_linhas.append(linha)

    if not substituiu:
        novas_linhas.append(f"{_NOME_CHAVE}={limpa}")

    caminho.write_text("\n".join(novas_linhas) + "\n", encoding="utf-8")


def _preparar_imagem_envio(img: Image.Image) -> bytes:
    rgb = img if img.mode == "RGB" else img.convert("RGB")
    if max(rgb.size) > _LADO_MAX_ENVIO:
        escala = _LADO_MAX_ENVIO / max(rgb.size)
        novo_tam = (max(1, round(rgb.width * escala)), max(1, round(rgb.height * escala)))
        rgb = rgb.resize(novo_tam, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    return buf.getvalue()


def _limpar_fundo_borda_branca(img: Image.Image) -> Image.Image:
    if img.has_transparency_data:
        rgba = img.convert("RGBA")
        fundo = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        rgb = Image.alpha_composite(fundo, rgba).convert("RGB")
    elif img.mode != "RGB":
        rgb = img.convert("RGB")
    else:
        rgb = img.copy()

    arr = np.asarray(rgb).copy()
    quase_branco = arr.min(axis=2) >= _LIMIAR_BRANCO_BORDA
    rotulos, _ = label(quase_branco)
    bordas = np.concatenate([rotulos[0, :], rotulos[-1, :], rotulos[:, 0], rotulos[:, -1]])
    ids_borda = set(int(v) for v in np.unique(bordas) if v > 0)
    if ids_borda:
        mascara_borda = np.isin(rotulos, list(ids_borda))
        arr[mascara_borda] = (255, 255, 255)
    return Image.fromarray(arr, mode="RGB")


def _traduzir_erro_ia(exc: Exception) -> str:
    nome_cls = type(exc).__name__
    status = getattr(exc, "status_code", None)
    lower = str(exc).lower()

    if status == 429 or nome_cls == "RateLimitError":
        if "free tier" in lower or "limit: 0" in lower:
            return (
                "A chave atual está no nível gratuito (Free Tier), que tem cota 0 "
                "para o Nano Banana nesta conta. Ative o faturamento no Google AI "
                "Studio ou informe outra chave em 'Chave IA'."
            )
        return (
            "Limite de requisições da API Nano Banana atingido. "
            "Aguarde um momento e tente novamente."
        )

    if status in (401, 403) or nome_cls in ("AuthenticationError", "PermissionDeniedError"):
        return "Chave da API Nano Banana inválida ou sem permissão de acesso."

    if nome_cls == "APITimeoutError" or "timeout" in lower or "timed out" in lower:
        return "Tempo limite excedido ao aguardar resposta da API Nano Banana."

    if nome_cls == "APIConnectionError":
        return "Falha de conexão com a API Nano Banana. Verifique sua internet."

    if (isinstance(status, int) and status >= 500) or nome_cls == "InternalServerError":
        return "Serviço Nano Banana temporariamente indisponível. Tente novamente em instantes."

    return f"Falha ao chamar a API Nano Banana: {nome_cls}"


def remover_fundo_ia(
    img: Image.Image,
    *,
    tipo: str = "peca",
    api_key: str | None = None,
    env_path: Path = _ARQUIVO_ENV_PADRAO,
    client: Any = None,
) -> Image.Image:
    """Isola o objeto principal da imagem em fundo branco usando Nano Banana 2.1."""
    if client is None:
        chave = (api_key or "").strip() or obter_chave_api(env_path=env_path)
        if not chave:
            raise ValueError(f"Chave da API Nano Banana ({_NOME_CHAVE}) não configurada.")
        client = genai.Client(
            api_key=chave,
            http_options=types.HttpOptions(
                timeout=_TIMEOUT_REQUISICAO_MS,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    prompt = _PROMPT_CARRO if tipo == "carro" else _PROMPT_PECA
    img_bytes = _preparar_imagem_envio(img)

    try:
        interacao = client.interactions.create(
            model=MODELO_NANO_BANANA,
            input=[
                {"type": "text", "text": prompt},
                {
                    "type": "image",
                    "data": base64.b64encode(img_bytes).decode("utf-8"),
                    "mime_type": "image/png",
                },
            ],
            response_format={"type": "image"},
            store=False,
        )
    except Exception as exc:
        raise RuntimeError(_traduzir_erro_ia(exc)) from exc

    saida_img = getattr(interacao, "output_image", None)
    dados_b64 = getattr(saida_img, "data", None) if saida_img is not None else None
    if not dados_b64:
        raise RuntimeError("A API Nano Banana não retornou uma imagem.")

    bruto = base64.b64decode(dados_b64)
    with Image.open(io.BytesIO(bruto)) as im:
        im.load()
        return _limpar_fundo_borda_branca(im)

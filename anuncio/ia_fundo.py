"""Remoção de fundo de fotos sob demanda via Poof API."""

import io
import os
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image, UnidentifiedImageError
import requests
from scipy.ndimage import label

from anuncio.layout import RAIZ_PROJETO

ENDPOINT_POOF_API = "https://api.poof.bg/v1/remove"
_ARQUIVO_ENV_PADRAO = RAIZ_PROJETO / ".env"
_NOME_CHAVE = "POOF_API_KEY"
_LADO_MAX_ENVIO = 2048
_LIMIAR_BRANCO_BORDA = 245
_TIMEOUT_REQUISICAO_SEG = 60


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
    """Lê a chave da Poof API do ambiente ou do arquivo .env local."""
    do_ambiente = os.environ.get(_NOME_CHAVE, "").strip()
    if do_ambiente:
        return do_ambiente
    return _ler_env(Path(env_path))


def salvar_chave_api(chave: str, env_path: Path = _ARQUIVO_ENV_PADRAO) -> None:
    """Salva ou atualiza POOF_API_KEY no arquivo .env local preservando outras linhas."""
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
    modo = "RGBA" if img.has_transparency_data else "RGB"
    preparada = img if img.mode == modo else img.convert(modo)
    if max(preparada.size) > _LADO_MAX_ENVIO:
        escala = _LADO_MAX_ENVIO / max(preparada.size)
        novo_tam = (
            max(1, round(preparada.width * escala)),
            max(1, round(preparada.height * escala)),
        )
        preparada = preparada.resize(novo_tam, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    preparada.save(buf, format="PNG")
    return buf.getvalue()


def _limpar_fundo_borda_branca(img: Image.Image) -> Image.Image:
    rgb = img.copy() if img.mode == "RGB" else img.convert("RGB")
    arr = np.asarray(rgb).copy()
    quase_branco = arr.min(axis=2) >= _LIMIAR_BRANCO_BORDA
    rotulos, _ = label(quase_branco)
    bordas = np.concatenate([rotulos[0, :], rotulos[-1, :], rotulos[:, 0], rotulos[:, -1]])
    ids_borda = set(int(v) for v in np.unique(bordas) if v > 0)
    if ids_borda:
        mascara_borda = np.isin(rotulos, list(ids_borda))
        arr[mascara_borda] = (255, 255, 255)
    return Image.fromarray(arr, mode="RGB")


def _normalizar_saida_poof(img: Image.Image) -> Image.Image:
    if img.has_transparency_data:
        rgba = img.convert("RGBA")
        arr = np.asarray(rgba).copy()
        transparente = arr[..., 3] == 0
        if transparente.any():
            arr[transparente, :3] = 255
        return Image.fromarray(arr, mode="RGBA")
    return _limpar_fundo_borda_branca(img)


def _traduzir_erro_http(status_code: int, _body_text: str = "") -> str:
    if status_code == 401:
        return "Chave da Poof API inválida. Confira a chave configurada em 'Chave IA'."
    if status_code == 403:
        return "Acesso negado pela Poof API: verifique sua chave ou permissão em 'Chave IA'."
    if status_code == 402:
        return "Créditos da Poof API esgotados neste mês. Confira sua cota no painel da Poof."
    if status_code == 429:
        return "Limite de requisições por minuto da Poof API atingido. Aguarde um instante e tente novamente."
    if status_code == 400:
        return "A Poof API não conseguiu processar esta imagem. Verifique se o arquivo é válido."
    if status_code >= 500:
        return "Serviço Poof API temporariamente indisponível. Tente novamente em instantes."
    return f"Falha na Poof API (HTTP {status_code})."


def remover_fundo_ia(
    img: Image.Image,
    *,
    tipo: str = "peca",
    api_key: str | None = None,
    env_path: Path = _ARQUIVO_ENV_PADRAO,
    http_post: Callable[..., Any] | None = None,
) -> Image.Image:
    """Remove o fundo da imagem usando a Poof API mantendo transparência limpa."""
    del tipo  # Mantido na assinatura para compatibilidade com chamadas por bloco.
    chave = (api_key or "").strip() or obter_chave_api(env_path=env_path)
    if not chave:
        raise ValueError(f"Chave da Poof API ({_NOME_CHAVE}) não configurada.")

    post_fn = requests.post if http_post is None else http_post
    img_bytes = _preparar_imagem_envio(img)

    try:
        resp = post_fn(
            ENDPOINT_POOF_API,
            headers={"x-api-key": chave},
            files={"file": ("imagem.png", img_bytes, "image/png")},
            timeout=_TIMEOUT_REQUISICAO_SEG,
        )
    except requests.Timeout as exc:
        raise RuntimeError("Tempo limite excedido ao aguardar resposta da Poof API.") from exc
    except requests.RequestException as exc:
        raise RuntimeError("Falha de conexão com a Poof API. Verifique sua internet.") from exc

    if getattr(resp, "status_code", 0) != 200:
        raise RuntimeError(_traduzir_erro_http(int(resp.status_code), getattr(resp, "text", "")))

    conteudo = getattr(resp, "content", b"")
    if not conteudo:
        raise RuntimeError("A Poof API não retornou uma imagem válida.")

    try:
        with Image.open(io.BytesIO(conteudo)) as im:
            im.load()
            return _normalizar_saida_poof(im)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise RuntimeError("A Poof API não retornou uma imagem válida.") from exc

"""Servidor Flask local para prévia e exportação dos anúncios Shopee."""

import base64
import io
import math
from pathlib import Path
import re
from typing import Callable
import unicodedata

from flask import Flask, Response, jsonify, request, send_file
from PIL import Image, UnidentifiedImageError

from anuncio.cartao import detectar_area_foto, normalizar_recorte
from anuncio.ia_fundo import obter_chave_api, remover_fundo_ia, salvar_chave_api
from anuncio.imagens import abrir_imagem
from anuncio.layout import CARRO_LARG, ETIQ_TAM, PRINT_TAM, RAIZ_PROJETO, SUB_TAM, TITULO_TAM
from anuncio.montar import Entrada, Resultado, montar

_TIPOS_IMAGEM = frozenset({"carro", "peca", "print"})


def _erro(mensagem: str, status: int = 400) -> tuple[Response, int]:
    return jsonify({"erro": mensagem}), status


def _parse_bool(dados: dict[str, object], campo: str, padrao: bool = True) -> bool:
    valor = dados.get(campo)
    if valor is None:
        return padrao
    if not isinstance(valor, bool):
        raise ValueError(f"Campo '{campo}' inválido")
    return valor


def _parse_num(
    dados: dict[str, object],
    campo: str,
    padrao: int | float,
    minimo: float,
    maximo: float,
    *,
    inteiro: bool = True,
) -> int | float:
    valor = dados.get(campo)
    if valor is None:
        return padrao
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"Campo '{campo}' inválido")
    if isinstance(valor, float) and not math.isfinite(valor):
        raise ValueError(f"Campo '{campo}' inválido")
    if valor < minimo or valor > maximo:
        raise ValueError(f"Campo '{campo}' fora do limite ({minimo}..{maximo})")
    return round(valor) if inteiro else float(valor)


def _parse_recorte(
    valor: object, campo: str = "recorte_print"
) -> tuple[int, int, int, int] | None:
    if valor is None:
        return None
    if not isinstance(valor, (list, tuple)) or len(valor) != 4:
        raise ValueError(f"{campo} deve conter 4 números")
    coords: list[int] = []
    for item in valor:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{campo} deve conter 4 números")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError(f"{campo} contém valor inválido")
        coords.append(round(item))
    return (coords[0], coords[1], coords[2], coords[3])


def _metadados_recorte_imagem(tipo: str, img: Image.Image) -> dict[str, object]:
    if tipo == "print":
        area = detectar_area_foto(img)
        recorte = normalizar_recorte(None, img.size, area)
        return {"area": list(area), "recorte": list(recorte)}
    return {"recorte": [0, 0, img.width, img.height]}


def _slugify(titulo: str) -> str:
    normalizado = unicodedata.normalize("NFKD", titulo)
    sem_acentos = "".join(ch for ch in normalizado if not unicodedata.combining(ch))
    ascii_lower = sem_acentos.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_lower).strip("-")
    return slug or "anuncio"


def _caminho_disponivel(pasta: Path, slug: str) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    pasta_resolvida = pasta.resolve()
    candidato = pasta_resolvida / f"{slug}.png"
    indice = 2
    while candidato.exists():
        candidato = pasta_resolvida / f"{slug}-{indice}.png"
        indice += 1
    if not candidato.is_relative_to(pasta_resolvida):
        raise ValueError("Caminho de saída inválido")
    return candidato


def _montar_da_requisicao(imagens: dict[str, Image.Image]) -> tuple[Resultado, str]:
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise ValueError("Corpo JSON inválido")

    usar_carro = _parse_bool(dados, "usar_carro", True)
    usar_peca = _parse_bool(dados, "usar_peca", True)
    usar_print = _parse_bool(dados, "usar_print", True)
    usar_etiqueta = _parse_bool(dados, "usar_etiqueta", True)
    usar_titulo = _parse_bool(dados, "usar_titulo", True)
    usar_subtitulo = _parse_bool(dados, "usar_subtitulo", True)

    largura_carro = int(_parse_num(dados, "largura_carro", CARRO_LARG, 100, 980))
    escala_peca = float(_parse_num(dados, "escala_peca", 1.0, 0.2, 2.5, inteiro=False))
    largura_print = int(_parse_num(dados, "largura_print", PRINT_TAM[0], 100, 900))
    tam_titulo = int(_parse_num(dados, "tam_titulo", TITULO_TAM, 20, 300))
    tam_sub = int(_parse_num(dados, "tam_sub", SUB_TAM, 12, 150))
    tam_etiqueta = int(_parse_num(dados, "tam_etiqueta", ETIQ_TAM, 10, 80))

    titulo = "" if dados.get("titulo") is None else dados.get("titulo")
    if not isinstance(titulo, str):
        raise ValueError("Título inválido")

    subtitulo = [] if dados.get("subtitulo") is None else dados.get("subtitulo")
    if not isinstance(subtitulo, list) or not all(isinstance(s, str) for s in subtitulo):
        raise ValueError("Subtítulo inválido")

    etiqueta = "" if dados.get("etiqueta") is None else dados.get("etiqueta")
    if not isinstance(etiqueta, str):
        raise ValueError("Etiqueta inválida")

    recorte = _parse_recorte(dados.get("recorte_print"), "recorte_print")
    recorte_carro = _parse_recorte(dados.get("recorte_carro"), "recorte_carro")
    recorte_peca = _parse_recorte(dados.get("recorte_peca"), "recorte_peca")
    entrada = Entrada(
        carro=imagens.get("carro"),
        peca=imagens.get("peca"),
        print_img=imagens.get("print"),
        titulo=titulo,
        subtitulo=subtitulo,
        etiqueta=etiqueta,
        recorte_print=recorte,
        recorte_carro=recorte_carro,
        recorte_peca=recorte_peca,
        usar_carro=usar_carro,
        usar_peca=usar_peca,
        usar_print=usar_print,
        usar_etiqueta=usar_etiqueta,
        usar_titulo=usar_titulo,
        usar_subtitulo=usar_subtitulo,
        largura_carro=largura_carro,
        escala_peca=escala_peca,
        largura_print=largura_print,
        tam_titulo=tam_titulo,
        tam_sub=tam_sub,
        tam_etiqueta=tam_etiqueta,
    )
    return montar(entrada), (titulo if usar_titulo else "")


def _imagem_para_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def criar_app(
    pasta_saida: Path = Path("saida"),
    removedor_fundo: Callable[..., Image.Image] = remover_fundo_ia,
    env_path: Path | None = None,
) -> Flask:
    """Cria e configura a aplicação Flask com estado em memória e pasta de saída."""
    pasta_estatica = Path(__file__).resolve().parent / "static"
    app = Flask(__name__, static_folder=str(pasta_estatica))
    app.config["IMAGENS"] = {}
    app.config["IMAGENS_ORIGINAIS"] = {}
    app.config["IMAGENS_SEM_FUNDO"] = {}
    pasta_destino = Path(pasta_saida)
    caminho_env = (RAIZ_PROJETO / ".env") if env_path is None else Path(env_path)

    @app.get("/")
    def index() -> Response:
        app.config["IMAGENS"].clear()
        app.config["IMAGENS_ORIGINAIS"].clear()
        app.config["IMAGENS_SEM_FUNDO"].clear()
        return app.send_static_file("index.html")

    @app.post("/api/imagem/<tipo>")
    def enviar_imagem(tipo: str) -> tuple[Response, int] | Response:
        if tipo not in _TIPOS_IMAGEM:
            return _erro("Tipo de imagem inválido", 404)

        arquivo = request.files.get("arquivo")
        if arquivo is None:
            return _erro("Arquivo não enviado")

        dados = arquivo.read()
        if not dados:
            return _erro("Arquivo de imagem vazio")

        try:
            img = abrir_imagem(dados)
        except Image.DecompressionBombError:
            return _erro("Arquivo de imagem inválido ou grande demais")
        except (UnidentifiedImageError, OSError, ValueError):
            return _erro("Arquivo de imagem inválido ou ilegível")

        app.config["IMAGENS_ORIGINAIS"][tipo] = img
        app.config["IMAGENS_SEM_FUNDO"].pop(tipo, None)
        app.config["IMAGENS"][tipo] = img
        resposta: dict[str, object] = {"largura": img.width, "altura": img.height}
        resposta.update(_metadados_recorte_imagem(tipo, img))
        return jsonify(resposta)

    @app.post("/api/imagem/<tipo>/remover-fundo")
    def remover_fundo_rota(tipo: str) -> tuple[Response, int] | Response:
        if tipo not in _TIPOS_IMAGEM:
            return _erro("Tipo de imagem inválido", 404)

        original = app.config["IMAGENS_ORIGINAIS"].get(tipo)
        if original is None:
            return _erro("Envie a imagem antes de remover o fundo")

        dados = request.get_json(silent=True)
        if dados is not None and not isinstance(dados, dict):
            return _erro("Corpo JSON inválido")
        try:
            usar = _parse_bool(dados or {}, "usar", True)
        except ValueError as exc:
            return _erro(str(exc))

        if not usar:
            ativa = original
            fundo_removido = False
        else:
            em_cache = app.config["IMAGENS_SEM_FUNDO"].get(tipo)
            if em_cache is None:
                try:
                    em_cache = removedor_fundo(original, tipo=tipo, env_path=caminho_env)
                except ValueError as exc:
                    return _erro(str(exc))
                except RuntimeError as exc:
                    return _erro(str(exc), 502)
                app.config["IMAGENS_SEM_FUNDO"][tipo] = em_cache
            ativa = em_cache
            fundo_removido = True

        app.config["IMAGENS"][tipo] = ativa
        resposta: dict[str, object] = {
            "png": _imagem_para_b64(ativa),
            "largura": ativa.width,
            "altura": ativa.height,
            "fundo_removido": fundo_removido,
        }
        resposta.update(_metadados_recorte_imagem(tipo, ativa))
        return jsonify(resposta)

    @app.get("/api/config/ia")
    def status_config_ia() -> Response:
        return jsonify({"configurada": bool(obter_chave_api(env_path=caminho_env))})

    @app.post("/api/config/ia")
    def salvar_config_ia() -> tuple[Response, int] | Response:
        dados = request.get_json(silent=True)
        if not isinstance(dados, dict) or not isinstance(dados.get("api_key"), str):
            return _erro("Informe uma chave de API válida")
        try:
            salvar_chave_api(dados["api_key"], env_path=caminho_env)
        except ValueError as exc:
            return _erro(str(exc))
        return jsonify({"configurada": True})

    @app.post("/api/previa")
    def previa() -> tuple[Response, int] | Response:
        try:
            resultado, _ = _montar_da_requisicao(app.config["IMAGENS"])
        except ValueError as exc:
            return _erro(str(exc))

        return jsonify({
            "png": _imagem_para_b64(resultado.imagem),
            "avisos": resultado.avisos,
            "recorte_print": (
                list(resultado.recorte_print) if resultado.recorte_print is not None else None
            ),
        })

    @app.post("/api/salvar")
    def salvar() -> tuple[Response, int] | Response:
        try:
            resultado, titulo = _montar_da_requisicao(app.config["IMAGENS"])
        except ValueError as exc:
            return _erro(str(exc))

        caminho = _caminho_disponivel(pasta_destino, _slugify(titulo))
        resultado.imagem.save(caminho, format="PNG")
        return send_file(
            caminho.resolve(),
            mimetype="image/png",
            as_attachment=True,
            download_name=caminho.name,
        )

    return app


if __name__ == "__main__":
    criar_app().run(host="127.0.0.1", port=5000)

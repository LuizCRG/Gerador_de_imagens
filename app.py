"""Servidor Flask local para prévia e exportação dos anúncios Shopee."""

import base64
import io
import math
from pathlib import Path
import re
import unicodedata

from flask import Flask, Response, jsonify, request, send_file
from PIL import Image, UnidentifiedImageError

from anuncio.cartao import detectar_area_foto, normalizar_recorte
from anuncio.imagens import abrir_imagem
from anuncio.montar import Entrada, Resultado, montar

_TIPOS_IMAGEM = frozenset({"carro", "peca", "print"})
_IMAGENS_OBRIGATORIAS = (
    ("carro", "Envie a foto do carro"),
    ("peca", "Envie a foto da peça"),
    ("print", "Envie o print de aplicação"),
)


def _erro(mensagem: str, status: int = 400) -> tuple[Response, int]:
    return jsonify({"erro": mensagem}), status


def _parse_recorte(valor: object) -> tuple[int, int, int, int] | None:
    if valor is None:
        return None
    if not isinstance(valor, (list, tuple)) or len(valor) != 4:
        raise ValueError("recorte_print deve conter 4 números")
    coords: list[int] = []
    for item in valor:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("recorte_print deve conter 4 números")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("recorte_print contém valor inválido")
        coords.append(round(item))
    return (coords[0], coords[1], coords[2], coords[3])


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
    for chave, mensagem in _IMAGENS_OBRIGATORIAS:
        if chave not in imagens:
            raise ValueError(mensagem)

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise ValueError("Corpo JSON inválido")

    titulo = "" if dados.get("titulo") is None else dados.get("titulo")
    if not isinstance(titulo, str):
        raise ValueError("Título inválido")

    subtitulo = [] if dados.get("subtitulo") is None else dados.get("subtitulo")
    if not isinstance(subtitulo, list) or not all(isinstance(s, str) for s in subtitulo):
        raise ValueError("Subtítulo inválido")

    etiqueta = "" if dados.get("etiqueta") is None else dados.get("etiqueta")
    if not isinstance(etiqueta, str):
        raise ValueError("Etiqueta inválida")

    recorte = _parse_recorte(dados.get("recorte_print"))
    entrada = Entrada(
        carro=imagens["carro"],
        peca=imagens["peca"],
        print_img=imagens["print"],
        titulo=titulo,
        subtitulo=subtitulo,
        etiqueta=etiqueta,
        recorte_print=recorte,
    )
    return montar(entrada), titulo


def criar_app(pasta_saida: Path = Path("saida")) -> Flask:
    """Cria e configura a aplicação Flask com estado em memória e pasta de saída."""
    pasta_estatica = Path(__file__).resolve().parent / "static"
    app = Flask(__name__, static_folder=str(pasta_estatica))
    app.config["IMAGENS"] = {}
    pasta_destino = Path(pasta_saida)

    @app.get("/")
    def index() -> Response:
        app.config["IMAGENS"].clear()
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

        app.config["IMAGENS"][tipo] = img
        resposta: dict[str, object] = {"largura": img.width, "altura": img.height}
        if tipo == "print":
            area = detectar_area_foto(img)
            recorte = normalizar_recorte(None, img.size, area)
            resposta["area"] = list(area)
            resposta["recorte"] = list(recorte)
        return jsonify(resposta)

    @app.post("/api/previa")
    def previa() -> tuple[Response, int] | Response:
        try:
            resultado, _ = _montar_da_requisicao(app.config["IMAGENS"])
        except ValueError as exc:
            return _erro(str(exc))

        buf = io.BytesIO()
        resultado.imagem.save(buf, format="PNG")
        png_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return jsonify({
            "png": png_b64,
            "avisos": resultado.avisos,
            "recorte_print": list(resultado.recorte_print),
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

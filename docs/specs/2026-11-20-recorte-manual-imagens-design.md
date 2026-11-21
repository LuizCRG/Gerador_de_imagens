# Recorte Manual de Imagens em Carro e Peça (design)

## Intenção
Estender o mesmo editor visual de recorte e botão **Centralizar recorte** já existente em **Print de aplicação** para os blocos **Carro** e **Peça**, permitindo ajustar manualmente qual região de cada foto enviada entra no anúncio `1024×1024`.

## Abordagem escolhida
Reutilizar um editor único parametrizado por tipo (`carro`, `peca`, `print`) tanto no front-end quanto nas rotas Flask e em `anuncio/montar.py`:
- **Print de aplicação:** mantém proporção travada `350:255` e `recorte` inicial via `detectar_area_foto`.
- **Carro e Peça:** permitem recorte livre (arrastar caixa + redimensionar canto inferior direito em proporção livre, mínimo 40 px) com `recorte` inicial `[0, 0, largura, altura]` e botão **Centralizar recorte** para restaurar o enquadramento inicial.

## O que muda
1. **`anuncio/montar.py`:**
   - `Entrada` ganha `recorte_carro: tuple[int, int, int, int] | None = None` e `recorte_peca: tuple[int, int, int, int] | None = None`.
   - `Resultado` ganha `recorte_carro: tuple[int, int, int, int] | None = None` e `recorte_peca: tuple[int, int, int, int] | None = None` ao final dos campos.
   - `montar(e)` normaliza `recorte_carro` / `recorte_peca` dentro dos limites da imagem e recorta a foto antes de chamar `recortar_carro(...)` e `remover_fundo_branco(...)`.
2. **`app.py`:**
   - `POST /api/imagem/<tipo>` e `POST /api/imagem/<tipo>/remover-fundo` sempre retornam `"recorte": [l, t, r, b]` (e `"area"` quando `tipo == "print"`).
   - `_montar_da_requisicao` aceita `recorte_carro` e `recorte_peca` opcionais usando `_parse_recorte(valor, nome)`.
3. **`static/index.html`, `static/style.css`, `static/app.js` e `README.md`:**
   - Blocos **Carro** (`#crop-section-carro`, `#crop-canvas-carro`, `#btn-centralizar-carro`) e **Peça** (`#crop-section-peca`, `#crop-canvas-peca`, `#btn-centralizar-peca`) recebem `.crop-block` compacto (`maxH = 240` px) logo abaixo do controle de tamanho, mantendo os IDs originais do bloco **Print de aplicação**.
   - `static/app.js` unifica o estado e eventos dos 3 editores em `state.cropMeta[tipo]`, `state.crops[tipo]`, `state.drag` e envia `recorte_carro`, `recorte_peca` e `recorte_print` em `buildPayload()`.
   - Atualiza também o editor de recorte quando **Remover fundo (IA)** / **Restaurar original** altera a imagem ativa de qualquer tipo (`carro`, `peca` ou `print`).

# Remoção de Fundo com Nano Banana – Implementation Plan

**Goal:** Integrar remoção de fundo sob demanda via `google-genai` (`gemini-nano-banana-2.1`) mantendo o original na sessão para alternar/restaurar com um clique.

**Spec:** `docs/specs/2026-11-20-remover-fundo-nanobanana-design.md`

---

### Task 1: Módulo `anuncio/ia_fundo.py` + `requirements.txt`
- **Files:** `requirements.txt`, `anuncio/ia_fundo.py`, `tests/test_ia_fundo.py`
- Adicionar `google-genai>=2.30.1` em `requirements.txt`.
- Implementar `obter_chave_api`, `salvar_chave_api`, `_limpar_fundo_borda_branca` e `remover_fundo_ia(img, *, tipo="peca", api_key=None, client=None) -> Image.Image`.
- Testes TDD (`tests/test_ia_fundo.py`) usando cliente falso em memória (sem chamadas externas na suíte pytest): leitura/escrita de `.env`, erro sem chave, construção correta da chamada `interactions.create(model="gemini-nano-banana-2.1", ..., store=False)` para `carro` e `peca`, limpeza de branco quase-puro na borda sem apagar branco interno, erro claro quando `output_image` vier ausente ou API lançar exceção.

### Task 2: Endpoints Flask em `app.py`
- **Files:** `app.py`, `tests/test_app.py`
- `criar_app(..., removedor_fundo=remover_fundo_ia, env_path=...)`: guarda `IMAGENS_ORIGINAIS`, `IMAGENS_SEM_FUNDO` e `IMAGENS` (limpos em `GET /` e resetados por `tipo` em novo upload).
- `POST /api/imagem/<tipo>/remover-fundo`: aplica e cacheia remoção (`usar=True`) ou restaura original (`usar=False`); retorna `{png, largura, altura, fundo_removido}` (+ `area`, `recorte` para `print`).
- `GET /api/config/ia` (`{"configurada": bool}`) e `POST /api/config/ia` (`{"api_key": "..."}`).
- Testes TDD em `tests/test_app.py` cobrindo remoção, cache na segunda chamada, restauração, novo upload invalidando cache, erro 400 sem imagem, erro 400/502 em falha da IA, e config da chave sem vazar o valor em `GET`.

### Task 3: Interface web + verificação completa
- **Files:** `static/index.html`, `static/style.css`, `static/app.js`, `README.md`, `tests/test_app.py`
- Adicionar botão **Remover fundo (IA)** / **Restaurar original** em cada bloco de foto (`carro`, `peca`, `print`), exibido após upload e atualizando miniatura + `#crop-canvas` (para `print`) + prévia ao vivo.
- Adicionar badge/controle discreto de chave API no cabeçalho (`IA: Configurada` / painel para trocar chave via `POST /api/config/ia`).
- Atualizar `tests/test_app.py` (`test_pagina_inicial` verificando novos controles e `test_ativos_estaticos_e_offline` verificando ausência de URLs externas) e `README.md`.
- Verificação final: `node --check static/app.js`, `python -m pytest -v`, e teste real no navegador (`http://127.0.0.1:5000`) com uma foto real de carro/peça com fundo colorido para validar o recorte real pelo Nano Banana.

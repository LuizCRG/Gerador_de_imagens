# Remoção de Fundo com Poof API – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o cliente Nano Banana (`google-genai`) pela Poof API (`POST https://api.poof.bg/v1/remove`) mantendo cache, restauração e controles de UI existentes.

**Architecture:** `anuncio/ia_fundo.py` passa a ler/gravar `POOF_API_KEY` no `.env` e enviar a imagem como `multipart/form-data` para a Poof API via `requests.post` (`x-api-key`, timeout 60s), preservando a transparência `RGBA` retornada e zerando cores ocultas em pixels `alpha == 0`. O servidor Flask (`app.py`) e os endpoints permanecem compatíveis, com textos da interface e testes atualizados para **Poof API**.

**Tech Stack:** Python 3.15, `requests>=2.31.0`, Pillow, NumPy, SciPy, Flask, Vanilla JS/CSS.

**Spec:** `docs/specs/2026-11-20-remover-fundo-poof-api-design.md`

## Global Constraints
- Chave da API lida de `POOF_API_KEY` (ambiente ou `.env` local ignorado pelo `.gitignore`), nunca commitada nem retornada em HTML/JS/JSON.
- Arquivos em `static/` não podem conter `http://` nem `https://` (`test_ativos_estaticos_e_offline`).
- Chamada HTTP à Poof API (`https://api.poof.bg/v1/remove`) sempre com `timeout=60`.
- Pixels totalmente transparentes (`alpha == 0`) na saída `RGBA` devem ter canais RGB definidos como `(255, 255, 255, 0)` para não interferir em `detectar_area_foto` nem `recortar_carro`.

## Review Focus
- `RGBA` da Poof com RGB oculto sob `alpha == 0` (ex.: `(20, 40, 60, 0)`) deve virar `(255, 255, 255, 0)` sem alterar pixels opacos/semitransparentes.
- Imagem maior que 2048 px no maior lado deve ser reduzida proporcionalmente antes do envio multipart.
- Erros HTTP da Poof (`400`, `401`/`403`, `402`, `429`, `5xx`) e exceções de `requests` (`Timeout`, `RequestException`) devem gerar `RuntimeError` em português sem vazar a chave.
- Resposta `200` com bytes inválidos (não imagem) deve gerar `RuntimeError("A Poof API não retornou uma imagem válida.")`.
- Se a Poof devolver imagem opaca sem transparência (`RGB`), aplicar limpeza de borda quase branca (`>= 245` conectado às bordas -> `(255, 255, 255)`).

---

### Task 1: Motor Poof API em `anuncio/ia_fundo.py` + `requirements.txt`

**Files:**
- Modify: `requirements.txt`
- Modify: `anuncio/ia_fundo.py`
- Test: `tests/test_ia_fundo.py`

**Interfaces:**
- Produces:
  - `ENDPOINT_POOF_API = "https://api.poof.bg/v1/remove"`
  - `obter_chave_api(env_path: Path = _ARQUIVO_ENV_PADRAO) -> str`
  - `salvar_chave_api(chave: str, env_path: Path = _ARQUIVO_ENV_PADRAO) -> None`
  - `remover_fundo_ia(img: Image.Image, *, tipo: str = "peca", api_key: str | None = None, env_path: Path = _ARQUIVO_ENV_PADRAO, http_post: Callable[..., Any] | None = None) -> Image.Image`

- [ ] **Step 1: Atualizar `tests/test_ia_fundo.py` (TDD RED)**
  - Cobrir `POOF_API_KEY` em `obter_chave_api` / `salvar_chave_api` e erro `ValueError` quando ausente.
  - Testar `remover_fundo_ia` enviando para `ENDPOINT_POOF_API` com `headers={"x-api-key": ...}`, `files={"file": ...}`, `timeout=60`, redimensionando imagem > 2048 px.
  - Testar saída `RGBA` com RGB oculto `(20, 40, 60, 0)` virando `(255, 255, 255, 0)` mantendo o sujeito opaco intacto, e fallback `RGB` limpando borda quase-branca.
  - Testar erros `401`/`403`, `402`, `429`, `400`, `500`, `requests.Timeout`, `requests.RequestException` e bytes inválidos em `200`.

- [ ] **Step 2: Rodar `python -m pytest tests/test_ia_fundo.py -q` para confirmar RED**
  - Expected: FAIL (constantes/parâmetro `http_post` e `POOF_API_KEY` ainda não implementados).

- [ ] **Step 3: Atualizar `requirements.txt` e implementar `anuncio/ia_fundo.py` (GREEN)**
  - Trocar `google-genai>=2.30.1` por `requests>=2.31.0` em `requirements.txt`.
  - Implementar `ENDPOINT_POOF_API`, `_NOME_CHAVE = "POOF_API_KEY"`, `_TIMEOUT_REQUISICAO_SEG = 60`, `_traduzir_erro_http`, `_normalizar_saida_poof` e `remover_fundo_ia` em `anuncio/ia_fundo.py`.

- [ ] **Step 4: Rodar `python -m pytest tests/test_ia_fundo.py -q` para confirmar GREEN**
  - Expected: PASS em todos os testes de `tests/test_ia_fundo.py`.

---

### Task 2: Testes de App, Interface (`static/`) e `README.md`

**Files:**
- Modify: `tests/test_app.py:481-500`
- Modify: `static/index.html`
- Modify: `static/app.js`
- Modify: `README.md`

**Interfaces:**
- Consumes: `obter_chave_api`, `salvar_chave_api`, `remover_fundo_ia` de `anuncio/ia_fundo.py` via `app.py`.

- [ ] **Step 1: Atualizar `tests/test_app.py` (`test_config_ia_nao_expoe_chave_e_salva_env` + marcadores Poof em `test_pagina_inicial`) e rodar `python -m pytest tests/test_app.py -q` (RED)**
  - Verificar que `.env` grava `POOF_API_KEY=...` e que `GET /` exibe rótulo `Poof API` sem conter `http://`/`https://`.

- [ ] **Step 2: Atualizar `static/index.html`, `static/app.js` e `README.md` (GREEN)**
  - Trocar referências visíveis de `Nano Banana` / `GEMINI_API_KEY` por `Poof API` / `POOF_API_KEY`.
  - Garantir em `static/app.js` que erros de chave/crédito (`inválida|sem permissão|créditos`) ou `400` abram `#ia-config-panel` se útil, mantendo zero URLs em `static/`.

- [ ] **Step 3: Verificar suíte e sintaxe**
  - Rodar `node --check static/app.js` e `python -m pytest -v`.
  - Expected: saída `0` e 100% dos testes `PASSED`.

---

### Task 3: Validação Real no Navegador + Commit

- [ ] **Step 1: Gravar `POOF_API_KEY` no `.env` local (gitignored)**
- [ ] **Step 2: Subir Flask (`python app.py`), testar no navegador (`http://127.0.0.1:5000`)**
  - Confirmar `#ia-status` = `IA: Pronta`, upload de imagens, 1 chamada real a **Remover fundo (IA)** na peça, checar miniatura + prévia `1024×1024` sem fundo azul, alternar **Restaurar original** e reaplicar do cache.
- [ ] **Step 3: Verificar `git status` (garantir `.env` ignorado e zero segredos rastreados), rodar `pytest -q` + `node --check` e commitar em `main`.**

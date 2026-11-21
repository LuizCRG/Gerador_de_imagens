# Recorte Manual de Carro e Peça – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar editor interativo de recorte + botão **Centralizar recorte** aos blocos **Carro** e **Peça** igual ao do **Print de aplicação**, integrando com `montar()` e rotas Flask.

**Architecture:** `anuncio/montar.py` recebe `recorte_carro` e `recorte_peca` opcionais em `Entrada`, normaliza os limites na imagem e aplica `.crop()` antes de `recortar_carro()` / `remover_fundo_branco()`. `app.py` devolve `recorte` em todos os uploads e ações de fundo IA e encaminha `recorte_carro`/`recorte_peca` ao `montar()`. No front-end (`static/`), uma lógica única parametrizada por `tipo` (`carro`, `peca`, `print`) controla os três `<canvas>` de recorte e envia os três recortes em `buildPayload()`.

**Tech Stack:** Python 3.15, Pillow, Flask, Vanilla JS/CSS/HTML, pytest.

**Spec:** `docs/specs/2026-11-20-recorte-manual-imagens-design.md`

## Global Constraints
- Preservar todos os IDs existentes no bloco Print (`crop-section`, `crop-info`, `btn-centralizar-recorte`, `crop-canvas-wrap`, `crop-canvas`) e comportamento `350:255` via `detectar_area_foto`.
- Sem URLs externas (`http://`/`https://`) em `static/`.
- Não duplicar código: unificar parser/metadados em `app.py`, helper de recorte em `anuncio/montar.py` e editor de canvas parametrizado em `static/app.js`.

## Review Focus
- `recorte_carro` ou `recorte_peca` fora dos limites ou com coordenadas invertidas `(r <= l, b <= t)` deve ser clampado com segurança dentro de `(0, 0, w, h)` sem `SystemError` / `ValueError` do Pillow.
- `recorte_carro` ou `recorte_peca` cobrindo só área branca/transparente não deve quebrar `montar()` (fallback limpo).
- `recorte_carro` / `recorte_peca` inválido no JSON de `/api/previa` ou `/api/salvar` (ex.: `[1, 2]` ou string) deve retornar HTTP `400` com nome do campo no erro.
- Trocar foto via upload ou alternar **Remover fundo (IA)** / **Restaurar original** em `carro` ou `peca` deve atualizar a imagem e redefinir o canvas de recorte daquele bloco imediatamente.
- Desativar o switch `Ativar` de `carro` ou `peca` deve esconder o editor daquele bloco e enviar `recorte_carro: null` / `recorte_peca: null`.

---

### Task 1: Suporte a `recorte_carro` e `recorte_peca` em `anuncio/montar.py`

**Files:**
- Modify: `anuncio/montar.py`
- Test: `tests/test_montar.py`

**Interfaces:**
- Produces:
  - `Entrada.recorte_carro: tuple[int, int, int, int] | None = None`
  - `Entrada.recorte_peca: tuple[int, int, int, int] | None = None`
  - `Resultado.recorte_carro: tuple[int, int, int, int] | None = None`
  - `Resultado.recorte_peca: tuple[int, int, int, int] | None = None`

- [ ] **Step 1: Escrever testes falhando em `tests/test_montar.py` (RED)**
  - `test_montar_respeita_recorte_carro_e_peca`: imagem dupla de peça (objeto vermelho à esquerda, objeto azul à direita) e carro com faixa lateral extra; passando `recorte_peca` só no lado esquerdo e `recorte_carro` no veículo, verificar que a cor do lado excluído não aparece no anúncio final e `Resultado` devolve `recorte_carro` e `recorte_peca` normalizados.
  - `test_montar_recorte_carro_peca_limites_e_vazio`: passar coordenadas fora dos limites / invertidas e área totalmente branca sem quebrar.

- [ ] **Step 2: Rodar `python -m pytest tests/test_montar.py -q` para confirmar RED**

- [ ] **Step 3: Implementar `_normalizar_recorte_livre`, `_recortar_entrada` e integração em `montar()`**

- [ ] **Step 4: Rodar `python -m pytest tests/test_montar.py -q` para confirmar GREEN**

---

### Task 2: Rotas Flask em `app.py` + testes em `tests/test_app.py`

**Files:**
- Modify: `app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Escrever testes falhando em `tests/test_app.py` (RED)**
  - Verificar que `POST /api/imagem/carro` e `POST /api/imagem/peca` retornam `"recorte": [0, 0, largura, altura]`.
  - Verificar que `POST /api/imagem/peca/remover-fundo` também retorna `"recorte": [0, 0, largura, altura]`.
  - Verificar que `POST /api/previa` aplica `recorte_carro` e `recorte_peca` e rejeita valores inválidos com HTTP `400` citando o campo.
  - Verificar em `test_pagina_inicial` os novos elementos (`id="crop-canvas-carro"`, `id="btn-centralizar-carro"`, `id="crop-canvas-peca"`, `id="btn-centralizar-peca"`).

- [ ] **Step 2: Rodar `python -m pytest tests/test_app.py -q` para confirmar RED**

- [ ] **Step 3: Atualizar `app.py` (`_parse_recorte`, `_metadados_recorte_imagem`, `_montar_da_requisicao`)**

---

### Task 3: Editores de Recorte na Interface (`static/`) + `README.md`

**Files:**
- Modify: `static/index.html`
- Modify: `static/style.css`
- Modify: `static/app.js`
- Modify: `README.md`

- [ ] **Step 1: Adicionar `.crop-block` em Carro e Peça no `static/index.html` com atributos `data-crop-*` unificados e IDs dedicados**
- [ ] **Step 2: Ajustar espaçamento compacto em `static/style.css` (`.crop-block` e `.crop-header h4`)**
- [ ] **Step 3: Refatorar `static/app.js` para gerenciar os 3 editores de recorte (`carro`, `peca`, `print`) via funções únicas parametrizadas por `tipo`, mantendo proporção livre em `carro`/`peca` e `350:255` em `print`, atualizando em upload e em `toggleRemoverFundo(tipo)`**
- [ ] **Step 4: Atualizar `README.md` mencionando recorte manual em Carro, Peça e Print**
- [ ] **Step 5: Rodar `node --check static/app.js` e `python -m pytest -v` (GREEN total)**

---

### Task 4: Teste Real no Navegador + Commit

- [ ] **Step 1: Subir Flask (`python app.py`), testar no navegador (`http://127.0.0.1:5000`) com imagens staged:**
  - Verificar editores de recorte aparecendo para **Carro**, **Peça** e **Print de aplicação** após upload.
  - Arrastar/redimensionar recorte no **Carro** e na **Peça**, conferir que a prévia `1024×1024` recorta de fato a região escolhida, e testar **Centralizar recorte** em ambos.
- [ ] **Step 2: Encerrar Flask, re-rodar `node --check` + `pytest -q`, checar `git status` e commitar em `main`.**

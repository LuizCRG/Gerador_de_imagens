# Ajustes de Layout, Remoção de Glow e Controles – Implementation Plan

**Goal:** Remover o glow azul da peça, adicionar ajuste de dimensões para todas as imagens/textos e permitir ligar/desligar cada bloco com reaproveitamento automático do espaço livre.

**Spec:** `docs/specs/2026-11-20-ajustes-layout-e-controles-design.md`

---

### Task 1: Remover glow azul e parametrizar dimensões nas funções de imagem/cartão/texto
- **Files:** `anuncio/layout.py`, `anuncio/imagens.py`, `anuncio/cartao.py`, `anuncio/textos.py`, `tests/test_peca.py`, `tests/test_carro.py`, `tests/test_cartao.py`, `tests/test_textos.py`
- `anuncio/imagens.py`:
  - `compor_peca(canvas, peca, pos)`: remove camadas de `GLOW`, compõe apenas a peça RGBA.
  - `encaixar_peca(peca, escala=1.0, caixa=CAIXA_PECA)`: aceita `caixa` customizável e mantém posicionamento centralizado com clamp seguro aos limites do canvas quando `escala > 1.0` e a peça cabe no canvas.
  - `recortar_carro(img, largura=CARRO_LARG, altura_max=CARRO_ALT_MAX)`: aceita dimensões customizadas.
- `anuncio/cartao.py`:
  - `desenhar_cartao(canvas, img_print, recorte, largura=PRINT_TAM[0]) -> tuple[int,int,int,int]`: ancora na base inferior (`CARTAO_POS[1] + PRINT_TAM[1] + 2 * CARTAO_BORDA`), devolvendo a caixa exata `(x0, y0, x1, y1)`.
  - `desenhar_etiqueta(canvas, texto, tam_fonte=ETIQ_TAM, pos=None) -> tuple[int,int,int,int]`: aceita `tam_fonte` e `pos` (calculada sobre `caixa_cartao` ou padrão `ETIQ_POS`), altura `round(ETIQ_ALT * tam_fonte / ETIQ_TAM)`.
- `anuncio/textos.py`:
  - `posicionar_textos(..., usar_titulo=True, usar_subtitulo=True, larg_max_titulo=TITULO_LARG_MAX, tam_titulo=TITULO_TAM, tam_sub=SUB_TAM)`: permite omitir título ou subtítulo, respeitando `larg_max_titulo`, posicionando subtítulo direto abaixo de `base_carro` quando `usar_titulo=False`.
- Atualizar `tests/test_peca.py` (sem glow azul) e adicionar testes TDD para dimensões/caixas em `test_carro.py`, `test_cartao.py`, `test_textos.py`.

### Task 2: Montagem adaptativa com flags `usar_*`, dimensões e reaproveitamento de espaço
- **Files:** `anuncio/montar.py`, `tests/test_montar.py`
- Estender `Entrada` com `usar_carro`, `usar_peca`, `usar_print`, `usar_etiqueta`, `usar_titulo`, `usar_subtitulo`, `largura_carro`, `escala_peca`, `largura_print`, `tam_titulo`, `tam_sub`, `tam_etiqueta` (e tornar `carro`, `peca`, `print_img` opcionais `Image | None = None`).
- Validação de entradas ativas e erro se tudo desativado.
- Cálculo adaptativo de `base_carro_efetivo`, `larg_max_titulo` (`952` sem peça), limite do subtítulo contra cartão/etiqueta (só quando `usar_print` ativo; se `usar_etiqueta=False`, usa topo do cartão `- 14`), e seleção geométrica da caixa da peça (`CAIXA_PECA` vs caixa livre complementar quando vizinhos estão desativados).
- Avisos comparados aos tamanhos iniciais pedidos na `Entrada`; `_proximo_ajuste` só tenta reduzir elementos que estão ativos.
- Testes TDD cobrindo todas as combinações de desligar blocos (sem print, sem carro, sem peça, sem título, sem etiqueta, só peça, tudo desligado) e dimensões personalizadas sem falsos avisos.

### Task 3: API Flask (`app.py`) aceitando flags e dimensões
- **Files:** `app.py`, `tests/test_app.py`
- `_montar_da_requisicao` lê flags `usar_*` (bool, padrão `True`) e dimensões numéricas (validadas com faixas seguras e mensagens HTTP 400 em tipos/valores inválidos), exigindo apenas as imagens dos blocos ativos (`carro`, `peca`, `print`) e gerando slug seguro (fallback `"anuncio"` se título desativado).
- Testes TDD em `tests/test_app.py`.

### Task 4: Interface web com toggles de ativação e controles deslizantes de dimensões
- **Files:** `static/index.html`, `static/style.css`, `static/app.js`, `README.md`, `tests/test_app.py`
- Toggles `Ativar` por bloco (Carro, Peça, Print, Etiqueta, Título, Subtítulo), recolhendo controles quando desativados e preservando arquivos já enviados na sessão caso reativados.
- Sliders com valor exibido ao lado e botão `"Restaurar padrões"`.
- Validação client-side (`validateBeforeSave` / `allRequiredReady`) considerando apenas blocos ativos.
- Verificação completa: `python -m pytest -v`, `node --check static/app.js`, e teste real no navegador em `http://127.0.0.1:5000`.

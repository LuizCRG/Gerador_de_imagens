# Ajustes de Layout, Remoção de Glow e Controles Individuais (design)

## Intenção
Evoluir o app local para:
1. Remover o glow azul da peça (peça limpa sobre o fundo radial).
2. Permitir ajustar as dimensões de cada imagem e texto diretamente na interface.
3. Permitir ativar e desativar cada bloco individualmente, liberando e reaproveitando na composição o espaço dos blocos desativados.

## Mudanças no Motor (`anuncio/`)

### 1. Remoção do glow azul (`anuncio/imagens.py`, `anuncio/layout.py`)
- `compor_peca(canvas, peca, pos)` passa a compor apenas a peça RGBA sobre o canvas, sem as camadas de glow azul.

### 2. Dimensões ajustáveis (`anuncio/imagens.py`, `anuncio/cartao.py`, `anuncio/textos.py`, `anuncio/montar.py`)
- **Carro:** `largura_carro` (px, padrão `500`, faixa na UI `250..900`); altura máxima escala na mesma proporção (`round(275 * largura_carro / 500)`).
- **Peça:** `escala_peca` (fator, padrão `1.0`, faixa na UI `0.40..1.60`). Quando a peça ampliada ultrapassar a caixa inicial, desloca para caber nos limites do canvas (`12..1012`) quando possível.
- **Cartão do print:** `largura_print` (px, padrão `350`, faixa na UI `200..560`), mantendo proporção `350:255`, âncora inferior esquerda fixa em `(40, 983)` (equivalente a `(40, 712)` no padrão `350×255`), borda `8 px`, cantos proporcionais/padrão.
- **Etiqueta do print:** `tam_etiqueta` (px, padrão `24`, faixa na UI `14..40`), altura `round(46 * tam / 24)`, contorno `4`, posicionada sobre a borda superior do cartão (`x0_cartao + 22`, `y0_cartao - alt // 2` — igual a `(62, 689)` no padrão).
- **Título:** `tam_titulo` (px, padrão `132`, faixa na UI `48..180`).
- **Subtítulo:** `tam_sub` (px, padrão `40`, faixa na UI `20..72`).
- Avisos de redução passam a comparar contra os valores solicitados na `Entrada` (e não contra `132`/`40`/`100%` fixos), evitando falsos avisos quando o usuário escolher um tamanho menor.

### 3. Ativar/desativar blocos e reaproveitamento de espaço (`anuncio/montar.py`, `app.py`)
Flags booleanas na `Entrada` (todas `True` por padrão):
`usar_carro`, `usar_peca`, `usar_print`, `usar_etiqueta`, `usar_titulo`, `usar_subtitulo`.

Comportamento quando cada bloco está desativado:
- **`usar_carro = False`:** não exige foto do carro nem aplica multiply; títulos/subtítulos sobem para o topo esquerdo (`base_carro_efetivo = 20` em vez de `283`), eliminando o espaço vazio superior.
- **`usar_peca = False`:** não exige foto da peça; `TITULO_LARG_MAX` expande de `560` para a largura útil inteira do canvas (`CANVAS - TITULO_X - 36 = 952 px`); nenhuma verificação contra `mascara_peca`.
- **`usar_print = False`:** não exige print de aplicação; `sub_x_etiqueta` e `cartao_x_peca` são ignorados, permitindo que subtítulo e peça ocupem a parte inferior esquerda.
- **`usar_etiqueta = False`:** (mesmo com `usar_print = True`) não desenha a pílula azul; o limite do subtítulo passa a ser `y0_cartao - 14` (topo do cartão branco) em vez do topo da pílula.
- **`usar_titulo = False`:** não exige texto de título; se `usar_subtitulo = True`, o subtítulo sobe diretamente para logo abaixo do carro (ou topo esquerdo `20` se o carro também estiver desativado).
- **`usar_subtitulo = False`:** não desenha nem verifica subtítulo.
- **Caixa adaptativa da peça (`usar_peca = True`):**
  - Quando todos os blocos estão ativos (ou no caso padrão), usa `CAIXA_PECA = (420, 12, 1000, 1012)`.
  - Quando blocos vizinhos estão desativados, gera também a caixa livre complementar (ex.: canvas inteiro `(24, 24, 1000, 1000)` se só a peça estiver ativa; faixa inferior inteira `(24, y_fim_esquerda + 24, 1000, 1000)` se `usar_print = False`; faixa superior `(24, 24, 1000, y_topo_print - 24)` se só o print estiver ativo à esquerda) e escolhe a caixa que permite encaixar a peça com maior dimensão sem sobrepor os blocos ativos.
- **Todos desativados:** lança `ValueError("Ative pelo menos um elemento para gerar o anúncio.")`.

## Mudanças na Interface (`static/`)
- Cada bloco tem um toggle `Ativar` no cabeçalho, recolhendo os controles do bloco quando desligado (mantendo em memória eventuais arquivos já enviados caso seja religado na mesma sessão).
- Controles deslizantes (`<input type="range">`) com leitura numérica ao lado e botão `"Restaurar tamanhos padrão"`.
- Prévia e validação (`validateBeforeSave`) exigem apenas fotos/título dos blocos ativos.

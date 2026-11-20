# Gerador de Imagem Principal – Anúncio Shopee (design)

## Intenção
App pessoal, rodando só neste PC (Windows), que transforma o prompt de layout em uma
ferramenta repetível: entra com 3 fotos + textos, sai o PNG 1024×1024 idêntico ao
`imagem de referencia.png`, sem IA redesenhando nada — só recorte, máscara e posicionamento.

## Metas
- Montar a imagem seguindo **exatamente** a especificação original (cores, posições,
  fontes, glow, multiply, cartão, pílula).
- Prévia ao vivo enquanto edito textos e o recorte do print.
- Verificação automática de sobreposição/cortes, com correção mínima (só tamanho de
  fonte ou da peça) e aviso visível do que foi ajustado.
- Baixar o PNG e também salvar em `saida/`.

## Não-metas
- Hospedar online, multiusuário, login.
- Outros templates/layouts, processamento em lote, histórico de projetos.
- Gerar ou "melhorar" fotos com IA.

## Anti-metas (falha mesmo que "funcione")
- Alterar o conteúdo das fotos além de recorte/remoção de fundo branco.
- Depender de internet para funcionar.
- Entregar imagem com texto cortado ou elementos sobrepostos sem avisar.

## Abordagens consideradas
| | Abordagem | Troca |
|---|---|---|
| **A (escolhida)** | Página local no navegador (Flask) + motor Python/Pillow | Uma lib extra (Flask); melhor para arrastar fotos e desenhar recorte |
| B | Janela Tkinter | Zero instalação extra, mas recorte/arrastar desajeitados |
| C | Streamlit | Rápido, mas recorte com mouse frágil e recarrega tudo |

Escolhida **A** por você: o recorte do print é o único passo manual e fica muito mais
fácil com prévia ao vivo no navegador.

## Como funciona
**Estrutura**
- `gerador.py` – motor puro (Pillow/numpy/scipy). Função `montar(carro, peca, print_img,
  recorte_print, titulo, subtitulo_linhas, etiqueta) -> (imagem, avisos)`. Testável
  isoladamente; também roda por linha de comando.
- `app.py` – servidor Flask em `http://127.0.0.1:5000`, recebe as imagens/textos, devolve
  a prévia PNG e os avisos.
- `static/index.html` (+ JS puro, sem build) – formulário, arrastar-e-soltar das 3 fotos,
  editor de recorte do print, prévia, botão "Baixar PNG".
- `abrir.bat` – inicia o servidor e abre o navegador.
- `tests/` – testes do motor (pytest).

**Fluxo na tela**
1. Arrasto carro, peça e print.
2. Digito título, subtítulo (até 3 linhas) e etiqueta.
3. No print aparece um retângulo travado em 350:255 que eu movo/redimensiono.
4. A prévia atualiza sozinha; avisos aparecem abaixo dela.
5. "Baixar PNG" baixa e salva em `saida/<titulo>.png`.

**Motor – pontos da especificação implementados como escritos**: fundo radial,
remoção de fundo branco por luminosidade (bordas suaves, buracos transparentes), caixa
da peça x 420–1000 / y 12–1012, glow em 3 camadas, carro com bbox não-branco + 15 px,
500 px de largura (limite 275 de altura) em (24, 8) com multiply, título Inter Black 132
em x=36 com baseline = base do carro + 112 e +126, subtítulo Inter ExtraBold 40 em x=40
(+56, passo 48), cartão 350×255 raio 26 / borda 8 / raio 30 / sombra 43% blur 14 +12 px
em (40, 712), pílula (22,119,255) contorno 4, texto 24, altura 46, largura texto+44 em
(62, 689).

## Decisões minhas (confira)
- **Fonte**: uso `Inter/static/Inter_18pt-Black.ttf` e `Inter_18pt-ExtraBold.ttf` da sua
  pasta (é o desenho "texto", equivalente ao Inter-Black.otf do Linux da especificação).
- **Print / interface do celular**: o app corta automaticamente faixas pretas/uniformes
  nas bordas (barras, navegação) e sugere um retângulo inicial central; o ajuste fino é
  seu, arrastando o retângulo. O app nunca adivinha "onde está a peça".
- **Quebra do título**: testa todos os pontos de quebra entre palavras e escolhe o que
  deixa as duas linhas com larguras mais parecidas. Título de uma palavra fica em 1 linha
  e o subtítulo segue a última linha.
- **Redução de fonte**: ao reduzir o título (>560 px ou sobreposição), 112 e 126
  escalam com ele; ao reduzir o subtítulo, 56 e 48 escalam com ele (escalar 56 pelo
  título faria o subtítulo bater nas descendentes do título).
- **Verificação automática** (pixels reais, não só caixas): peça opaca × textos/cartão;
  subtítulo × pílula; tudo dentro do canvas. Ordem de correção: 1) reduzir título,
  2) reduzir subtítulo, 3) reduzir a peça. Cada ajuste vira aviso na tela.
- **Dependências extras**: Flask (servidor) e pytest (testes).
- Sem salvar sessão: fechar a página zera o formulário.

## Deixado para quem constrói
Visual da página (simples e limpo), mensagens de erro, detalhes do editor de recorte.

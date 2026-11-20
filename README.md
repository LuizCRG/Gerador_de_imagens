# Gerador de Anúncio Shopee

Aplicativo local (offline, Windows) que monta a imagem principal `1024×1024` PNG para anúncios da Shopee sem alterar as fotos com IA — apenas recorte, remoção de fundo branco, ajuste de dimensões e posicionamento.

## Como abrir

1. Dê um duplo clique em **`abrir.bat`** (ou execute `python app.py` no terminal).
2. O navegador abrirá **`http://127.0.0.1:5000`**.

## Como usar

1. **Ative ou desative** cada bloco (`Carro`, `Peça`, `Título`, `Subtítulo`, `Print de aplicação` e `Etiqueta do print`). Blocos desativados não exigem envio e liberam espaço para os demais elementos.
2. Envie as fotos dos blocos ativados (arrastando ou clicando).
3. Preencha os textos e ajuste os **controles deslizantes de dimensões** (ou clique em **Restaurar padrões**).
4. Se o print estiver ativo, arraste o retângulo `350:255` (ou redimensione pelo canto inferior direito) para enquadrar a região desejada.
5. Confira a prévia ao vivo (`1024×1024`) e os avisos de ajuste automático, se houver.
6. Clique em **Baixar PNG**.

## Onde os arquivos são salvos

- Cada download salva uma cópia automática em `saida/<nome-do-titulo>.png` (ou `saida/anuncio.png` se o título estiver desativado), acrescentando `-2`, `-3`, etc. quando já existir arquivo com o mesmo nome.

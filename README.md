# Gerador de Anúncio Shopee

Aplicativo local (Windows) que monta a imagem principal `1024×1024` PNG para anúncios da Shopee (offline por padrão, com opção sob demanda de remover fundos complexos via Poof API).

## Como abrir

1. Dê um duplo clique em **`abrir.bat`** (ou execute `python app.py` no terminal).
2. O navegador abrirá **`http://127.0.0.1:5000`**.

## Como usar

1. **Ative ou desative** cada bloco (`Carro`, `Peça`, `Título`, `Subtítulo`, `Print de aplicação` e `Etiqueta do print`). Blocos desativados não exigem envio e liberam espaço para os demais elementos.
2. Envie as fotos dos blocos ativados (arrastando ou clicando).
3. *(Opcional)* Clique em **Remover fundo (IA)** abaixo de qualquer foto enviada (`Carro`, `Peça` ou `Print`) para recortar o objeto automaticamente com fundo transparente usando a Poof API. É possível alternar de volta com **Restaurar original** a qualquer momento.
4. Preencha os textos e ajuste os **controles deslizantes de dimensões** (ou clique em **Restaurar padrões**).
5. Em qualquer foto ativada (`Carro`, `Peça` ou `Print`), arraste o quadro de recorte (ou redimensione pelo canto) para centralizar/enquadrar manualmente a região desejada, ou clique em **Centralizar recorte** para voltar ao enquadramento padrão.
6. Confira a prévia ao vivo (`1024×1024`) e os avisos de ajuste automático, se houver.
7. Clique em **Baixar PNG**.

## Remoção de fundo com Poof API (opcional)

- Para usar o botão **Remover fundo (IA)**, defina `POOF_API_KEY=...` no arquivo `.env` (ignorado pelo git) na raiz do projeto ou clique em **Chave IA** no topo da tela para salvar a chave localmente.
- Quando o indicador estiver verde (**`IA: Pronta`**), você pode remover e restaurar o fundo de qualquer imagem enviada.

## Onde os arquivos são salvos

- Cada download salva uma cópia automática em `saida/<nome-do-titulo>.png` (ou `saida/anuncio.png` se o título estiver desativado), acrescentando `-2`, `-3`, etc. quando já existir arquivo com o mesmo nome.

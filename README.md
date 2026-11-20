# Gerador de Anúncio Shopee

Ferramenta local (offline) para gerar imagens principais de anúncio em **1024 × 1024 px** (PNG RGB).

## Como iniciar

### Pelo atalho (Windows)
Dê um duplo clique em `abrir.bat`. Ele abre o navegador em `http://127.0.0.1:5000` e inicia o servidor local.

### Pelo terminal
```bat
python app.py
```
Em seguida, abra `http://127.0.0.1:5000` no navegador.

## Como usar

1. Envie as **3 fotos** na coluna esquerda (arrastando e soltando ou clicando nas áreas): **Carro**, **Peça** e **Print**.
2. Preencha o **Título**, o **Subtítulo** (até 3 linhas, uma por linha) e a **Etiqueta do print**.
3. Ajuste o **Recorte do print** na proporção fixa `350:255`:
   - Arraste o interior do retângulo para mover.
   - Arraste a alça azul no canto inferior direito para redimensionar dentro da imagem.
   - Use **Centralizar recorte** caso queira voltar à seleção inicial sugerida.
4. Confira a prévia 1024 × 1024 na coluna direita e os eventuais avisos de ajuste abaixo dela.
5. Clique em **Baixar PNG** para baixar a imagem gerada.

## Onde os PNGs são salvos

Além do download pelo navegador, cada arquivo exportado é gravado automaticamente na pasta `saida/` com o nome baseado no título (por exemplo, `saida/puxador-de-porta.png`). Se já existir um arquivo com o mesmo nome, é adicionado um sufixo numérico (`-2`, `-3`, etc.) sem sobrescrever o anterior.

## Testes

```bat
python -m pytest -q
```

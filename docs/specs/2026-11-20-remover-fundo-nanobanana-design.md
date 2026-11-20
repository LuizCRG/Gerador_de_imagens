# Remoção de Fundo com Nano Banana (design)

## Intenção
Adicionar uma opção sob demanda para remover o fundo de fotos reais enviadas pelo usuário usando a API do **Nano Banana** (`gemini-nano-banana-2.1` via SDK oficial `google-genai`), isolando o objeto em fundo branco sólido para que o motor atual (`remover_fundo_branco` / `multiply`) recorte e componha o anúncio limpo.

## Metas
- Guardar a chave da API localmente em `.env` (listado no `.gitignore`, nunca versionado no git), com suporte também à variável de ambiente `GEMINI_API_KEY` e atualização opcional pela interface.
- Manter a foto original enviada em memória na sessão para que o usuário possa alternar entre **Remover fundo (IA)** e **Restaurar original** sem perder a foto original nem repetir chamadas à API à toa.
- Tratar erros de autenticação, rede, cota ou resposta sem imagem devolvendo mensagens claras em português (sem expor a chave).

## Não-metas
- Não rodar IA automaticamente no upload sem o usuário pedir.
- Não enviar fotos armazenadas na API (`store=False`).
- Não alterar `anuncio/montar.py` nem quebrar o modo 100% offline quando a opção de IA não for clicada.

## Como funciona
1. **`anuncio/ia_fundo.py`**:
   - `obter_chave_api()` lê `os.environ.get("GEMINI_API_KEY")` e, se ausente, lê `GEMINI_API_KEY` do arquivo `.env` na raiz do projeto.
   - `salvar_chave_api(chave)` grava/atualiza `GEMINI_API_KEY` no `.env` local (sem espaços, sem vazar em logs).
   - `remover_fundo_ia(img, *, tipo="peca", api_key=None, client=None) -> Image.Image`:
     - Redimensiona apenas se maior que 2048 px no maior lado (preservando proporção).
     - Envia via `client.interactions.create(model="gemini-nano-banana-2.1", input=[...], response_format={"type": "image"}, store=False)` com prompt específico para `"carro"` (preservar sombra suave de contato sob os pneus) ou `"peca"`/`"print"` (isolar em `#FFFFFF` sólido preservando furos internos e detalhes).
     - Garante borda externa conectada (`>= 245`) em branco puro `(255, 255, 255)` para `multiply` e remoção de fundo limpos.
2. **Servidor (`app.py`)**:
   - Mantém `IMAGENS_ORIGINAIS`, `IMAGENS_SEM_FUNDO` (cache por upload) e `IMAGENS` (ativa) na memória da sessão, todos limpos em `GET /` e por tipo em novo upload.
   - `POST /api/imagem/<tipo>/remover-fundo`: alterna entre removida (chamando `remover_fundo_ia` na primeira vez ou reusando cache) e original (`{"usar": false}`), devolvendo PNG em base64 + dimensões (`area`/`recorte` quando `tipo == "print"`).
   - `GET /api/config/ia` (devolve apenas `{"configurada": bool}`) e `POST /api/config/ia` (salva nova chave no `.env`).
3. **Interface (`static/`)**:
   - Botão **Remover fundo (IA)** abaixo da dropzone de cada imagem enviada, alternando para **Restaurar original** quando ativo e atualizando a miniatura e a prévia ao vivo.
   - Indicador discreto do status da chave Nano Banana no cabeçalho com opção de atualizar a chave se necessário.

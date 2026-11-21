# Remoção de Fundo com Poof API (design)

## Intenção
Substituir a integração anterior do Nano Banana (bloqueada pela cota zero no nível gratuito do Google AI Studio) pela **Poof API** (`POST https://api.poof.bg/v1/remove`), permitindo remover o fundo das imagens enviadas sob demanda usando o plano gratuito mensal da Poof (100 créditos/mês sem cartão, saída PNG em resolução completa).

## Abordagens consideradas
1. **Substituir direto pela Poof API (escolhida):** troca o motor em `anuncio/ia_fundo.py` para chamar a Poof API via `requests` com uma única chave `POOF_API_KEY` no `.env` e no painel **Chave IA**, mantendo interface, cache e rotas idênticos. Mais simples para o usuário e sem dependências pesadas.
2. **Manter Poof + Nano Banana selecionáveis:** exigiria seletor de provedor na interface, duas variáveis de chave e manutenção paralela de duas integrações sem necessidade no uso atual. Descartada.

## Metas, Não-metas e Anti-metas
- **Metas:**
  - Ler e salvar `POOF_API_KEY` localmente em `.env` (ignorado pelo git) ou via variável de ambiente, sem expor a chave no HTML/JS/respostas da API.
  - Preservar a foto original em memória para alternar entre **Remover fundo (IA)** e **Restaurar original** com cache por upload.
  - Preservar transparência `RGBA` retornada pela Poof API (zerando cores residuais onde `alpha == 0` para branco transparente `(255, 255, 255, 0)`), garantindo compatibilidade limpa com `carro`, `peca` e `print`.
  - Traduzir erros da Poof (`400` entrada inválida, `401`/`403` chave inválida, `402` créditos esgotados, `429` limite por minuto, timeout e rede) em mensagens claras em português.
- **Não-metas:** não rodar remoção automática no upload sem clique do usuário; não criar seletor múltiplo de provedores.
- **Anti-metas:** nunca incluir URLs externas (`http://`/`https://`) em `static/` (mantendo compatibilidade offline e o teste `test_ativos_estaticos_e_offline`); nunca deixar requisições HTTP sem timeout.

## Como funciona e o que muda
1. **`anuncio/ia_fundo.py` e `requirements.txt`**:
   - Troca `google-genai` por `requests>=2.31.0` (`2.34.2` já instalada).
   - `_NOME_CHAVE = "POOF_API_KEY"`, `ENDPOINT_POOF_API = "https://api.poof.bg/v1/remove"`, timeout de `60` segundos (`_TIMEOUT_REQUISICAO_SEG = 60`).
   - `remover_fundo_ia(img, *, tipo="peca", api_key=None, env_path=..., http_post=None) -> Image.Image`: redimensiona se maior que 2048 px no maior lado, envia PNG via `multipart/form-data` (`files={"file": ("imagem.png", img_bytes, "image/png")}`) com header `{"x-api-key": chave}`, valida resposta HTTP 200 e normaliza saída `RGBA` (limpando RGB residual de pixels 100% transparentes).
2. **`app.py`**:
   - Mantém exatamente as mesmas rotas (`/api/imagem/<tipo>/remover-fundo`, `/api/config/ia`), cache `IMAGENS_SEM_FUNDO` e `IMAGENS_ORIGINAIS`.
3. **Interface (`static/index.html`, `static/app.js`) e `README.md`**:
   - Atualiza os textos visíveis de `Nano Banana` / `GEMINI_API_KEY` para `Poof API` / `POOF_API_KEY` (sem adicionar URLs externas nos arquivos estáticos).
   - Quando o backend acusar chave Poof inválida/ausente, abre automaticamente o painel **Chave IA** para o usuário informar a chave.

## Próximo passo após aprovação
Criar o plano de execução (`writing-plans`), atualizar testes em TDD (`tests/test_ia_fundo.py`, `tests/test_app.py`), implementar a troca, verificar suíte completa + browser E2E e gravar em commit.

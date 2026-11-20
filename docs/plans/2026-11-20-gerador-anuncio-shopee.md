# Gerador de Anúncio Shopee – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** App local (Flask + página HTML) que monta a imagem principal 1024×1024 do anúncio Shopee a partir de 3 fotos + textos, seguindo a especificação de layout.

**Architecture:** Pacote `anuncio/` com o motor puro em Pillow/numpy/scipy (fundo, peça+glow, carro, textos, cartão, montagem com verificação/autocorreção). `app.py` expõe o motor via Flask em 127.0.0.1:5000 e guarda em memória as últimas imagens enviadas (uso de uma pessoa só). `static/` tem a página com upload, editor de recorte 350:255 e prévia ao vivo.

**Tech Stack:** Python 3.15, Pillow 13, numpy 2.5, scipy 1.18, Flask, pytest. JS puro, sem build.

**Spec:** `docs/specs/2026-11-20-gerador-anuncio-shopee-design.md`

## Global Constraints
- Canvas 1024×1024, saída PNG RGB.
- Fontes: `Inter/static/Inter_18pt-Black.ttf` (título) e `Inter/static/Inter_18pt-ExtraBold.ttf` (subtítulo, etiqueta), caminhos relativos à raiz do projeto.
- Nenhuma alteração do conteúdo das fotos além de recorte, redimensionamento (LANCZOS) e máscara de fundo branco.
- Todos os valores numéricos do layout ficam em `anuncio/layout.py` (uma constante por valor da especificação).
- Funciona offline; servidor escuta só em 127.0.0.1.
- Escalonamento ao reduzir fontes: 112 e 126 escalam com o tamanho do título (s = t/132); 56 e 48 escalam com o tamanho do subtítulo (s = t/40). *(Ajuste à spec: escalar 56 pelo título faria o subtítulo bater nas descendentes do título.)*
- Comandos: `python -m pytest -q` a partir da raiz.

## Review Focus
1. Foto de celular com rotação EXIF / modo CMYK / paleta → toda imagem entra por `abrir_imagem()` (exif_transpose + convert). Teste na Task 2.
2. Peça já em PNG transparente → manter o alfa original, não aplicar máscara de luminosidade. Teste na Task 2.
3. Carro em PNG transparente → compor sobre branco antes do multiply. Teste na Task 3.
4. Título com acentos ou palavra única muito longa → reduzir até 560 px, 1 linha se for uma palavra. Teste na Task 5.
5. Retângulo de recorte vindo do navegador fora da imagem ou fora da proporção → `normalizar_recorte()` corrige no servidor. Teste na Task 4.

---

### Task 1: Base do projeto + fundo radial

**Files:**
- Create: `requirements.txt`, `.gitignore`, `anuncio/__init__.py`, `anuncio/layout.py`, `anuncio/imagens.py`, `tests/conftest.py`, `tests/test_fundo.py`

**Interfaces:**
- Produces: `layout.py` constantes (`CANVAS=1024`, `FUNDO_CENTRO=(760,480)`, `FUNDO_RAIO=700`, `FUNDO_COR_CENTRO=(255,255,255)`, `FUNDO_COR_BORDA=(228,234,243)`, `CAIXA_PECA=(420,12,1000,1012)`, `GLOW=[((30,140,255),41,50,0.55),((70,190,255),15,22,0.40),((190,230,255),5,8,0.45)]`, `CARRO_POS=(24,8)`, `CARRO_LARG=500`, `CARRO_ALT_MAX=275`, `CARRO_MARGEM=15`, `TITULO_X=36`, `TITULO_TAM=132`, `TITULO_COR=(8,8,8)`, `TITULO_DESLOC=112`, `TITULO_ENTRELINHA=126`, `TITULO_LARG_MAX=560`, `SUB_X=40`, `SUB_TAM=40`, `SUB_COR=(52,52,52)`, `SUB_DESLOC=56`, `SUB_ENTRELINHA=48`, `PRINT_TAM=(350,255)`, `PRINT_RAIO=26`, `CARTAO_BORDA=8`, `CARTAO_RAIO=30`, `CARTAO_POS=(40,712)`, `SOMBRA_OPAC=0.43`, `SOMBRA_BLUR=14`, `SOMBRA_DY=12`, `ETIQ_COR=(22,119,255)`, `ETIQ_CONTORNO=4`, `ETIQ_TAM=24`, `ETIQ_ALT=46`, `ETIQ_PAD=44`, `ETIQ_POS=(62,689)`, `FONTE_BLACK`, `FONTE_EXTRABOLD`)
- Produces: `imagens.fundo_radial() -> Image.Image` (RGB 1024²)
- Produces: fixtures em `conftest.py`: `img_carro` (branco 900×600, carro cinza escuro retângulo arredondado 200..700 × 150..420 + sombra cinza clara 180..720 × 420..450), `img_peca` (branco 400×900: barra vertical preta x 250..350 × y 20..880, pé horizontal preto x 50..350 × y 750..880, furo branco circular r=20 em (300,450); constantes `PONTO_PRETO=(270,200)`, `CENTRO_FURO=(300,450)`. Depois de encaixada fica em x≈535..884, longe do título/subtítulo/cartão), `img_print` (720×1600: barra preta 0..120 no topo, foto texturizada colorida 120..1400, barra de navegação cinza uniforme (40,40,40) 1400..1600)

- [ ] **Step 1:** `git init`; `requirements.txt` (pillow, numpy, scipy, flask, pytest); `.gitignore` (`__pycache__/`, `saida/`, `.pytest_cache/`).
- [ ] **Step 2: Failing test** `tests/test_fundo.py`
```python
def test_fundo_centro_branco():  assert fundo_radial().getpixel((760,480)) == (255,255,255)
def test_fundo_borda():          assert fundo_radial().getpixel((0,1023)) == (228,234,243)  # dist 934 > 700
def test_fundo_meio():           # (410,480) está a 350 px → metade do caminho
    p = fundo_radial().getpixel((410,480)); assert all(abs(a-b) <= 1 for a,b in zip(p,(241.5,244.5,249)))
def test_fundo_tamanho():        im = fundo_radial(); assert im.size == (1024,1024) and im.mode == "RGB"
```
- [ ] **Step 3:** Run `python -m pytest tests/test_fundo.py -q` → FAIL (import).
- [ ] **Step 4:** Implementar `fundo_radial()` com numpy: `t = clip(dist/700, 0, 1)`, cor = centro + (borda−centro)·t, arredondar.
- [ ] **Step 5:** Run → PASS. Commit `feat: base do projeto e fundo radial`.

### Task 2: Peça – abrir, remover fundo branco, encaixar, glow

**Files:** Modify `anuncio/imagens.py`; Test `tests/test_peca.py`

**Interfaces:**
- Produces: `abrir_imagem(dados: bytes | str | Path) -> Image.Image` (exif_transpose; RGBA se tiver alfa/transparência, senão RGB)
- Produces: `remover_fundo_branco(img: Image.Image) -> Image.Image` RGBA. Se a imagem tiver alfa com algum valor < 250, devolve como está (RGBA). Senão: luminância L; `alfa = clip((247 − L) / (247 − 215), 0, 1)`; suaviza o alfa com GaussianBlur(0.6); descontamina cor nas bordas: `c = (c − 255·(1−a)) / a` para a > 0.
- Produces: `encaixar_peca(peca: Image.Image, escala: float = 1.0) -> tuple[Image.Image, tuple[int,int]]` — recorta ao bbox do alfa, redimensiona proporcional para caber em `CAIXA_PECA` × escala, centralizado na caixa; devolve imagem e posição.
- Produces: `compor_peca(canvas: Image.Image, peca: Image.Image, pos: tuple[int,int]) -> None` — para cada camada de `GLOW`: alfa da peça no canvas → `scipy.ndimage.maximum_filter(size=dilat)` → `GaussianBlur(blur)` → × opacidade → cor composta no canvas; depois a peça por cima (alpha_composite). Canvas RGBA.

- [ ] **Step 1: Failing tests**
```python
def test_branco_vira_transparente(img_peca):  r = remover_fundo_branco(img_peca); assert r.getpixel((5,5))[3] == 0
def test_preto_fica_opaco(img_peca):          # ponto dentro do "L"
    assert remover_fundo_branco(img_peca).getpixel(PONTO_PRETO)[3] == 255
def test_furo_transparente(img_peca):         assert remover_fundo_branco(img_peca).getpixel(CENTRO_FURO)[3] == 0
def test_borda_suave(img_peca):               a = np.array(remover_fundo_branco(img_peca))[...,3]; assert ((a>0)&(a<255)).sum() > 0
def test_png_transparente_preservado():       # RGBA 100×100 alfa 0 com quadrado branco opaco no meio
    r = remover_fundo_branco(im); assert r.getpixel((50,50)) == (255,255,255,255)
def test_encaixar_alta(img_peca):             p,(x,y) = encaixar_peca(remover_fundo_branco(img_peca)); assert p.height == 1000 and y == 12 and 420 <= x and x+p.width <= 1000
def test_encaixar_larga():                    # peça 1200×200 preta → largura 580, centralizada em y
    assert p.width == 580 and x == 420 and abs((y + p.height/2) - 512) <= 1
def test_encaixar_escala(img_peca):           p,_ = encaixar_peca(rgba, escala=0.9); assert p.height == 900
def test_glow_azul_perto_da_peca(img_peca):   # pixel 10 px fora da borda esquerda da peça: B > R + 15
def test_glow_some_longe(img_peca):           # pixel em (100,100) igual ao fundo
def test_exif_rotacao(tmp_path):              # JPEG 100×50 com EXIF Orientation=6 → abrir_imagem → size == (50,100)
def test_cmyk_vira_rgb(tmp_path):             assert abrir_imagem(caminho_cmyk).mode == "RGB"
```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS. **Step 5:** Commit `feat: peça com fundo removido e glow`.

### Task 3: Carro – recorte e multiply

**Files:** Modify `anuncio/imagens.py`; Test `tests/test_carro.py`

**Interfaces:**
- Produces: `recortar_carro(img: Image.Image) -> Image.Image` RGB. Se RGBA, compõe sobre branco antes. bbox dos pixels com min(R,G,B) < 245, margem `CARRO_MARGEM` (limitada à imagem); redimensiona para largura 500, ou altura 275 se passar.
- Produces: `aplicar_multiply(canvas: Image.Image, img: Image.Image, pos: tuple[int,int]) -> tuple[int,int,int,int]` — ImageChops.multiply na região; devolve a caixa ocupada (x0,y0,x1,y1). `y1` = base do carro usada pelo título.

- [ ] **Step 1: Failing tests**
```python
def test_recorte_largura(img_carro):   assert recortar_carro(img_carro).width == 500
def test_recorte_margem(img_carro):    # bbox não-branco 180..720 × 150..450 → +15 → 570×330 → 500×289 → altura > 275 → limita: 275 de altura
    c = recortar_carro(img_carro); assert c.height == 275 and c.width == round(570*275/330)
def test_carro_largo():                # carro 1000×100 → 500 de largura, altura < 275
def test_carro_png_transparente():     # RGBA com fundo alfa 0 → não vira preto; canto == (255,255,255)
def test_multiply_branco_some(img_carro):
    cv = fundo_radial(); caixa = aplicar_multiply(cv, recortar_carro(img_carro), (24,8)); assert cv.getpixel((26,10)) == fundo_radial().getpixel((26,10))
def test_multiply_escuro_fica(img_carro):  # centro do carro no canvas continua escuro (< 80)
def test_multiply_caixa(img_carro):    assert caixa == (24, 8, 24+c.width, 8+c.height)
```
- [ ] Steps 2–5 como na Task 2. Commit `feat: carro com multiply`.

### Task 4: Print – área da foto, recorte, cartão e etiqueta

**Files:** Create `anuncio/cartao.py`; Test `tests/test_cartao.py`

**Interfaces:**
- Produces: `detectar_area_foto(img) -> tuple[int,int,int,int]` — remove, a partir de cada borda, linhas/colunas com média de cinza < 25 ou desvio padrão < 6.
- Produces: `normalizar_recorte(recorte: tuple|None, img_size: tuple[int,int], area: tuple) -> tuple[int,int,int,int]` — `None` → maior retângulo 350:255 centralizado em `area`; senão corrige a proporção para 350:255 mantendo o centro e a largura (reduz se não couber), e desloca para dentro da imagem.
- Produces: `desenhar_cartao(canvas: Image.Image, img_print: Image.Image, recorte: tuple) -> tuple[int,int,int,int]` — recorta, redimensiona para 350×255, máscara arredondada raio 26; cartão branco 366×271 raio 30 em `CARTAO_POS`, foto em +8; sombra preta (alfa 0.43·255) com blur 14 deslocada +12 em y, desenhada antes. Devolve caixa do cartão `(40,712,406,983)`.
- Produces: `desenhar_etiqueta(canvas, texto: str) -> tuple[int,int,int,int]` — texto em MAIÚSCULAS, ExtraBold 24; largura = texto + 44, altura 46, raio 23, fundo (22,119,255), contorno branco 4, texto branco centrado (anchor "mm"), em (62,689). Devolve a caixa.

- [ ] **Step 1: Failing tests**
```python
def test_area_sem_barras(img_print):    l,t,r,b = detectar_area_foto(img_print); assert t >= 120 and b <= 1400 and l == 0 and r == 720
def test_recorte_inicial_proporcao(img_print):  l,t,r,b = normalizar_recorte(None, img_print.size, area); assert abs((r-l)/(b-t) - 350/255) < 0.01 and t >= 120 and b <= 1400
def test_recorte_fora_da_imagem():      assert normalizar_recorte((-50,-50,300,300),(720,1600),(0,0,720,1600))[0] >= 0
def test_recorte_proporcao_corrigida(): l,t,r,b = normalizar_recorte((0,0,350,400),(720,1600),(0,0,720,1600)); assert abs((r-l)/(b-t)-350/255) < 0.01
def test_cartao_borda_branca(...):      assert cv.getpixel((44, 847))[:3] == (255,255,255)
def test_cartao_foto(...):              # (48+175, 720+127) tem a cor da foto, não branco
def test_cartao_canto_arredondado(...): # (41,713) ≈ fundo (diferença < 12 por canal)
def test_cartao_sombra(...):            # (220, 990) mais escuro que fundo_radial() no mesmo ponto
def test_etiqueta_azul(...):            assert cv.getpixel((74, 712))[:3] == (22,119,255)
def test_etiqueta_contorno(...):        x0,y0,x1,y1 = desenhar_etiqueta(cv,"aplicação na porta"); assert cv.getpixel(((x0+x1)//2, y0+1))[:3] == (255,255,255) and y1-y0 == 46
```
- [ ] Steps 2–5. Commit `feat: cartão do print e etiqueta`.

### Task 5: Textos – quebra, tamanhos e posições

**Files:** Create `anuncio/textos.py`; Test `tests/test_textos.py`

**Interfaces:**
- Produces: `quebrar_titulo(titulo: str, fonte: ImageFont.FreeTypeFont) -> list[str]` — 1 palavra → `[titulo]`; senão testa cada ponto de quebra e escolhe o de menor largura máxima (desempate: menor diferença).
- Produces: `@dataclass Textos: linhas_titulo: list[str]; baselines_titulo: list[int]; tam_titulo: int; linhas_sub: list[str]; baselines_sub: list[int]; tam_sub: int`
- Produces: `posicionar_textos(base_carro: int, titulo: str, subtitulo: list[str], tam_titulo: int = 132, tam_sub: int = 40) -> Textos` — subtítulo: remove linhas vazias, MAIÚSCULAS, `ValueError("Subtítulo tem mais de 3 linhas")` se > 3; título reduzido de 2 em 2 px enquanto a linha mais larga > 560; baselines conforme Global Constraints.
- Produces: `desenhar_textos(canvas, t: Textos) -> None` e `mascara_textos(t: Textos) -> tuple[np.ndarray, np.ndarray]` (máscaras bool 1024² da tinta do título e do subtítulo, para verificação).

- [ ] **Step 1: Failing tests**
```python
def test_quebra_equilibrada():   assert quebrar_titulo("Puxador de Porta", f132) == ["Puxador", "de Porta"]
def test_uma_palavra():          assert quebrar_titulo("Retrovisor", f132) == ["Retrovisor"]
def test_baselines_padrao():     t = posicionar_textos(283, "Puxador de Porta", ["compatível com","new fiesta sedan","2011 a 2017"])
                                 assert t.baselines_titulo == [395, 521] and t.baselines_sub == [577, 625, 673] and t.linhas_sub[0] == "COMPATÍVEL COM"
def test_titulo_longo_reduz():   t = posicionar_textos(283, "Maçaneta Interna Dianteira Esquerda", []); assert t.tam_titulo < 132 and max(f(t.tam_titulo).getlength(l) for l in t.linhas_titulo) <= 560
def test_palavra_longa_reduz():  t = posicionar_textos(283, "Retrovisor-Elétrico-Completo", []); assert len(t.linhas_titulo) == 1 and largura <= 560
def test_quatro_linhas_erro():   with pytest.raises(ValueError): posicionar_textos(283, "X Y", ["a","b","c","d"])
def test_linhas_vazias_ignoradas(): assert len(posicionar_textos(283,"X Y",["a","","b"]).linhas_sub) == 2
```
- [ ] Steps 2–5. Commit `feat: layout dos textos`.

### Task 6: Montagem com verificação e autocorreção

**Files:** Create `anuncio/montar.py`; Test `tests/test_montar.py`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces:
```python
@dataclass
class Entrada:
    carro: Image.Image; peca: Image.Image; print_img: Image.Image
    titulo: str; subtitulo: list[str]; etiqueta: str
    recorte_print: tuple[int,int,int,int] | None = None
@dataclass
class Resultado:
    imagem: Image.Image; avisos: list[str]; tam_titulo: int; tam_sub: int; escala_peca: float; recorte_print: tuple
def verificar(mascara_peca, m_titulo, m_sub, caixa_carro_tinta, caixa_cartao, caixa_etiqueta) -> list[str]  # códigos: "titulo_x_peca","sub_x_peca","sub_x_etiqueta","carro_x_peca","cartao_x_peca","fora_do_canvas"
def montar(e: Entrada) -> Resultado
```
- Regras: máscara da peça = alfa > 32 dilatado 6 px; "carro_x_peca" usa pixels não brancos do carro; "sub_x_etiqueta" = última linha do subtítulo (tinta) abaixo de `ETIQ_POS[1] − 6`. Correção em laço (máx. 80 iterações): título×peça → título −2 (mín. 72); sub×peca ou sub×etiqueta → primeiro título −2 (se > 72), depois subtítulo −2 (mín. 26); carro/cartão×peça ou mínimos atingidos → escala da peça −0.03 (mín. 0.5). A peça processada (`remover_fundo_branco`) é calculada uma vez; glow só é recomposto quando a escala muda. Cada ajuste final vira aviso em português, ex.: `"Título reduzido de 132 para 118 px"`, `"Peça reduzida para 91%"`. Se ainda houver problema após o laço: aviso `"Não foi possível eliminar: <código>"`.
- Ordem de composição: fundo → glow+peça → carro (multiply) → textos → cartão → etiqueta. Saída convertida para RGB.

- [ ] **Step 1: Failing tests**
```python
def test_montar_padrao(fixtures):      r = montar(Entrada(...,"Puxador de Porta",["compatível com","new fiesta sedan","2011 a 2017"],"aplicação na porta"))
                                       assert r.imagem.size == (1024,1024) and r.imagem.mode == "RGB" and r.avisos == [] and r.tam_titulo == 132
def test_peca_larga_corrigida():       # peça 1200×700 (ocupa x 420..1000) → sem sobreposição no fim
                                       assert any("reduzid" in a for a in r.avisos) and not any("Não foi possível" in a for a in r.avisos)
def test_subtitulo_longo_corrigido():  # linha "COMPATÍVEL COM TODAS AS VERSÕES" → sem "Não foi possível"
def test_verificar_detecta():          # máscaras sintéticas sobrepostas → "titulo_x_peca" in verificar(...)
def test_recorte_devolvido(fixtures):  assert abs((r.recorte_print[2]-r.recorte_print[0])/(r.recorte_print[3]-r.recorte_print[1]) - 350/255) < 0.01
```
- [ ] Steps 2–5. **Step 6:** salvar `saida/teste_fixtures.png` via script curto e abrir/inspecionar visualmente. Commit `feat: montagem com verificação`.

### Task 7: Servidor Flask

**Files:** Create `app.py`; Test `tests/test_app.py`

**Interfaces:**
- Consumes: `abrir_imagem`, `detectar_area_foto`, `normalizar_recorte`, `montar`, `Entrada`.
- Produces: `criar_app(pasta_saida: Path = Path("saida")) -> Flask`. Estado em memória `app.config["IMAGENS"]: dict[str, Image]`.
  - `GET /` → `static/index.html`
  - `POST /api/imagem/<tipo>` (`carro|peca|print`, campo `arquivo`) → `{"largura","altura"}`; para `print` também `{"area": [...], "recorte": [...]}`. Tipo inválido → 404; arquivo ilegível → 400 `{"erro"}`.
  - `POST /api/previa` JSON `{titulo, subtitulo: [..], etiqueta, recorte_print: [..]|null}` → `{"png": base64, "avisos": [...], "recorte_print": [...]}`; imagem faltando → 400 `{"erro": "Envie a foto do carro"}` (etc.); ValueError → 400.
  - `POST /api/salvar` mesmo JSON → grava `saida/<slug-do-titulo>.png` (sem acentos, minúsculas, hífens; sufixo `-2`, `-3` se existir) e devolve o arquivo (`send_file`, `as_attachment=True`).
  - `if __name__ == "__main__"`: `criar_app().run(host="127.0.0.1", port=5000)`.

- [ ] **Step 1: Failing tests** (Flask test client, `tmp_path` como pasta de saída)
```python
def test_upload_print_devolve_recorte(): assert set(r.json) >= {"largura","altura","area","recorte"}
def test_tipo_invalido():               assert client.post("/api/imagem/xyz", ...).status_code == 404
def test_arquivo_invalido():            assert client.post("/api/imagem/carro", data={"arquivo": (BytesIO(b"lixo"),"a.png")}).status_code == 400
def test_previa_sem_imagens():          assert r.status_code == 400 and "carro" in r.json["erro"]
def test_previa_ok():                   png = base64.b64decode(r.json["png"]); assert Image.open(BytesIO(png)).size == (1024,1024)
def test_salvar_grava_arquivo(tmp_path): assert (tmp_path/"puxador-de-porta.png").exists() and r.mimetype == "image/png"
def test_salvar_nao_sobrescreve(tmp_path): # duas vezes → existe "puxador-de-porta-2.png"
```
- [ ] Steps 2–5. Commit `feat: servidor Flask`.

### Task 8: Página, editor de recorte e atalho

**Files:** Create `static/index.html`, `static/app.js`, `static/style.css`, `abrir.bat`, `README.md`

**Interfaces:**
- Consumes: endpoints da Task 7.
- Página: coluna esquerda com 3 áreas de arrastar/clicar (carro, peça, print, com miniatura), campos Título, Subtítulo (textarea, até 3 linhas), Etiqueta; editor de recorte (canvas com o print em escala; retângulo travado em 350:255, arrastar para mover, alça no canto inferior direito para redimensionar, limitado à imagem; coordenadas convertidas para o tamanho original); coluna direita com prévia 1024 (exibida a 512–640 px), lista de avisos e botão "Baixar PNG". Prévia pedida 350 ms após a última mudança; erros do servidor exibidos acima da prévia.
- `abrir.bat`: `cd /d "%~dp0"`, `start "" http://127.0.0.1:5000`, `python app.py`.
- `README.md`: como abrir, onde os PNGs são salvos.

- [ ] **Step 1:** Criar arquivos. **Step 2:** `python -m pytest -q` → tudo PASS.
- [ ] **Step 3: Verificação no navegador** (subagente browser): abrir http://127.0.0.1:5000, enviar as 3 fixtures salvas em PNG, digitar textos de exemplo, mover o retângulo, confirmar prévia atualizada, avisos vazios e download. Esperado: imagem 1024 com layout da referência.
- [ ] **Step 4:** Commit `feat: interface web e atalho`.

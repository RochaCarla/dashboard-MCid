# Skill: UI Institucional — Dashboard UnB / Ministério das Cidades

## Quando usar esta skill
Invoke when the user wants to **make the dashboard more institutional**, add the UnB logo, apply official branding, or improve the visual identity of the GitHub Pages dashboard.

Trigger phrases (PT): "melhorar interface", "institucionalizar", "colocar logo UnB", "página institucional", "identidade visual", "branding oficial"

---

## O que esta skill entrega
1. Header institucional com logos (UnB + Ministério das Cidades)
2. Paleta de cores oficial da UnB (azul #003366, verde institucional)
3. Footer com créditos, links institucionais e selo de atualização
4. Tipografia institucional (Inter / Roboto)
5. Favicon com brasão UnB
6. Layout responsivo aprimorado

---

## Protocolo de execução

### PASSO 1 — Coletar informações
Pergunte (use AskUserQuestion):
- **Logos**: Usar logo UnB + Ministério das Cidades? Outros parceiros?
- **Texto do footer**: Nome do laboratório/grupo de pesquisa responsável?
- **Paleta preferida**: UnB padrão (azul #003366) ou manter teal/navy atual?
- **Parceiros adicionais**: SENAI, CBIC, BNDES, etc.?

### PASSO 2 — Adicionar assets de logo

Criar pasta `assets/` com:
```
assets/
  logo-unb.svg       — Brasão/logotipo da UnB
  logo-mcid.svg      — Logo Ministério das Cidades
  favicon.ico        — Favicon institucional
```

**Logo UnB (SVG inline sugerido):**
Usar o brasão oficial disponível em https://marca.unb.br ou SVG simplificado com as iniciais "UnB" em fonte serif bold sobre fundo azul #003366.

**Se não houver SVG disponível, usar texto estilizado:**
```html
<div class="logo-unb">
  <div class="logo-mark">UnB</div>
  <div class="logo-text">Universidade de Brasília</div>
</div>
```

### PASSO 3 — Reestruturar o Header

Substituir o header atual por versão institucional com 3 zonas:

```html
<!-- HEADER INSTITUCIONAL -->
<div class="hdr-inst">
  <!-- Barra superior (logos) -->
  <div class="hdr-top">
    <div class="hdr-top-inner">
      <div class="logos-left">
        <img src="assets/logo-unb.svg" alt="UnB" class="logo" height="44">
        <div class="logo-sep"></div>
        <img src="assets/logo-mcid.svg" alt="MCid" class="logo" height="36">
      </div>
      <div class="hdr-top-right">
        <span class="badge"><span class="dot"></span><span id="hdrDate">–</span></span>
      </div>
    </div>
  </div>
  <!-- Barra de título -->
  <div class="hdr-title-bar">
    <div class="hdr-title-inner">
      <div>
        <h1 id="hdrTitle">Painel de Gestão — GT Cidades Inteligentes</h1>
        <div class="sub" id="hdrSub">Universidade de Brasília · Ministério das Cidades</div>
      </div>
      <div class="hdr-btns">
        <button class="btn-h" onclick="expandAll()">⊞ Expandir</button>
        <button class="btn-h" onclick="collapseAll()">⊟ Recolher</button>
        <button class="btn-h gold" onclick="exportCSV()">↓ Exportar</button>
      </div>
    </div>
  </div>
</div>
```

### PASSO 4 — Atualizar paleta de cores

Substituir variáveis CSS `:root` pela paleta institucional UnB:

```css
:root {
  /* UnB Institucional */
  --navy: #003366;          /* Azul UnB principal */
  --navy-l: #004080;        /* Azul UnB claro */
  --teal: #006633;          /* Verde institucional */
  --teal-l: #008844;        /* Verde claro */
  --teal-bg: #E6F2E6;
  --gold: #C4A035;          /* Dourado UnB */
  --gold-d: #A88A2A;
  --accent: #003366;        /* Cor de destaque */

  /* Backgrounds e textos */
  --bg: #F7F8FA;
  --card: #FFFFFF;
  --border: #E0E4EA;
  --text: #1A2A3A;
  --text-l: #5A6B7A;
  --text-m: #8A9AAA;

  /* Status (manter) */
  --ok: #2ECC71; --ok-bg: #E8FAF0;
  --warn: #F39C12; --warn-bg: #FFF8E7;
  --err: #E74C3C; --err-bg: #FDE8E8;
  --info: #3498DB; --info-bg: #E8F4FD;
}
```

### PASSO 5 — Adicionar Footer institucional

```html
<footer class="footer-inst">
  <div class="footer-inner">
    <div class="footer-col">
      <div class="footer-brand">
        <img src="assets/logo-unb.svg" alt="UnB" height="32">
        <span>Universidade de Brasília</span>
      </div>
      <p class="footer-desc">
        Dashboard desenvolvido pelo [Nome do Lab/Grupo] em parceria com o
        Ministério das Cidades para acompanhamento das ações do GT Cidades Inteligentes.
      </p>
    </div>
    <div class="footer-col">
      <h4>Links</h4>
      <ul>
        <li><a href="https://www.unb.br" target="_blank">UnB</a></li>
        <li><a href="https://www.gov.br/cidades" target="_blank">Ministério das Cidades</a></li>
      </ul>
    </div>
    <div class="footer-col">
      <h4>Contato</h4>
      <p>email@unb.br</p>
      <p>Brasília - DF</p>
    </div>
  </div>
  <div class="footer-bottom">
    <span>© 2025 Universidade de Brasília. Todos os direitos reservados.</span>
  </div>
</footer>
```

### PASSO 6 — CSS do Footer

```css
.footer-inst {
  background: var(--navy);
  color: rgba(255,255,255,.85);
  padding: 40px 40px 0;
  margin-top: 60px;
}
.footer-inner {
  max-width: 1440px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 40px;
  padding-bottom: 30px;
  border-bottom: 1px solid rgba(255,255,255,.1);
}
.footer-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 12px;
}
.footer-desc {
  font-size: 12px;
  color: rgba(255,255,255,.6);
  line-height: 1.6;
}
.footer-col h4 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .5px;
  color: var(--gold);
  margin-bottom: 12px;
}
.footer-col ul {
  list-style: none;
}
.footer-col ul li {
  margin-bottom: 8px;
}
.footer-col ul li a {
  color: rgba(255,255,255,.7);
  text-decoration: none;
  font-size: 12px;
  transition: color .2s;
}
.footer-col ul li a:hover {
  color: #fff;
}
.footer-col p {
  font-size: 12px;
  color: rgba(255,255,255,.6);
  margin-bottom: 4px;
}
.footer-bottom {
  padding: 16px 0;
  text-align: center;
  font-size: 11px;
  color: rgba(255,255,255,.4);
}

@media(max-width:768px) {
  .footer-inner {
    grid-template-columns: 1fr;
    gap: 24px;
  }
}
```

### PASSO 7 — Atualizar Header CSS

```css
/* Header institucional */
.hdr-inst {
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 4px 20px rgba(0,51,102,.2);
}
.hdr-top {
  background: #fff;
  border-bottom: 1px solid var(--border);
  padding: 10px 40px;
}
.hdr-top-inner {
  max-width: 1440px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.logos-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.logo-sep {
  width: 1px;
  height: 30px;
  background: var(--border);
}
.hdr-title-bar {
  background: linear-gradient(135deg, var(--navy), var(--navy-l) 60%, var(--teal));
  padding: 16px 40px;
}
.hdr-title-inner {
  max-width: 1440px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 14px;
}
.hdr-title-inner h1 {
  font-family: 'Inter', sans-serif;
  font-size: 18px;
  color: #fff;
  font-weight: 700;
}
.hdr-title-inner .sub {
  font-size: 12px;
  color: rgba(255,255,255,.7);
  margin-top: 2px;
}
```

### PASSO 8 — Trocar fonte para Inter (mais institucional)

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

```css
body {
  font-family: 'Inter', sans-serif;
}
```

### PASSO 9 — Adicionar favicon

```html
<link rel="icon" href="assets/favicon.ico" type="image/x-icon">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
```

---

## Personalização

### Trocar logos por SVG inline (sem dependência de arquivo externo)
Se não quiser criar arquivos SVG separados, usar texto estilizado:
```css
.logo-mark {
  font-family: 'Playfair Display', serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--navy);
}
```

### Adicionar banner/hero acima dos KPIs
```html
<div class="hero-banner">
  <h2>Acompanhamento de Ações</h2>
  <p>GT Cidades Inteligentes — Plano de trabalho 2025</p>
</div>
```

### Modo escuro institucional
Adicionar toggle no header que aplica classe `.dark` no `<body>` com variáveis invertidas.

---

## Verificação final
- [ ] Logos exibindo corretamente (fallback se SVG falhar)
- [ ] Header sticky funcional com duas barras
- [ ] Footer com links corretos
- [ ] Paleta UnB aplicada consistentemente
- [ ] Responsivo em mobile (logos empilham, footer 1 coluna)
- [ ] Favicon aparecendo na aba do browser
- [ ] Contraste WCAG AA em todos os textos

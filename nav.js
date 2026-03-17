// Shared navigation — injected into all pages
const NAV_HTML = `
<nav id="site-nav">
  <div class="nav-inner">
    <div class="nav-brand">
      <span class="nav-dot"></span>
      <span class="nav-logo">BÜRKERT</span>
      <span class="nav-sub">· STRATEGIC ANALYSIS 2026</span>
    </div>
    <div class="nav-links">
      <a href="index.html"     class="nav-link" data-page="macro">宏观脉搏</a>
      <a href="liquid.html"    class="nav-link" data-page="liquid">AI 液冷</a>
      <a href="semiconductor.html" class="nav-link" data-page="semi">半导体 SBU</a>
    </div>
    <div class="nav-status">
      <span class="status-dot"></span>
      <span class="status-txt">LIVE 2026</span>
    </div>
  </div>
  <div class="nav-progress"></div>
</nav>
`;

const NAV_CSS = `
#site-nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
  background: rgba(2,5,18,0.88);
  backdrop-filter: blur(24px) saturate(160%);
  -webkit-backdrop-filter: blur(24px) saturate(160%);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.nav-inner {
  max-width: 1280px; margin: 0 auto;
  display: flex; align-items: center; gap: 24px;
  padding: 0 clamp(16px,4vw,40px); height: 52px;
}
.nav-brand {
  display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}
.nav-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #E30613;
  box-shadow: 0 0 8px #E30613;
  animation: navBlink 2.4s ease-in-out infinite;
}
@keyframes navBlink { 0%,100%{opacity:1} 50%{opacity:.25} }
.nav-logo {
  font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700;
  color: #fff; letter-spacing: .22em;
}
.nav-sub {
  font-family: 'Courier New', monospace; font-size: 9px;
  color: rgba(255,255,255,.22); letter-spacing: .15em;
}
.nav-links {
  display: flex; gap: 4px; margin-left: auto;
}
.nav-link {
  padding: 5px 14px; font-size: 11px;
  font-family: 'Courier New', monospace; letter-spacing: .12em;
  color: rgba(255,255,255,.38); text-decoration: none;
  border: 1px solid transparent;
  transition: all .2s ease;
}
.nav-link:hover { color: #fff; border-color: rgba(255,255,255,.12); }
.nav-link.active { color: var(--accent,#E30613); border-color: var(--accent,#E30613); background: rgba(227,6,19,.08); }
.nav-status {
  display: flex; align-items: center; gap: 6px; flex-shrink: 0;
}
.status-dot {
  width: 5px; height: 5px; border-radius: 50%; background: #00FFB2;
  animation: navBlink 2.8s ease-in-out infinite;
}
.status-txt { font-family: 'Courier New', monospace; font-size: 8px; color: rgba(255,255,255,.22); letter-spacing: .2em; }
.nav-progress {
  height: 2px; background: linear-gradient(90deg, var(--accent,#E30613), transparent);
  width: 0; transition: width .3s ease;
}
@media(max-width:600px){ .nav-sub,.nav-status{display:none} .nav-link{padding:5px 10px;font-size:10px} }
`;

function injectNav(activePage, accent) {
  document.head.insertAdjacentHTML('beforeend', `<style>${NAV_CSS}</style>`);
  document.body.insertAdjacentHTML('afterbegin', NAV_HTML);
  document.documentElement.style.setProperty('--accent', accent || '#E30613');
  document.getElementById('site-nav').style.setProperty('--accent', accent || '#E30613');
  const link = document.querySelector(`.nav-link[data-page="${activePage}"]`);
  if (link) link.classList.add('active');
  // Scroll progress bar
  window.addEventListener('scroll', () => {
    const pct = window.scrollY / (document.documentElement.scrollHeight - window.innerHeight) * 100;
    document.querySelector('.nav-progress').style.width = pct + '%';
  });
  // Push content below nav
  document.body.style.paddingTop = '52px';
}

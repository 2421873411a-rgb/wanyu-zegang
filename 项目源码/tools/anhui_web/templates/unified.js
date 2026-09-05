(() => {
  document.body.classList.add('js-unified');
  const views = [...document.querySelectorAll('[data-view]')];
  const tabs = [...document.querySelectorAll('[data-view-link]')];
  const valid = new Set(views.map((node) => node.dataset.view));
  const nav = document.querySelector('.product-nav');
  const progress = document.querySelector('.product-progress span');
  let scrollFrame = 0;
  const updateChrome = () => {
    scrollFrame = 0;
    const max = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    const ratio = Math.min(1, Math.max(0, scrollY / max));
    progress?.style.setProperty('width', `${ratio * 100}%`);
    nav?.classList.toggle('is-scrolled', scrollY > 12);
  };
  const requestChromeUpdate = () => {
    if (!scrollFrame) scrollFrame = requestAnimationFrame(updateChrome);
  };
  const toView = (value) => {
    const raw = value.replace(/^#/, '');
    if (raw === 'dashboard') return document.body.classList.contains('unified-site--jobs') ? 'jobs_dashboard' : 'salary_dashboard';
    return valid.has(raw) ? raw : [...valid][0];
  };
  const activate = (value, write = true) => {
    const view = toView(value || location.hash);
    views.forEach((node) => { node.classList.toggle('is-active', node.dataset.view === view); });
    tabs.forEach((tab) => { const active = tab.dataset.viewLink === view; tab.classList.toggle('is-current', active); tab.setAttribute('aria-current', active ? 'page' : 'false'); });
    document.body.dataset.activeView = view;
    tabs.find((tab) => tab.dataset.viewLink === view)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    if (write && location.hash !== `#${view}`) history.replaceState({}, '', `${location.pathname}${location.search}#${view}`);
    document.querySelectorAll('.unified-view').forEach((node) => {
      const active = node.dataset.view === view;
      node.querySelectorAll('.product-main > section').forEach((section) => section.classList.toggle('is-visible', active));
      node.querySelectorAll('.archive-flow > *').forEach((child, index) => {
        child.classList.toggle('is-visible', active);
        if (active) child.style.setProperty('--archive-delay', `${Math.min(index, 18) * 18}ms`);
      });
    });
    scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    requestChromeUpdate();
  };
  const setupArchiveControls = () => {
    document.querySelectorAll('[data-archive-toggle="all"]').forEach((button) => {
      button.addEventListener('click', () => {
        const sections = [...button.closest('.archive-index-shell')?.parentElement?.querySelectorAll('[data-archive-section]') || []];
        const shouldOpen = sections.some((section) => !section.open);
        sections.forEach((section) => {
          section.open = shouldOpen;
          section.querySelector('summary')?.setAttribute('aria-expanded', String(shouldOpen));
        });
        button.setAttribute('aria-expanded', String(shouldOpen));
        button.textContent = shouldOpen ? '收起全部' : '展开全部';
      });
    });
    document.querySelectorAll('[data-archive-index-link]').forEach((link) => {
      link.addEventListener('click', (event) => {
        const hash = link.getAttribute('href') || '';
        const target = hash.startsWith('#') ? document.querySelector(hash) : null;
        if (!target) return;
        event.preventDefault();
        const section = target.closest('[data-archive-section]');
        if (section) {
          section.open = true;
          section.querySelector('summary')?.setAttribute('aria-expanded', 'true');
        }
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
    document.querySelectorAll('[data-archive-section] summary').forEach((summary) => {
      summary.addEventListener('click', () => {
        requestAnimationFrame(() => summary.setAttribute('aria-expanded', String(summary.parentElement?.open)));
      });
    });
    document.querySelectorAll('[data-archive-search]').forEach((input) => {
      const shell = input.closest('.archive-index-shell');
      const root = shell?.parentElement;
      const status = shell?.querySelector('[data-archive-search-status]');
      const search = () => {
        const query = String(input.value || '').trim().toLowerCase();
        const sections = [...root?.querySelectorAll('[data-archive-section]') || []];
        let visible = 0;
        sections.forEach((section) => {
          const hit = !query || section.textContent.toLowerCase().includes(query);
          section.hidden = !hit;
          if (hit) { visible += 1; if (query) section.open = true; }
        });
        shell?.querySelectorAll('[data-archive-index-link]').forEach((link) => {
          const target = document.querySelector(link.getAttribute('href') || '');
          link.hidden = Boolean(query && target?.hidden);
        });
        if (status) status.textContent = query ? `找到 ${visible} 个档案分组` : `显示全部 ${sections.length} 个档案分组`;
      };
      input.addEventListener('input', search);
    });
  };
  tabs.forEach((tab) => tab.addEventListener('click', () => activate(tab.dataset.viewLink)));
  addEventListener('hashchange', () => activate(location.hash, false));
  addEventListener('scroll', requestChromeUpdate, { passive: true });
  addEventListener('resize', requestChromeUpdate, { passive: true });
  setupArchiveControls();
  activate(location.hash || [...valid][0]);
  updateChrome();
})();

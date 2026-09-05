(() => {
  const data = document.querySelector('#page-data');
  if (!window.productData && data) {
    try { window.productData = JSON.parse(data.textContent || '{}'); } catch { window.productData = {}; }
  }
  window.productData = window.productData || {};
  window.productUrl = (updates = {}) => {
    const url = new URL(location.href);
    Object.entries(updates).forEach(([key, value]) => value === '' || value == null ? url.searchParams.delete(key) : url.searchParams.set(key, value));
    return url;
  };
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const frameKey = Symbol('motionFrame');
  const settleKey = Symbol('motionSettle');
  const readNumber = (node) => {
    const value = Number.parseFloat(String(node?.textContent || '').replace(/[^0-9.+-]/g, ''));
    return Number.isFinite(value) ? value : 0;
  };
  const animateNumber = (node, target, options = {}) => {
    if (!node) return;
    const next = Number(target);
    if (!Number.isFinite(next)) return;
    if (node[frameKey]) cancelAnimationFrame(node[frameKey]);
    if (node[settleKey]) { clearTimeout(node[settleKey]); node[settleKey] = 0; }
    const start = readNumber(node);
    const duration = reduced.matches ? 0 : Number(options.duration || 420);
    const format = options.format || ((value) => value.toLocaleString('en-US', { maximumFractionDigits: 0 }));
    if (!duration || Math.abs(next - start) < 0.005) { node.textContent = format(next); return; }
    const started = performance.now();
    /* rAF 停摆（窗口遮挡 / 后台节流）时由 setTimeout 兜底落定终值 */
    node[settleKey] = setTimeout(() => { node.textContent = format(next); node[frameKey] = 0; }, duration + 120);
    const tick = (now) => {
      const progress = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      node.textContent = format(start + (next - start) * eased);
      if (progress < 1) node[frameKey] = requestAnimationFrame(tick);
      else { node[frameKey] = 0; if (node[settleKey]) { clearTimeout(node[settleKey]); node[settleKey] = 0; } }
    };
    node[frameKey] = requestAnimationFrame(tick);
  };
  const pulse = (node) => {
    if (!node || reduced.matches) return;
    node.classList.remove('is-pinging');
    void node.offsetWidth;
    node.classList.add('is-pinging');
  };
  const transition = (node, className, duration = 420) => {
    if (!node) return;
    if (node.__wanyuTransitionTimer) clearTimeout(node.__wanyuTransitionTimer);
    node.classList.remove(className);
    void node.offsetWidth;
    if (reduced.matches) return;
    node.classList.add(className);
    node.__wanyuTransitionTimer = setTimeout(() => {
      node.classList.remove(className);
      node.__wanyuTransitionTimer = 0;
    }, duration);
  };
  window.wanyuMotion = { reduced, animateNumber, pulse, transition };
})();

(() => {
  /* 皖域择岗 · 机会洞察：多人岗筛选 / 梯队联动 / CSV 导出 */
  if (!document.querySelector('#insight-multi-table')) return;
  const table = document.querySelector('#insight-multi-table');
  const rows = [...table.querySelectorAll('tbody tr')];
  const countNode = document.querySelector('#insight-multi-count');
  const citySelect = document.querySelector('#insight-city');
  const examSelect = document.querySelector('#insight-exam');
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  let minRecruits = 2;
  const csvCell = (value) => { let text = String(value ?? ''); if (/^[=+\-@]/.test(text)) text = "'" + text; return '"' + text.replaceAll('"', '""') + '"'; };
  const filter = () => {
    let visible = 0;
    rows.forEach((row) => {
      const hit = Number(row.dataset.recruits || 0) >= minRecruits
        && (!citySelect?.value || row.dataset.city === citySelect.value)
        && (!examSelect?.value || row.dataset.exam === examSelect.value);
      row.hidden = !hit;
      if (hit) visible += 1;
    });
    if (countNode) countNode.textContent = String(visible);
  };
  document.querySelectorAll('[data-multi-min]').forEach((button) => button.addEventListener('click', () => {
    document.querySelectorAll('[data-multi-min]').forEach((item) => item.classList.toggle('is-selected', item === button));
    minRecruits = Number(button.dataset.multiMin) || 0;
    filter();
  }));
  citySelect?.addEventListener('change', filter);
  examSelect?.addEventListener('change', filter);
  document.querySelector('#insight-export')?.addEventListener('click', () => {
    const visible = rows.filter((row) => !row.hidden);
    if (!visible.length) return;
    const header = ['城市', '类别', '代码', '单位与职位', '招录人数', '报名'].map(csvCell).join(',');
    const lines = visible.map((row) => [...row.children].slice(0, 6).map((cell) => csvCell(cell.textContent.trim())).join(','));
    const csv = '\ufeff' + [header, ...lines].join('\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    link.download = '多人岗机会清单.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  });
  document.querySelectorAll('[data-tier-card]').forEach((card) => card.addEventListener('click', () => {
    const tier = card.dataset.tierCard;
    const table2 = document.querySelector('#insight-quick-table');
    if (!table2) return;
    const active = card.classList.toggle('is-selected');
    table2.querySelectorAll('tbody tr').forEach((row) => { row.classList.toggle('is-highlight', active && row.dataset.tier === tier); });
    document.querySelectorAll('[data-tier-card]').forEach((item) => { if (item !== card) item.classList.remove('is-selected'); });
  }));
  filter();
})();

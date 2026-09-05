(() => {
  /* 皖域择岗 · 岗位详情浮层 v9.2：全字段 + 资格标签解读 + 同城定位 + 快捷操作（收藏/对比/平替/模拟） */
  const data = window.productData || {};
  const records = Array.isArray(data.records) ? data.records : [];
  if (!records.length) return;
  const recordById = new Map(records.map((record) => [String(record.record_id), record]));
  const metrics = data.metrics || {};
  const cityStats = new Map((metrics.cities || []).map((item) => [String(item.city), item]));
  const salarySeries = data.salary?.series || {};
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const store = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key) || fallback); } catch { return null; } };
  const writeKey = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} };
  const parseNum = (value) => { const num = Number.parseFloat(String(value ?? '').replace(/[^0-9.]/g, '')); return Number.isFinite(num) ? num : null; };
  const KEYS = { saved: 'wanyu.jobSaved.v1', compare: 'wanyu.jobCompare.v1', overrides: 'wanyu.registrationOverrides.v1' };
  const userStore = window.WanyuUserStore;
  const v12State = Boolean(data.cycleRuntime?.cycle && userStore);
  const validCompetitionTypes = new Set(['examinees', 'registrations', 'interview_shortlisted']);
  const SKIP_FIELDS = new Set(['报名*', '审查合格*', '有效笔试/达线/规模参考', '有效笔试/达线', '最低入围/线', '最低面试线', '最高笔试']);

  const field = (label, value) => '<div><dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(value === '' || value === null || value === undefined ? '—' : value) + '</dd></div>';

  const savedIds = () => v12State ? new Set(userStore.activeLocalSaved?.() || []) : (() => { const ids = store(KEYS.saved, '[]'); return new Set(Array.isArray(ids) ? ids.map(String) : []); })();
  const compareIds = () => v12State ? new Set(userStore.activeLocalCompare?.() || []) : (() => { const ids = store(KEYS.compare, '[]'); return new Set(Array.isArray(ids) ? ids.map(String) : []); })();
  const toggleList = (key, id, eventName) => {
    if (v12State) {
      const isSaved = key === KEYS.saved;
      const ids = isSaved ? new Set(userStore.activeLocalSaved?.() || []) : new Set(userStore.activeLocalCompare?.() || []);
      const value = String(id);
      const index = ids.has(value);
      if (index) ids.delete(value); else ids.add(value);
      if (isSaved) userStore.saveActiveSaved(ids); else userStore.saveActiveCompare(ids);
      document.dispatchEvent(new CustomEvent(eventName, { detail: { id: value } }));
      return !index;
    }
    const ids = store(key, '[]');
    const list = Array.isArray(ids) ? ids.map(String) : [];
    const index = list.indexOf(id);
    if (index >= 0) list.splice(index, 1); else list.push(id);
    writeKey(key, list);
    document.dispatchEvent(new CustomEvent(eventName, { detail: { id } }));
    return index < 0;
  };

  const cityPosition = (record) => {
    const lines = records
      .filter((item) => item.city === record.city && item.exam === record.exam && !item.exclusion)
      .map((item) => parseNum(item.fields?.['最低入围/线'] ?? item.fields?.['最低面试线']))
      .filter((value) => value !== null)
      .sort((a, b) => a - b);
    const mine = parseNum(record.fields?.['最低入围/线'] ?? record.fields?.['最低面试线']);
    if (mine === null || !lines.length) return null;
    const below = lines.filter((value) => value < mine).length;
    const median = lines[Math.floor(lines.length / 2)];
    return { count: lines.length, below, median, min: lines[0], max: lines[lines.length - 1], mine };
  };

  const openDetail = (record) => {
    if (!record) return;
    const tags = (record.eligibility?.tags || []).map(String);
    const evaluate = window.wanyuEligibility?.evaluate || (() => ({ ok: true, reasons: [] }));
    const verdict = evaluate(tags.join(' '));
    const tagLabels = window.wanyuEligibility?.TAG_LABELS || {};
    const natures = (record.natures || []).map((item) => '<span class="nature-chip">' + escapeHtml(item.label) + '</span>').join('');
    const base = Number(record.competition_base || 0);
    const overrides = store(KEYS.overrides, '{}') || {};
    const override = Number(overrides[record.record_id] || 0);
    const denominator = override > 0 ? override : validCompetitionTypes.has(String(record.competition_metric_type || '')) ? base : 0;
    const ratioComparable = denominator > 0;
    const ratioText = ratioComparable ? '1:' + (denominator / Math.max(1, Number(record.recruits || 1))).toFixed(1) : '不可比';
    const ratioSource = override > 0 ? '本机手动修正' : ratioComparable ? (record.competition_source || '已观测分母') : '缺少可比分母';
    const salaryKey = record.exam === '事业单位' ? '事业编' : '公务员';
    const salary3y = Number(salarySeries?.[salaryKey]?.[record.city]?.['3年'] || 0);
    const stats = cityStats.get(record.city) || {};
    const position = cityPosition(record);
    const savedNow = savedIds().has(String(record.record_id));
    const compareNow = compareIds().has(String(record.record_id));
    const extraFields = Object.entries(record.fields || {}).filter(([name]) => !SKIP_FIELDS.has(name));
    const tagHtml = tags.length
      ? '<div class="detail-tags">' + tags.map((tag) => {
          const ok = !verdict.reasons.includes(tagLabels[tag] || tag);
          return '<span class="detail-tag ' + (ok ? 'is-ok' : 'is-blocked') + '"><b>' + escapeHtml(tagLabels[tag] || tag) + '</b>' + (ok ? '·符合你的条件' : '·不满足') + '</span>';
        }).join('') + '</div>'
      : '<p class="wanyu-dialog__note">该岗位没有身份/资格限制标签，普通考生均可关注。</p>';
    const body =
      '<div class="detail-head"><div><p class="detail-head__meta">' + escapeHtml(record.city) + '市 · ' + escapeHtml(record.exam) + '</p><strong class="detail-head__code">' + escapeHtml(record.code) + '</strong><h3 class="detail-head__title">' + escapeHtml(record.unit_position) + '</h3>' + (record.title_status === 'not_separately_published' ? '<small class="detail-head__note">职位名称：源表未单列披露</small>' : '') + '</div>'
      + '<div class="detail-head__nums"><div><span>招录</span><b>' + Number(record.recruits || 0) + ' 人</b></div><div><span>竞争</span><b>' + ratioText + '</b><small>' + escapeHtml(ratioSource) + '</small></div>'
      + '<div><span>入围线</span><b>' + (position ? position.mine.toFixed(1) : '—') + '</b></div><div><span>同市 3 年待遇</span><b>' + (salary3y ? salary3y.toFixed(1) + ' 万' : '—') + '</b><small>' + escapeHtml(salaryKey) + '</small></div></div></div>'
      + (record.exclusion ? '<p class="detail-excluded">⚠ 定向岗位：' + escapeHtml(record.exclusion.category_label || record.exclusion.reason || '身份定向，普通考生不可报') + '</p>' : '')
      + '<p class="wanyu-dialog__lead">资格标签解读</p>' + tagHtml
      + (natures ? '<p class="wanyu-dialog__lead">岗位性质</p><div class="detail-tags">' + natures + '</div>' : '')
      + '<p class="wanyu-dialog__lead">核心数据</p><dl class="detail-grid">'
      + field('报名', record.fields?.['报名*']) + field('审查合格', record.fields?.['审查合格*'])
      + field('有效笔试/达线', record.fields?.['有效笔试/达线/规模参考'] || record.fields?.['有效笔试/达线'])
      + field('最低入围/线', record.fields?.['最低入围/线'] ?? record.fields?.['最低面试线']) + field('最高笔试', record.fields?.['最高笔试'])
      + '</dl>'
      + (position ? '<p class="wanyu-dialog__lead">在同市同类别里的位置</p><dl class="detail-grid">'
        + field('有入围线的岗位', position.count + ' 条') + field('本岗线位次', '第 ' + (position.below + 1) + ' 低 / ' + position.count)
        + field('全市最低线', position.min.toFixed(1)) + field('中位线', position.median.toFixed(1)) + field('最高线', position.max.toFixed(1))
        + '</dl><p class="wanyu-dialog__note">入围线越高的岗位通常越热门；中位线可用于快速判断本岗的相对热度。</p>' : '')
      + '<p class="wanyu-dialog__lead">该市整体（' + escapeHtml(record.city) + '）</p><dl class="detail-grid">'
      + field('岗位数', stats.jobs ?? '—') + field('招录', stats.recruits ?? '—')
      + field('平均竞争比', stats.ratio_comparable === true || stats.ratio_status === 'single_denominator' ? (Number(stats.ratio || 0) > 0 ? '1:' + (1 / Number(stats.ratio)).toFixed(1) : '—') : '不可比（分母混合或覆盖不完整）')
      + '</dl>'
      + (extraFields.length ? '<p class="wanyu-dialog__lead">源表全部字段</p><dl class="detail-grid detail-grid--raw">'
        + extraFields.map(([name, value]) => field(name, value)).join('') + '</dl>' : '')
      + '<p class="wanyu-dialog__note">数据取自源表快照，报名期请以官方最新公告复核。</p>';
    window.wanyuOverlay('岗位详情 · ' + record.code, body, {
      footer: '<button type="button" class="primary-button" data-detail-save="' + escapeHtml(record.record_id) + '">' + (savedNow ? '★ 已收藏' : '☆ 收藏') + '</button>'
        + '<button type="button" class="primary-button primary-button--quiet" data-detail-compare="' + escapeHtml(record.record_id) + '">' + (compareNow ? '已加入对比' : '+ 加入对比') + '</button>'
        + '<button type="button" class="text-button" data-substitute-for="' + escapeHtml(record.record_id) + '">找平替</button>'
        + '<button type="button" class="text-button" data-detail-sim="' + escapeHtml(record.code) + '">去模拟对照 →</button>',
      onMount(wrap) {
        wrap.querySelector('[data-detail-save]')?.addEventListener('click', (event) => {
          const added = toggleList(KEYS.saved, String(record.record_id), 'wanyu:saved-changed');
          event.target.textContent = added ? '★ 已收藏' : '☆ 收藏';
        });
        wrap.querySelector('[data-detail-compare]')?.addEventListener('click', (event) => {
          const added = toggleList(KEYS.compare, String(record.record_id), 'wanyu:compare-changed');
          event.target.textContent = added ? '已加入对比' : '+ 加入对比';
        });
        wrap.querySelector('[data-detail-sim]')?.addEventListener('click', () => {
          location.hash = location.hash.includes('score_sim') ? location.hash : '#score_sim';
          setTimeout(() => {
            const input = document.querySelector('#sim-job-select');
            if (!input) return;
            const option = [...input.options].find((item) => item.value === String(record.code));
            if (option) { input.value = option.value; input.dispatchEvent(new Event('change', { bubbles: false })); }
          }, 120);
        });
      },
    });
  };

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-job-detail]');
    if (!trigger) return;
    openDetail(recordById.get(String(trigger.dataset.jobDetail)));
  });
  window.wanyuOpenJobDetail = openDetail;
})();

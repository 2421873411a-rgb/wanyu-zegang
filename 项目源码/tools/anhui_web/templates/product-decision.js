(() => {
  /* 皖域择岗 · 一页决策单 v9.2：条件 / 城市短名单 / 收藏(含稳档列) / 体检结论 / 报名自查 / 模拟快照，可打印带走 */
  const data = window.productData || {};
  const sheet = document.querySelector('#decision-sheet');
  if (!sheet) return;
  const store = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key) || fallback); } catch { return null; } };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const parseNum = (value) => { const num = Number.parseFloat(String(value ?? '').replace(/[^0-9.]/g, '')); return Number.isFinite(num) ? num : null; };
  const records = Array.isArray(data.records) ? data.records : [];
  const recordById = new Map(records.map((record) => [String(record.record_id), record]));
  const cityFacts = new Map(((data.cities || data.jobs?.cities || []).map((item) => [String(item.city), item])));
  const salarySeries = data.salary?.series || {};
  const validCompetitionTypes = new Set(['examinees', 'registrations', 'interview_shortlisted']);
  const ratioIsComparable = (item) => Boolean(item && (item.ratio_comparable === true || item.ratio_status === 'single_denominator'));
  const EXAM_COMPOSE = { 事业单位: (a, b) => a + b, 省考: (a, b) => (a + b) / 2 };
  const BAND_TEXT = { safe: '稳', hit: '达线', near: '贴线', miss: '差分' };
  const bandKeyOf = (score, line) => (window.wanyuCore?.bandOf ? window.wanyuCore.bandOf(score, line) : (score >= line + 5 ? 'safe' : score >= line ? 'hit' : score >= line - 3 ? 'near' : 'miss'));

  const buildHtml = () => {
    const profile = store('wanyu.profile.v1', '{}') || {};
    const shortlist = (store('wanyu.cityShortlist.v1', '[]') || []).map(String);
    const savedIds = (store('wanyu.jobSaved.v1', '[]') || []).map(String);
    const notes = store('wanyu.jobNotes.v1', '{}') || {};
    const groups = store('wanyu.jobGroups.v1', '{}') || {};
    const simState = store('wanyu.simState.v1', 'null');
    const sim = (simState && EXAM_COMPOSE[simState.exam] && Array.isArray(simState.scores) && simState.scores.length === 2)
      ? { exam: simState.exam, composite: EXAM_COMPOSE[simState.exam](Number(simState.scores[0]), Number(simState.scores[1])), vol: Number(simState.vol) || 0 }
      : null;
    const identity = ['four_project', 'veteran', 'military_family', 'fresh', 'male', 'female', 'party', 'cert_legal']
      .filter((key) => profile[key])
      .map((key) => ({ four_project: '四项目人员', veteran: '退役士兵', military_family: '随军家属', fresh: '应届', male: '男', female: '女', party: '党员', cert_legal: '法律职业资格' }[key]));
    const today = new Date().toISOString().slice(0, 10);
    const section = (title, body) => '<section><h2>' + title + '</h2>' + body + '</section>';
    const parts = [];
    parts.push('<header class="decision-sheet__head"><h1>报考决策单</h1><p>' + today + ' · 皖域择岗档案 · 本地数据生成，仅供参考，不构成录用预测</p></header>');
    parts.push(section('1 · 我的条件', '<p>' + (identity.length ? identity.join(' · ') : '未设置身份条件') + (profile.strict ? '（严格模式）' : '') + '</p>'));
    if (shortlist.length) {
      const rows = shortlist.map((city) => {
        const facts = cityFacts.get(city) || {};
        const salary = Number(salarySeries?.公务员?.[city]?.['3年'] || 0);
        const ratio = Number(facts.ratio || 0);
        return '<tr><td>' + escapeHtml(city) + '</td><td>' + (facts.jobs ?? '—') + '</td><td>' + (facts.recruits ?? '—') + '</td><td>' + (ratioIsComparable(facts) && ratio > 0 ? '1:' + (1 / ratio).toFixed(1) : '不可比') + '</td><td>' + (salary ? salary.toFixed(1) + ' 万' : '—') + '</td></tr>';
      }).join('');
      parts.push(section('2 · 城市短名单', '<table><thead><tr><th>城市</th><th>岗位</th><th>招录</th><th>竞争比</th><th>公务员3年</th></tr></thead><tbody>' + rows + '</tbody></table>'));
    }
    const savedRecords = savedIds.map((id) => recordById.get(id)).filter(Boolean);
    const bandOfRecord = (record) => {
      if (!sim || record.exam !== sim.exam) return null;
      const line = parseNum(record.fields?.['最低入围/线'] ?? record.fields?.['最低面试线']);
      return line === null ? null : bandKeyOf(sim.composite, line);
    };
    if (savedRecords.length) {
      const rows = savedRecords.map((record) => {
        const id = String(record.record_id);
        const base = Number(record.competition_base || 0);
        const line = String(record.fields?.['最低入围/线'] ?? record.fields?.['最低面试线'] ?? '').trim();
        const band = bandOfRecord(record);
        const comparable = validCompetitionTypes.has(String(record.competition_metric_type || '')) && base > 0;
        return '<tr><td>' + escapeHtml(groups.byJob?.[id] || '') + '</td><td>' + escapeHtml(record.code) + '</td><td>' + escapeHtml(record.city) + '</td><td>' + escapeHtml(record.unit_position) + '</td><td>' + record.recruits + '</td><td>' + (comparable ? '1:' + (base / Number(record.recruits || 1)).toFixed(1) : '不可比') + '</td><td>' + escapeHtml(line || '—') + '</td><td>' + (band ? BAND_TEXT[band] : '—') + '</td><td class="note">' + escapeHtml(notes[id] || '') + '</td></tr>';
      }).join('');
      parts.push(section('3 · 收藏岗位（' + savedRecords.length + '）', '<table class="wide"><thead><tr><th>分组</th><th>代码</th><th>城市</th><th>单位与职位</th><th>招</th><th>竞争</th><th>入围线</th><th>稳档</th><th>笔记</th></tr></thead><tbody>' + rows + '</tbody></table>'));
    }
    /* 体检结论：身份冲突 / 无线岗位 / 稳档结构，自动汇总成一段可读文字 */
    if (savedRecords.length) {
      const conflicts = savedRecords.filter((record) => window.wanyuEligibility && !window.wanyuEligibility.evaluate((record.eligibility?.tags || []).join(' ')).ok);
      const noLine = savedRecords.filter((record) => parseNum(record.fields?.['最低入围/线'] ?? record.fields?.['最低面试线']) === null).length;
      const bands = { safe: 0, hit: 0, near: 0, miss: 0, other: 0 };
      savedRecords.forEach((record) => {
        const band = bandOfRecord(record);
        if (band) bands[band] += 1; else bands.other += 1;
      });
      const lines = [];
      lines.push(conflicts.length
        ? '⚠ 有 ' + conflicts.length + ' 条收藏与你的身份条件冲突（' + conflicts.map((record) => record.code).slice(0, 4).join('、') + '），报名前务必复核或移除。'
        : '✓ 全部收藏岗位与你的身份条件相符。');
      lines.push(sim
        ? '按当前模拟分（' + sim.exam + ' ' + sim.composite.toFixed(1) + ' 分' + (sim.vol ? ' · 波动±' + sim.vol : '') + '）：稳 ' + bands.safe + ' 条 · 达线 ' + bands.hit + ' 条 · 贴线 ' + bands.near + ' 条 · 差分 ' + bands.miss + ' 条。'
          + (bands.safe >= 2 ? '稳档储备充足，可按城市偏好做取舍。' : bands.safe === 1 ? '只有 1 条稳档，建议再补 1–2 条低竞争保底岗。' : '暂无稳档岗位，考虑换赛道或降低城市预期。')
        : '尚未设置分数模拟，稳档列为空；到「分数模拟」输入分数后可自动补全。');
      if (noLine) lines.push('另有 ' + noLine + ' 条岗位源表未提供入围线，不参与稳档对照。');
      parts.push(section('4 · 收藏体检结论', '<ul class="decision-conclusion">' + lines.map((line) => '<li>' + line + '</li>').join('') + '</ul>'));
    }
    if (simState && simState.exam && !sim) {
      const cfg = simState.exam === '省考' ? '（行测+申论）÷2' : '职测+综应';
      parts.push(section('4 · 分数模拟快照', '<p>' + escapeHtml(simState.exam) + ' · 合成 ' + cfg + ' · 两科 ' + (simState.scores || []).map((value) => Number(value).toFixed(1)).join(' + ') + (simState.vol ? ' · 波动 ±' + escapeHtml(simState.vol) : '') + '</p><p class="hint">完整分档清单见「分数模拟」视图。</p>'));
    }
    const checklist = [
      '专业目录已核对：毕业证 / 学位证专业全称与官方目录逐级对上',
      '应届身份口径已确认（社保 / 三方协议状态）',
      '四六级、计算机、法律资格等证书复审前可出示原件',
      '定向岗证明材料齐全（如适用）',
      '缴费截止时间已设提醒',
      '最低服务年限与城市定居计划已和家人沟通',
    ];
    parts.push(section('5 · 报名自查清单', '<ul class="decision-checklist">' + checklist.map((item) => '<li><span class="decision-checklist__box" aria-hidden="true"></span>' + escapeHtml(item) + '</li>').join('') + '</ul>'));
    parts.push('<footer class="decision-sheet__foot"><span>生成于本机浏览器 · 数据口径见「报考手册 · 数据口径与快照」</span><span class="decision-sheet__actions"><button type="button" class="primary-button" data-sheet-action="print">打印 / 存 PDF</button><button type="button" class="text-button" data-sheet-action="close">收起</button></span></footer>');
    return '<div class="decision-sheet__paper">' + parts.join('') + '</div>';
  };

const render = () => {
sheet.innerHTML = buildHtml();
sheet.hidden = false;
const hostView = sheet.closest('[data-view]');
if (hostView && !hostView.classList.contains('is-active')) { try { location.hash = '#' + hostView.dataset.view; } catch {} }
setTimeout(() => { try { sheet.scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch {} }, 380);
  };
  document.querySelectorAll('[data-build-decision]').forEach((button) => button.addEventListener('click', render));
  sheet.addEventListener('click', (event) => {
    const action = event.target.closest('[data-sheet-action]');
    if (!action) return;
    if (action.dataset.sheetAction === 'print') {
      const root = document.createElement('div');
      root.id = 'wanyu-print-root';
      root.innerHTML = sheet.innerHTML;
      document.body.appendChild(root);
      document.body.classList.add('print-decision');
      const cleanup = () => { document.body.classList.remove('print-decision'); root.remove(); window.removeEventListener('afterprint', cleanup); };
      window.addEventListener('afterprint', cleanup);
      window.print();
      setTimeout(cleanup, 2000);
    } else if (action.dataset.sheetAction === 'close') {
      sheet.hidden = true;
    }
  });
})();

/* 皖域择岗 v9.3 · 全岗位库 + 岗位地图（在原总览站之上的加法视图）
   数据：PAGE_DATA.allMajors（构建期已由规则库预打标）；交互全本地。 */
(() => {
  const root = document.getElementById('wyall-table');
  if (!root) return; // 仅总览站挂载
  const pageData = window.productData || (() => { try { return JSON.parse(document.getElementById('page-data').textContent); } catch (e) { return {}; } })();
  const ALL = pageData.allMajors || { rows: [], meta: {}, map: [] };
  const ROWS = ALL.rows || [];
  const META = ALL.meta || {};
  const MAP = ALL.map || [];
  const DIR_NAMES = { four_project: '四项目定向', veteran: '退役士兵定向', military_family: '随军家属定向', targeted: '其他定向' };
  const TAG_NAMES = { fresh_only: '仅应届', gender_male: '限男性', gender_female: '限女性', party: '中共党员', cert_legal: '法律职业资格', min_service: '最低服务期', prof_test: '专业测试', night_shift: '夜班/值班', allowance_diff: '差额拨款' };
  const XU = { dazhuan: 2, benke: 3, shuoshi: 4, boshi: 5 };
  const PALETTE = ['#dfe8fb', '#bdd0f8', '#90b3f3', '#5f93ee', '#2f6fed'];

  const state = { page: 1, pageSize: 50, filters: { kw: '', city: '', lb: '', xl: '', tag: '', exam: '' }, profile: loadProfile(), lastMatch: null, citySel: '', mapMajor: '' };

  function loadProfile() {
    try { return Object.assign({ major: '', cat: '', xl: 'benke', gender: '', hukouCity: '', fresh: false, party: false, cert: false, sp: false, vet: false, fam: false, active: false }, JSON.parse(localStorage.getItem('wy93.profile') || '{}')); } catch (e) { return { major: '', cat: '', xl: 'benke', gender: '', hukouCity: '', fresh: false, party: false, cert: false, sp: false, vet: false, fam: false, active: false }; }
  }
  function saveProfile() { try { localStorage.setItem('wy93.profile', JSON.stringify(state.profile)); } catch (e) {} }
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const normMajor = (s) => String(s || '').replace(/专业/g, '').replace(/\s+/g, '').trim();
  /* 原始岗位专业字段保留代码与备注；候选控件只展示可读名称，避免把编码碎片当成专业。 */
  const cleanMajorOption = (value) => String(value || '').trim().replace(/^[^\u4e00-\u9fffA-Za-z]+/, '').trim();
  const isHumanMajor = (value) => {
    const text = cleanMajorOption(value);
    return text.length >= 2 && /[\u4e00-\u9fffA-Za-z]/.test(text)
      && text.replace(/[\d\s()[\]{}._（）【】+\-*\/、，,;；:.：?？]/g, '').length > 0;
  };
  const majorOptions = () => [...new Set([].concat(META.cats || [], META.majors || []).map(cleanMajorOption).filter(isHumanMajor))]
    .sort((a, b) => a.localeCompare(b, 'zh'));
const guessCat = (m) => { const nm = normMajor(m); return nm && (META.csMembers || []).indexOf(nm) >= 0 ? '计算机类' : ''; };
const bareOf = (s) => String(s || '').replace(/（[^）]*）/g, '').replace(/专业/g, '');
const catalogFor = (nm) => (META.catalog || {})[normMajor(nm)] || [];

  function matchRow(r) {
    const p = state.profile, reasons = []; let bad = '';
    const ok = (t) => reasons.push({ okr: true, t });
    const no = (t) => { reasons.push({ okr: false, t }); if (!bad) bad = t.split('：')[0]; };
    if (r.dir) {
      const pass = (r.dir === 'four_project' && p.sp) || (r.dir === 'veteran' && p.vet) || (r.dir === 'military_family' && p.fam);
      if (pass) ok('定向岗：' + DIR_NAMES[r.dir] + '，身份符合'); else no('身份定向：' + DIR_NAMES[r.dir]);
    }
    if (r.hukou && !r.dir) { if (p.hukouCity && p.hukouCity === r.city) ok('户籍限定：面向' + r.city + '户籍，符合'); else no('户籍限定：面向' + r.city + '户籍招考'); }
    if (r.tags.indexOf('fresh_only') >= 0 && !p.fresh) no('限应届毕业生');
    if (r.tags.indexOf('gender_male') >= 0 && p.gender !== 'male') no('限男性');
    if (r.tags.indexOf('gender_female') >= 0 && p.gender !== 'female') no('限女性');
    if (r.tags.indexOf('party') >= 0 && !p.party) no('限中共党员');
    if (r.tags.indexOf('cert_legal') >= 0 && !p.cert) no('限法律职业资格');
    if ((r.floor || 0) > (XU[p.xl] || 3)) no('学历门槛：' + r.xl);
    if (!r.unlim && !bad) {
      if (!r.zy && r.exam && r.exam !== '省考') {
        ok('专业口径：软件工程档案已核（源库未结构化）');
      } else {
      const nm = normMajor(p.major);
      const items = zyItems(r);
      let hitItem = '';
      if (!nm) hitItem = '不限';
      if (!hitItem) {
        const cat = normMajor(p.cat || guessCat(p.major));
        for (const it of items) {
          const bare = it.replace(/（[^）]*）/g, '').replace(/专业/g, '');
          if (!bare) continue;
          if (cat && bare === cat) { hitItem = bare + '（你所选大类）'; break; }
          if (nm && (bare === nm || bare.indexOf(nm) >= 0)) { hitItem = bare + (bare === nm ? '（与你专业一致）' : '（含你的专业）'); break; }
        }
        if (!hitItem && nm) {
          const cs = META.csMembers || [];
          if (cs.indexOf(nm) >= 0 && items.some((it) => it.indexOf('计算机类') >= 0)) hitItem = '计算机类（你的专业属计算机类）';
        }
      }
      if (hitItem) ok('专业匹配：命中「' + hitItem + '」'); else no('专业不符：专业列无「' + (nm || '未填写') + '」相关项');
      }
    }
    return { ok: bad === '', bad, reasons };
  }

  const zyCache = {};
  function zyItems(r) {
    /* 事业编考区代码存在跨单位复用（同码不同专业），缓存键必须包含专业原文而非仅代码 */
    const key = r.code + '|' + (r.zy || '');
    if (zyCache[key]) return zyCache[key];
    const items = String(r.zy || '').split(/[、，,；;/\s]+/).map((s) => s.trim()).filter(Boolean);
    zyCache[key] = items;
    return items;
  }

  function matchedRows() {
    const out = [], ex = {};
    ROWS.forEach((r) => { const m = matchRow(r); if (m.ok) out.push(r); else ex[m.bad] = (ex[m.bad] || 0) + 1; });
    return { rows: out, ex };
  }

  function tagChips(r) {
    let h = '';
    if (r.exam && r.exam !== '省考') h += '<span class="wyall-tag wyall-tag--hukou">' + r.exam + '</span>';
    if (r.dir) h += '<span class="wyall-tag wyall-tag--dir">' + DIR_NAMES[r.dir] + '</span>';
    r.tags.forEach((t) => { h += '<span class="wyall-tag">' + (TAG_NAMES[t] || t) + '</span>'; });
    if (r.hukou) h += '<span class="wyall-tag wyall-tag--hukou">户籍限定</span>';
    if (r.sl && r.sl !== '不限') h += '<span class="wyall-tag wyall-tag--hukou">申论' + esc(r.sl) + '</span>';
    return h;
  }

  function fmtNum(v) { return v == null ? '—' : v; }

  function renderTable(rows, withReason) {
    const pages = Math.max(1, Math.ceil(rows.length / state.pageSize));
    const start = (state.page - 1) * state.pageSize;
    const sc = META.scoreCoverage || {};
    const pe = sc.perExam || {};
    const covPct = function (n, d) { return d ? Math.round((n || 0) * 100 / d) : 0; };
    const examSeg = ['省考', '事业编', '国考'].map(function (ex) {
      const e = pe[ex] || {};
      return ex + ' 报名' + covPct(e.bm, e.total) + '% · 达线/进面人数' + covPct(e.adv, e.total) + '% · 入围线' + covPct(e.line, e.total) + '%';
    }).join('；');
    let h = '<div style="padding:10px 12px">共 ' + rows.length + ' 个岗位 · 第 ' + state.page + ' / ' + pages + ' 页<br><span style="opacity:.75">全库覆盖：报名 ' + (sc.bm || 0) + '/' + META.total + '（' + covPct(sc.bm, META.total) + '%）· 达线/进面人数 ' + (sc.adv || 0) + '（' + covPct(sc.adv, META.total) + '%）· 入围线 ' + (sc.line || 0) + '（' + covPct(sc.line, META.total) + '%）· 拟录用 ' + (sc.hire || 0) + '<br>分考试：' + examSeg + (META.cycle ? '（数据周期 ' + META.cycle + '）' : '') + '；"—"表示该岗成绩数据未发布或不适用：事业编逐岗成绩散见于各单位复审公告（已尽量回收），下半年统考 9 月 7-11 日报名、10 月 17 日笔试，数据届时发布。</span></div>';
    h += '<table><thead><tr><th>代码</th><th>市</th><th>招录机关 · 职位</th><th>人数</th><th title="报名人数，官方报名数据逐岗汇编">报名</th><th title="最低入围线，省考为合成成绩、事业编为笔试求和，混合量纲按考试类别区分">入围线</th><th title="入围人数（有效笔试/达线），现覆盖软件工程档案省考岗，其余岗位待名单明细接入">入围人数</th><th>学历</th><th>专业要求 / 标签</th></tr></thead><tbody>';
    rows.slice(start, start + state.pageSize).forEach((r) => {
      h += '<tr class="wyall-row" data-code="' + r.code + '" data-city="' + esc(r.city) + '" data-exam="' + esc(r.exam || '省考') + '"><td>' + r.code + '</td><td>' + r.city + '</td><td><b>' + esc(r.unit) + '</b><span class="wyall-reason"><br>' + esc(r.zw) + '</span></td><td>' + r.num + '</td><td>' + fmtNum(r.bm) + '</td><td>' + fmtNum(r.line) + '</td><td>' + fmtNum(r.adv) + '</td><td>' + esc(r.xl) + '</td><td><span class="wyall-reason">' + esc((r.zy || '不限').slice(0, 40)) + (r.zy.length > 40 ? '…' : '') + '</span><br>' + tagChips(r);
      if (withReason) {
        matchRow(r).reasons.forEach((x) => { h += '<div class="wyall-reason' + (x.okr ? '' : ' wyall-reason--bad') + '"><b>' + (x.okr ? '✓' : '✕') + '</b> ' + esc(x.t) + '</div>'; });
      }
      h += '</td></tr>';
    });
    h += '</tbody></table>';
    if (pages > 1) {
      h += '<div class="wyall-pager" style="padding:10px 12px">';
      for (let i = 1; i <= pages; i++) {
        if (pages > 15 && i > 3 && i < pages - 2 && Math.abs(i - state.page) > 2) { if (i === 4) h += '<span>…</span>'; continue; }
        h += '<button data-page="' + i + '" class="' + (i === state.page ? 'is-on' : '') + '">' + i + '</button>';
      }
      h += '</div>';
    }
    return h;
  }

  /* —— v9.8 岗位成绩单：逐人笔试排名 / 笔面综合排名 / 输分查排名 —— */
  let scoreState = null;
  const scoreKey = (row, includeNum = true) => [row.exam || '省考', row.city || '', row.code || '', includeNum && row.num != null ? row.num : ''].join('|');
  function scoreListsFor(row) {
    const lists = window.__SCORE_LISTS__ || {};
    const byKey = lists.by_key;
    if (byKey) {
      return byKey[scoreKey(row)] || byKey[scoreKey(row, false)] || {};
    }
    return { bs: (lists.bs || {})[row.code] || [], ms: (lists.ms || {})[row.code] || [] };
  }
  function renderScorePanel(row) {
    const code = row.code;
    const host = document.getElementById('wyall-score');
    if (!host) return;
    const lists = scoreListsFor(row);
    const bs = lists.bs || [];
    const ms = lists.ms || [];
    const key = scoreKey(row);
    if (!scoreState || scoreState.key !== key) scoreState = { key: key, tab: bs.length ? 'bs' : 'ms', page: 1, q: null };
    if (!bs.length && !ms.length) { host.innerHTML = '<p class="wyall-foot">该岗暂无考生成绩名单：名单来自各考区/单位官方公告逐岗汇总，公告未发布或不公开的岗位不展示。</p>'; return; }
    if (scoreState.tab === 'ms' && !ms.length) scoreState.tab = 'bs';
    if (scoreState.tab === 'bs' && !bs.length) scoreState.tab = 'ms';
    const list = scoreState.tab === 'bs' ? bs : ms;
    const pages = Math.max(1, Math.ceil(list.length / 20));
    if (scoreState.page > pages) scoreState.page = pages;
    const start = (scoreState.page - 1) * 20;
    let rowsHtml = '';
    list.slice(start, start + 20).forEach((row, i) => {
      if (scoreState.tab === 'bs') rowsHtml += '<tr><td>' + (start + i + 1) + '</td><td>' + esc(row[1] || '—') + '</td><td><b>' + row[0] + '</b></td></tr>';
      else rowsHtml += '<tr><td>' + (start + i + 1) + '</td><td>' + esc(row[3] || '—') + '</td><td>' + (row[1] == null ? '—' : row[1]) + '</td><td>' + (row[2] == null ? '—' : row[2]) + '</td><td><b>' + row[0] + '</b></td></tr>';
    });
    let lookupOut = '';
    if (scoreState.q != null && scoreState.q !== '') {
      const q = Number(scoreState.q);
      if (!isNaN(q)) {
        const above = list.filter((x) => x[0] > q).length;
        const equal = list.filter((x) => x[0] === q).length;
        lookupOut = above + equal ? '该岗共 ' + list.length + ' 人 · 成绩 ' + q + ' 可排第 <b>' + (above + 1) + '</b> 名（高于 ' + above + ' 人' + (equal ? '，含同分 ' + equal + ' 人' : '') + '）' : '';
      }
    }
    const qLabel = scoreState.tab === 'bs' ? '输入笔试成绩查排名' : '输入考试总成绩查排名';
    let pager = '';
    if (pages > 1) {
      pager = '<div class="wyall-pager" style="padding:6px 0">';
      const win = [];
      for (let i = 1; i <= pages; i++) { if (i <= 2 || i > pages - 2 || Math.abs(i - scoreState.page) <= 1) win.push(i); }
      let last = 0;
      win.forEach((i) => { if (last && i - last > 1) pager += '<span>…</span>'; pager += '<button type="button" data-score-page="' + i + '" class="' + (i === scoreState.page ? 'is-on' : '') + '">' + i + '</button>'; last = i; });
      pager += '</div>';
    }
    host.innerHTML = '<div style="display:flex;gap:8px;flex-wrap:wrap;margin:6px 0">' +
      (bs.length ? '<button type="button" class="wyall-btn' + (scoreState.tab === 'bs' ? ' is-on' : '') + '" data-score-tab="bs">笔试成绩排名（' + bs.length + ' 人）</button>' : '') +
      (ms.length ? '<button type="button" class="wyall-btn' + (scoreState.tab === 'ms' ? ' is-on' : '') + '" data-score-tab="ms">笔面综合排名（' + ms.length + ' 人）</button>' : '') +
      '<span class="wyall-note" style="align-self:center">' + (scoreState.tab === 'bs' ? '按笔试合成成绩降序 · 来源：官方达线/成绩名单' : '按考试总成绩降序 · 来源：面试成绩及总成绩公告') + '</span></div>' +
      '<div style="display:flex;gap:8px;align-items:center;margin:8px 0;flex-wrap:wrap"><input id="wyall-score-q" type="number" step="0.01" placeholder="' + qLabel + '" value="' + (scoreState.q == null ? '' : scoreState.q) + '" style="height:30px;padding:0 8px;border:1px solid #d2e1ed;border-radius:8px"><button type="button" class="wyall-btn" data-score-go>查排名</button><span id="wyall-score-qout" style="opacity:.9">' + lookupOut + '</span></div>' +
      '<div style="max-height:300px;overflow:auto;border:1px solid var(--line,#d8e4ee);border-radius:8px"><table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr>' +
      (scoreState.tab === 'bs' ? '<th style="text-align:left;padding:6px 10px">排名</th><th style="text-align:left;padding:6px 10px">准考证号</th><th style="text-align:left;padding:6px 10px">笔试成绩</th>' : '<th style="text-align:left;padding:6px 10px">总成绩排名</th><th style="text-align:left;padding:6px 10px">准考证号</th><th style="text-align:left;padding:6px 10px">笔试</th><th style="text-align:left;padding:6px 10px">面试</th><th style="text-align:left;padding:6px 10px">总成绩</th>') +
      '</tr></thead><tbody>' + rowsHtml + '</tbody></table></div>' + pager;
    if (!host.dataset.bound) {
      host.dataset.bound = '1';
      host.addEventListener('click', (event) => {
        const tabBtn = event.target.closest('[data-score-tab]');
        if (tabBtn) { scoreState.tab = tabBtn.dataset.scoreTab; scoreState.page = 1; scoreState.q = null; renderScorePanel(row); return; }
        const pgBtn = event.target.closest('[data-score-page]');
        if (pgBtn) { scoreState.page = Number(pgBtn.dataset.scorePage) || 1; renderScorePanel(row); return; }
        if (event.target.closest('[data-score-go]')) {
          const input = document.getElementById('wyall-score-q');
          scoreState.q = input && input.value !== '' ? input.value : null;
          renderScorePanel(row);
        }
      });
      host.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && event.target && event.target.id === 'wyall-score-q') {
          event.preventDefault();
          scoreState.q = event.target.value !== '' ? event.target.value : null;
          renderScorePanel(row);
        }
      });
    }
  }

function openDetail(code, cityOrReason, examOrReason, withReason) {
const city = typeof cityOrReason === 'string' ? cityOrReason : '';
const exam = typeof examOrReason === 'string' ? examOrReason : '';
const reason = typeof cityOrReason === 'boolean' ? cityOrReason : (typeof examOrReason === 'boolean' ? examOrReason : Boolean(withReason));
    const r = ROWS.filter((x) => x.code === code && (!city || x.city === city) && (!exam || x.exam === exam))[0];
    if (!r) return;    let h = '<p class="wyall-dialog-lead">' + r.code + ' · ' + esc(r.city) + (r.reg ? ' · ' + esc(r.reg) : '') + ' · 招 ' + r.num + ' 人</p><div>' + tagChips(r) + '</div><dl class="wyall-kv">';
    [['招录机关', r.unit], ['机构性质 / 层级', (r.xz || '—') + ' / ' + (r.cc || '—')], ['职位名称', r.zw], ['职级层次', r.zj || '—'], ['职位类别', r.lb || '—'], ['招考人数', r.num], ['报名 / 审查合格 / 缴费', (r.bm == null ? '—' : r.bm) + ' / ' + (r.hg == null ? '—' : r.hg) + ' / ' + (r.jf == null ? '—' : r.jf)], ['最低入围线（笔试）', r.line == null ? '—' : r.line], ['入围人数（有效笔试/达线）', r.adv == null ? '—' : r.adv], ['最高笔试参考', r.top == null ? '—' : r.top], ['拟录用参考（笔试/总成绩）', (r.hq == null ? '—' : r.hq) + ' / ' + (r.ht == null ? '—' : r.ht)], ['学历 / 学位', r.xl + ' / ' + (r.xw || '—')], ['年龄', r.age || '—'], ['专业要求', r.zy || '不限'], ['经历要求', r.jl || '—'], ['其他条件', r.qt || '—'], ['申论 / 专业科目', (r.sl || '—') + ' / ' + (r.km || '—')], ['备注（职位简介）', r.bz || '—'], ['官方备注（国考职位表原文）', r.officialRemark || '—'], ['咨询电话', r.dh || '—']].forEach((x) => { h += '<dt>' + x[0] + '</dt><dd>' + esc(x[1]) + '</dd>'; });
    h += '</dl>';
    if (r.bm == null && r.line == null) h += '<p class="wyall-foot">该岗暂无报名与成绩数据：报名/入围线/最高笔试已按官方渠道逐岗汇编，仅个别岗位数据未发布，发布后自动接入。</p>';
    if (r.line != null && r.top != null) h += '<p class="wyall-foot">入围线为笔试合成成绩（省考口径），最高笔试为该岗考生成绩上限；数据来源见“名词解释与数据来源”。</p>';
    if (reason && state.profile.active) {
      const m = matchRow(r);
      h += '<p><b style="color:' + (m.ok ? '#1d9e74' : '#c8452c') + '">' + (m.ok ? '✓ 画像匹配：可报' : '✕ 画像匹配：不可报') + '</b></p>' + m.reasons.map((x) => '<div class="wyall-reason' + (x.okr ? '' : ' wyall-reason--bad') + '"><b>' + (x.okr ? '✓' : '✕') + '</b> ' + esc(x.t) + '</div>').join('');
    }
    h += '<p class="wyall-foot">标签由规则库自动解析（附原文可复核），最终以官方公告为准。</p>';
    h += '<div style="margin:10px 0 2px"><b>岗位成绩单</b><span class="wyall-note">（逐人成绩与排名，可输入自己的分数查询名次）</span></div><div id="wyall-score"></div>';
    if (typeof window.wanyuOverlay === 'function') {
      window.wanyuOverlay('岗位详情 · ' + esc(r.unit), h);
      setTimeout(() => renderScorePanel(r), 30);
    }
  }

  function csvExport(rows) {
    const head = ['考试类别', '职位代码', '市', '招录机关', '职位名称', '人数', '学历', '专业要求', '其他条件', '经历要求', '职位简介', '官方备注', '标签', '身份定向', '报名', '入围线', '入围人数'];
    const lines = [head.join(',')];
    rows.forEach((r) => {
      const cells = [r.exam || '省考', r.code, r.city, r.unit, r.zw, r.num, r.xl, r.zy, r.qt, r.jl, r.bz, r.officialRemark || '', r.tags.join('|'), DIR_NAMES[r.dir] || '', r.bm == null ? '' : r.bm, r.line == null ? '' : r.line, r.adv == null ? '' : r.adv];
      lines.push(cells.map((c) => { c = String(c == null ? '' : c); return /[",\n]/.test(c) ? '"' + c.replace(/"/g, '""') + '"' : c; }).join(','));
    });
    const blob = new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '皖域全专业岗位.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /* ---------------- 岗位地图 ---------------- */
function mapFloorMax() {
const sel = document.getElementById('wyall-map-floor');
return sel ? Number(sel.value || 3) : 3;
}
const FLOOR_NAMES = { 2: '大专', 3: '本科', 4: '硕士', 5: '博士' };
function countsByCity() {
const counts = {}, rec = {};
let rows;
if (state.mapMajor) {
const am = window.wanyuAllMatch;
const floorMax = mapFloorMax();
rows = ROWS.filter((r) => (!am || am.match(r, state.mapMajor)) && (r.floor || 0) <= floorMax);
} else if (state.profile.active && state.lastMatch) {
rows = state.lastMatch.rows;
} else {
rows = ROWS;
}
rows.forEach((r) => { counts[r.city] = (counts[r.city] || 0) + 1; rec[r.city] = (rec[r.city] || 0) + r.num; });
const floorMax = mapFloorMax();
const floorLabel = state.mapMajor && FLOOR_NAMES[floorMax] ? FLOOR_NAMES[floorMax] : '';
return { counts, rec, total: rows.length, mode: state.mapMajor ? 'major' : (state.profile.active && state.lastMatch ? 'profile' : 'all'), floorLabel };
}

  function renderMap() {
    const host = document.getElementById('wyall-map');
    if (!host || !MAP.length) return;
    let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
    MAP.forEach((f) => f.polys.forEach((poly) => poly.forEach((ring) => ring.forEach((pt) => {
      if (pt[0] < minX) minX = pt[0]; if (pt[0] > maxX) maxX = pt[0]; if (pt[1] < minY) minY = pt[1]; if (pt[1] > maxY) maxY = pt[1];
    }))));
    const W = 620, midLat = (minY + maxY) / 2, kx = Math.cos(midLat * Math.PI / 180);
    const k = W / ((maxX - minX) * kx), H = (maxY - minY) * k;
    const cc = countsByCity();
    let maxN = 1;
    Object.keys(cc.counts).forEach((c) => { if (cc.counts[c] > maxN) maxN = cc.counts[c]; });
    const color = (n) => (n ? PALETTE[Math.min(4, Math.floor((n - 1) / Math.max(1, Math.ceil(maxN / 5))))] : '');
    let svg = '<svg class="wyall-map" viewBox="0 0 ' + W + ' ' + (H + 8) + '" role="img" aria-label="安徽省各市岗位分布地图">';
    MAP.forEach((f) => {
      const n = cc.counts[f.name] || 0;
      svg += '<path class="city' + (n ? '' : ' q0') + (state.citySel === f.name ? ' is-on' : '') + '" data-city="' + f.name + '" fill="' + color(n) + '" d="';
      f.polys.forEach((poly) => poly.forEach((ring) => {
        svg += 'M' + ring.map((pt) => (((pt[0] - minX) * kx * k).toFixed(1)) + ',' + ((maxY - pt[1]) * k).toFixed(1)).join('L') + 'Z';
      }));
      svg += '"><title>' + f.name + '：' + n + ' 岗 / ' + (cc.rec[f.name] || 0) + ' 人</title></path>';
    });
    MAP.forEach((f) => {
      const x = (f.cx - minX) * kx * k, y = (maxY - f.cy) * k;
      svg += '<text class="cl" x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '">' + f.name + ' ' + (cc.counts[f.name] || 0) + '</text>';
    });
    svg += '</svg>';
    host.innerHTML = svg;
    host.querySelectorAll('path.city').forEach((p) => p.addEventListener('click', () => {
      state.citySel = state.citySel === p.dataset.city ? '' : p.dataset.city;
      state.filters.city = state.citySel;
      syncCitySelect();
      state.page = 1;
      refreshTable();
      renderMap();
    }));
const mode = document.getElementById('wyall-map-mode');
const floorSuffix = cc.floorLabel ? '（' + cc.floorLabel + '可报）' : '';
if (mode) mode.textContent = cc.mode === 'major' ? '当前口径：专业「' + state.mapMajor + '」' + floorSuffix + '可报（' + cc.total + ' 岗）' : (cc.mode === 'profile' ? '当前口径：画像可报数（' + cc.total + ' 岗）' : '当前口径：全部专业（' + ROWS.length + ' 岗）');
    const legend = document.getElementById('wyall-map-legend');
    if (legend) legend.innerHTML = '岗位数：' + PALETTE.map((c) => '<i style="background:' + c + '"></i>').join('') + ' 多';
    const side = document.getElementById('wyall-mapside');
    if (side) {
      const sorted = MAP.slice().sort((a, b) => (cc.counts[b.name] || 0) - (cc.counts[a.name] || 0));
      let h = '<h2 style="font-size:15px;margin:0 0 8px">' + (cc.mode === 'major' ? '各市可报（专业「' + state.mapMajor + '」' + floorSuffix + '）' : cc.mode === 'profile' ? '各市可报（画像已生效）' : '各市岗位数（全部专业）') + '</h2>';
      sorted.forEach((f) => {
        const n = cc.counts[f.name] || 0;
        h += '<div class="wyall-bar" data-city="' + f.name + '"><span class="n">' + f.name + '</span><span class="track"><span class="fill" style="width:' + (n / maxN * 100) + '%"></span></span><b>' + n + ' 岗/' + (cc.rec[f.name] || 0) + ' 人</b></div>';
      });
      h += '<div class="wyall-exbar"><span class="chip">省直 ' + (cc.counts['省直'] || 0) + ' 岗（非地图区域）</span></div>';
      side.innerHTML = h;
      side.querySelectorAll('.wyall-bar').forEach((bar) => bar.addEventListener('click', () => {
        state.citySel = bar.dataset.city; state.filters.city = bar.dataset.city; syncCitySelect(); state.page = 1; refreshTable();
      }));
    }
  }

  function syncCitySelect() { const sel = document.getElementById('wyall-city'); if (sel) sel.value = state.citySel; }

  /* ---------------- 全岗位库 ---------------- */
  function applyFilters(rows) {
    const f = state.filters, kw = f.kw.trim();
    return rows.filter((r) => {
      if (f.exam && r.exam !== f.exam) return false;
      if (state.citySel && r.city !== state.citySel) return false;
      if (f.city && r.city !== f.city) return false;
      if (f.lb && r.lb !== f.lb) return false;
      if (f.xl && r.xl.indexOf(f.xl) < 0) return false;
      if (f.tag === 'directed' && !r.dir) return false;
      if (f.tag === 'hukou' && !r.hukou) return false;
      if (f.tag && f.tag !== 'directed' && f.tag !== 'hukou' && r.tags.indexOf(f.tag) < 0) return false;
      if (kw && (r.unit + r.zw + r.zy + r.qt + r.jl + r.bz + r.code).indexOf(kw) < 0) return false;
      return true;
    });
  }

  function filteredRows() {
    return applyFilters(ROWS);
  }

  function refreshTable() {
    const profileMode = state.profile.active && state.lastMatch;
    const base = profileMode ? state.lastMatch.rows : ROWS;
    const rows = applyFilters(base);
    root.innerHTML = renderTable(rows, profileMode);
    const count = document.getElementById('wyall-count');
if (count) count.textContent = profileMode ? '画像可报 ' + state.lastMatch.rows.length + ' 岗，当前筛选后 ' + rows.length + ' 岗' : '共 ' + rows.length + ' 条岗位（筛选与关键词实时生效）';
root.querySelectorAll('tr.wyall-row').forEach((tr) => tr.addEventListener('click', () => openDetail(tr.dataset.code, tr.dataset.city, tr.dataset.exam, true)));
    root.querySelectorAll('.wyall-pager button').forEach((b) => b.addEventListener('click', () => {
      state.page = parseInt(b.dataset.page, 10); refreshTable(); window.scrollTo(0, 0);
    }));
    renderMap();
  }

  function refreshSummary() {
    const box = document.getElementById('wyall-matchsum');
    if (!box) return;
    if (!(state.profile.active && state.lastMatch)) { box.hidden = true; box.innerHTML = ''; return; }
    const m = state.lastMatch;
    const exTotal = Object.keys(m.ex).reduce((a, k) => a + m.ex[k], 0);
    let h = '<div class="wyall-stat ok"><b>' + m.rows.length + '</b><span>可报岗位</span></div>' +
      '<div class="wyall-stat acc"><b>' + m.rows.reduce((a, r) => a + r.num, 0) + '</b><span>可报招录人数</span></div>' +
      '<div class="wyall-stat bad"><b>' + exTotal + '</b><span>被排除岗位</span></div>';
    box.innerHTML = h;
    box.hidden = false;
    const state2 = document.getElementById('wyall-profile-state');
    if (state2) state2.textContent = '画像已生效 · 地图着色已同步为可报口径';
  }

  /* ---------------- 专业自动补全 ---------------- */
  function setupMajorCombo() {
    const input = document.getElementById('wyall-p-major');
    const list = document.getElementById('wyall-major-list');
    if (!input || !list) return;
    const options = majorOptions();
    const categoryOptions = new Set((META.cats || []).map(cleanMajorOption).filter(isHumanMajor));
    let items = [];
    function renderList(q) {
      const needle = normMajor(q);
      items = needle ? options.filter((o) => normMajor(o).indexOf(needle) >= 0).slice(0, 40) : options.slice(0, 40);
      if (!items.length) { list.hidden = true; input.setAttribute('aria-expanded', 'false'); return; }
      list.innerHTML = items.map((o) => '<button type="button" role="option" data-v="' + esc(o) + '">' + esc(o) + '</button>').join('');
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      list.querySelectorAll('button').forEach((b) => b.addEventListener('mousedown', (e) => {
        e.preventDefault();
        input.value = b.dataset.v;
        list.hidden = true;
        input.setAttribute('aria-expanded', 'false');
        if (categoryOptions.has(b.dataset.v)) {
          const cat = document.getElementById('wyall-p-cat');
          if (cat) cat.value = b.dataset.v;
        }
      }));
    }
    input.addEventListener('focus', () => renderList(input.value));
    input.addEventListener('input', () => renderList(input.value));
    input.addEventListener('blur', () => { setTimeout(() => { list.hidden = true; input.setAttribute('aria-expanded', 'false'); }, 160); });
    input.addEventListener('keydown', (e) => {
      if (list.hidden) return;
      const btns = [...list.querySelectorAll('button')];
      let idx = btns.findIndex((b) => b.classList.contains('is-on'));
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        idx = e.key === 'ArrowDown' ? (idx + 1) % btns.length : (idx - 1 + btns.length) % btns.length;
        btns.forEach((b) => b.classList.remove('is-on'));
        btns[idx].classList.add('is-on');
        btns[idx].scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'Enter') {
        e.preventDefault();
        (btns[idx] || btns[0]).dispatchEvent(new Event('mousedown'));
      } else if (e.key === 'Escape') { list.hidden = true; }
    });
  }

  function bindAll() {
    const run = document.getElementById('wyall-run');
    if (!run) return;
    run.addEventListener('click', () => {
      const p = state.profile;
      p.major = document.getElementById('wyall-p-major').value;
      p.cat = document.getElementById('wyall-p-cat').value;
      p.xl = document.getElementById('wyall-p-xl').value;
      p.gender = document.getElementById('wyall-p-gender').value;
      p.hukouCity = document.getElementById('wyall-p-hukou').value;
      ['fresh', 'party', 'cert', 'sp', 'vet', 'fam'].forEach((k) => { p[k] = document.getElementById('wyall-p-' + k).checked; });
      if (!p.cat && p.major) p.cat = guessCat(p.major);
      if (p.cat) { const catSel = document.getElementById('wyall-p-cat'); if (catSel && !catSel.value) catSel.value = p.cat; }
      p.active = !!(p.major || p.cat);
      saveProfile();
      state.lastMatch = matchedRows();
      state.page = 1;
      refreshSummary();
      refreshTable();
    });
    document.getElementById('wyall-reset').addEventListener('click', () => {
      state.profile = loadProfile(); Object.keys(state.profile).forEach((k) => { if (typeof state.profile[k] === 'boolean') state.profile[k] = false; state.profile[k] = ['major', 'cat', 'gender', 'hukouCity'].indexOf(k) >= 0 ? '' : (k === 'xl' ? 'benke' : false); });
      state.profile.active = false; saveProfile(); state.lastMatch = null;
      ['wyall-p-major'].forEach((id) => { const n = document.getElementById(id); if (n) n.value = ''; });
      ['fresh', 'party', 'cert', 'sp', 'vet', 'fam'].forEach((k) => { const n = document.getElementById('wyall-p-' + k); if (n) n.checked = false; });
      document.getElementById('wyall-p-cat').value = '';
      document.getElementById('wyall-profile-state').textContent = '';
      refreshSummary(); refreshTable();
    });
    const kw = document.getElementById('wyall-kw');
    kw.addEventListener('input', () => { state.filters.kw = kw.value; state.page = 1; refreshTable(); });
    ['wyall-exam', 'wyall-city', 'wyall-lb', 'wyall-xl', 'wyall-tag'].forEach((id) => {
      document.getElementById(id).addEventListener('change', () => {
        state.filters.exam = document.getElementById('wyall-exam').value;
        state.filters.city = document.getElementById('wyall-city').value;
        state.citySel = state.filters.city;
        state.filters.lb = document.getElementById('wyall-lb').value;
        state.filters.xl = document.getElementById('wyall-xl').value;
        state.filters.tag = document.getElementById('wyall-tag').value;
        state.page = 1; refreshTable();
      });
    });
    document.getElementById('wyall-csv').addEventListener('click', () => {
      const base = state.profile.active && state.lastMatch ? state.lastMatch.rows : ROWS;
      csvExport(applyFilters(base));
    });
  }

if (META.total) {
setupMajorCombo();
const mapInput = document.getElementById('wyall-map-major');
const mapList = document.getElementById('wyall-map-major-list');
if (mapList) mapList.innerHTML = majorOptions().map((value) => '<option value="' + esc(value) + '"></option>').join('');
if (mapInput) {
const applyMapMajor = () => { state.mapMajor = String(mapInput.value || '').trim(); state.page = 1; refreshTable(); renderMap(); };
let majorDebounce = 0;
mapInput.addEventListener('change', applyMapMajor);
mapInput.addEventListener('input', () => { clearTimeout(majorDebounce); majorDebounce = setTimeout(applyMapMajor, 260); });
mapInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); clearTimeout(majorDebounce); applyMapMajor(); } });
}
const floorSel = document.getElementById('wyall-map-floor');
if (floorSel) floorSel.addEventListener('change', () => { state.page = 1; refreshTable(); renderMap(); });
/* 总览「按专业匹配」口径变化时，岗位地图同步跟随（同专业只播一次，尊重手动清除） */
let seededMapMajor = null;
document.addEventListener('wanyu:caliber-changed', () => {
  const mc = window.wanyuMasterCaliber || {};
  if (mc.caliber !== 'major' || !mc.major) { seededMapMajor = null; return; }
  if (seededMapMajor === mc.major) return;
  seededMapMajor = mc.major;
  state.mapMajor = mc.major;
  const mi = document.getElementById('wyall-map-major');
  if (mi && document.activeElement !== mi) mi.value = mc.major;
  state.page = 1;
  refreshTable();
  renderMap();
});
document.getElementById('wyall-map-major-clear')?.addEventListener('click', () => { state.mapMajor = ''; const mi = document.getElementById('wyall-map-major'); if (mi) mi.value = ''; state.page = 1; refreshTable(); renderMap(); });
bindAll();
    if (state.profile.active) {
      state.lastMatch = matchedRows();
      document.getElementById('wyall-p-major').value = state.profile.major;
      document.getElementById('wyall-p-cat').value = state.profile.cat;
      document.getElementById('wyall-p-xl').value = state.profile.xl;
      document.getElementById('wyall-p-gender').value = state.profile.gender;
      document.getElementById('wyall-p-hukou').value = state.profile.hukouCity;
      ['fresh', 'party', 'cert', 'sp', 'vet', 'fam'].forEach((k) => { const n = document.getElementById('wyall-p-' + k); if (n) n.checked = !!state.profile[k]; });
      refreshSummary();
    }
    refreshTable();
  }

  /* ---------------- 对外暴露：总览“专业匹配”口径复用 ---------------- */
  window.wanyuAllMatch = {
    majors: majorOptions(),
    cats: [...new Set((META.cats || []).map(cleanMajorOption).filter(isHumanMajor))].sort((a, b) => a.localeCompare(b, 'zh')),
    csMembers: (META.csMembers || []).slice(),
    benkeFloor: 3,
  match: (row, major) => {
    if (!major) return true;
    const nm = normMajor(major);
    if (!nm) return true;
    if (row.unlim) return true;
    const items = zyItems(row);
    if (items.some((it) => it.indexOf('不限') >= 0)) return true;
    if (!row.zy && row.exam && row.exam !== '省考') return true; // 档案口径豁免
    const cat = normMajor(guessCat(major));
    const cats = catalogFor(nm).map(bareOf);
    for (const it of items) {
      const bare = bareOf(it);
      if (!bare) continue;
      if (cat && bare === cat) return true;
      if (cats.length && cats.indexOf(bare) >= 0) return true; // 目录：专业所属大类
      if (bare === nm || bare.indexOf(nm) >= 0) return true;
    }
    if ((META.csMembers || []).indexOf(nm) >= 0 && items.some((it) => it.indexOf('计算机类') >= 0)) return true;
    return false;
  },
    floorOk: (row) => (row.floor || 0) <= 3, // 本科及以上口径
  };
})();

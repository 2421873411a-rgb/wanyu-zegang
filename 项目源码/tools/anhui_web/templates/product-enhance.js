(() => {
  /* 皖域择岗 · 增强层 v9：画像引擎 / 设置(主题·字号·对比度) / 焦点陷阱 / 命令面板(NL) / 分享码 / 多画像 / 名词与来源 */
  const data = window.productData || {};
  const PROFILE_KEY = 'wanyu.profile.v1';
  const PROFILES_KEY = 'wanyu.profiles.v1';
  const FILTER_KEY = 'wanyu.searchFilters.v1';
  const STATE_KEYS = ['wanyu.jobCompare.v1', 'wanyu.jobSaved.v1', 'wanyu.cityShortlist.v1', 'wanyu.jobNotes.v1', 'wanyu.jobGroups.v1', 'wanyu.registrationOverrides.v1', 'wanyu.matchWeights.v1', 'wanyu.simSchemes.v1', 'wanyu.simState.v1', PROFILE_KEY];
  const THEME_KEY = 'wanyu.theme.v1';
  const SETTINGS_KEY = 'wanyu.settings.v1';

  const TAG_LABELS = {
    four_project: '四项目定向', veteran: '退役士兵定向', military_family: '随军家属定向', targeted: '其他定向',
    fresh_only: '仅应届', gender_male: '限男性', gender_female: '限女性', party: '中共党员',
    cert_legal: '法律职业资格', min_service: '最低服务期', allowance_diff: '差额补贴', night_shift: '夜班/值班', prof_test: '专业测试',
  };
  const TAG_TO_PROFILE = {
    four_project: 'four_project', veteran: 'veteran', military_family: 'military_family',
    fresh_only: 'fresh', gender_male: 'male', gender_female: 'female', party: 'party', cert_legal: 'cert_legal',
  };
  const PROFILE_FIELDS = [
    ['four_project', '我是“服务基层项目”人员（四项目：村官/三支一扶/西部计划/特岗）'],
    ['veteran', '我是退役士兵（含普通高校毕业生入伍）'],
    ['military_family', '我是随军家属'],
    ['fresh', '我是应届毕业生（含择业期内）'],
    ['male', '男性'],
    ['female', '女性'],
    ['party', '我是中共党员'],
    ['cert_legal', '我有法律职业资格证书'],
  ];

  const loadProfile = () => {
    try {
      const stored = JSON.parse(localStorage.getItem(PROFILE_KEY) || '{}');
      const profile = { strict: Boolean(stored.strict) };
      PROFILE_FIELDS.forEach(([key]) => { profile[key] = Boolean(stored[key]); });
      return profile;
    } catch { const profile = { strict: false }; PROFILE_FIELDS.forEach(([key]) => { profile[key] = false; }); return profile; }
  };
  const profile = loadProfile();
  const persistProfile = () => { try { localStorage.setItem(PROFILE_KEY, JSON.stringify(profile)); } catch {} };

  const IDENTITY_TAGS = ['four_project', 'veteran', 'military_family', 'targeted'];
  const SOFT_TAGS = ['fresh_only', 'gender_male', 'gender_female', 'party', 'cert_legal'];
  const evaluateTags = (tagString) => {
    const tags = String(tagString || '').split(/\s+/).filter(Boolean);
    const reasons = [];
    tags.forEach((tag) => {
      if (IDENTITY_TAGS.includes(tag)) {
        const profileKey = TAG_TO_PROFILE[tag];
        if (!profileKey || !profile[profileKey]) reasons.push(TAG_LABELS[tag] || tag);
        return;
      }
      if (profile.strict && SOFT_TAGS.includes(tag)) {
        const profileKey = TAG_TO_PROFILE[tag];
        if (!profileKey || !profile[profileKey]) reasons.push(TAG_LABELS[tag] || tag);
      }
    });
    return { ok: reasons.length === 0, reasons, tags };
  };

  window.wanyuEligibility = {
    profile,
    TAG_LABELS,
    evaluate: evaluateTags,
    setProfileKey(key, value) { if (key in profile) { profile[key] = Boolean(value); persistProfile(); document.dispatchEvent(new CustomEvent('wanyu:profile-changed')); } },
  };

  /* —— 轻量浮层组件（含焦点陷阱与焦点归还） —— */
  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])';
  const openOverlay = (title, bodyHtml, options = {}) => {
    document.querySelector('.wanyu-overlay')?.remove();
    const opener = document.activeElement;
    const wrap = document.createElement('div');
    wrap.className = 'wanyu-overlay';
    wrap.innerHTML = '<div class="wanyu-dialog" role="dialog" aria-modal="true" aria-label="' + title + '">'
      + '<header><strong>' + title + '</strong><button type="button" class="wanyu-dialog__close" aria-label="关闭">×</button></header>'
      + '<div class="wanyu-dialog__body">' + bodyHtml + '</div>'
      + (options.footer ? '<footer>' + options.footer + '</footer>' : '')
      + '</div>';
    document.body.appendChild(wrap);
    const close = () => { wrap.remove(); document.removeEventListener('keydown', trapKey, true); if (opener instanceof Element && document.contains(opener)) opener.focus({ preventScroll: true }); };
    const trapKey = (event) => {
      if (event.key === 'Escape') { event.stopPropagation(); close(); return; }
      if (event.key !== 'Tab') return;
      const nodes = [...wrap.querySelectorAll(FOCUSABLE)].filter((node) => node.offsetParent !== null || node === document.activeElement);
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      else if (!wrap.contains(document.activeElement)) { event.preventDefault(); first.focus(); }
    };
    wrap.addEventListener('click', (event) => { if (event.target === wrap) close(); });
    wrap.querySelector('.wanyu-dialog__close').addEventListener('click', close);
    document.addEventListener('keydown', trapKey, true);
    options.onMount?.(wrap, close);
    setTimeout(() => { (wrap.querySelector('input, select, textarea, button:not(.wanyu-dialog__close)') || wrap.querySelector('.wanyu-dialog__close'))?.focus({ preventScroll: true }); }, 30);
    return wrap;
  };
  window.wanyuOverlay = openOverlay;

  /* —— 设置：主题三态 / 字号三档 / 高对比度（本地持久化） —— */
  const settings = Object.assign({ theme: 'light', font: 'standard', contrast: false }, (() => { try { return JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}'); } catch { return {}; } })());
  const applySettings = () => {
    document.body.classList.toggle('paper-mode', settings.theme === 'paper');
    if (settings.theme === 'dark') document.body.dataset.theme = 'dark'; else delete document.body.dataset.theme;
    document.body.dataset.fontsize = settings.font;
    document.body.classList.toggle('contrast-high', Boolean(settings.contrast));
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); } catch {}
  };
  const openSettings = () => {
    const body = '<p class="wanyu-dialog__lead">阅读偏好只保存在本机浏览器。</p>'
      + '<div class="settings-group"><span>主题</span><div class="segmented" role="group" aria-label="主题">'
      + [['light', '清爽'], ['paper', '纸张'], ['dark', '夜间']].map(([key, label]) => '<button type="button" data-set-theme="' + key + '"' + (settings.theme === key ? ' class="is-selected"' : '') + '>' + label + '</button>').join('') + '</div></div>'
      + '<div class="settings-group"><span>字号</span><div class="segmented" role="group" aria-label="字号">'
      + [['standard', '标准'], ['large', '大'], ['xlarge', '特大']].map(([key, label]) => '<button type="button" data-set-font="' + key + '"' + (settings.font === key ? ' class="is-selected"' : '') + '>' + label + '</button>').join('') + '</div></div>'
      + '<label class="profile-check"><input type="checkbox" data-set-contrast' + (settings.contrast ? ' checked' : '') + '><span>高对比度（加深文字与边框）</span></label>';
    openOverlay('显示设置', body, {
      onMount(wrap) {
        wrap.querySelectorAll('[data-set-theme]').forEach((button) => button.addEventListener('click', () => {
          settings.theme = button.dataset.setTheme;
          applySettings();
          wrap.querySelectorAll('[data-set-theme]').forEach((item) => item.classList.toggle('is-selected', item === button));
        }));
        wrap.querySelectorAll('[data-set-font]').forEach((button) => button.addEventListener('click', () => {
          settings.font = button.dataset.setFont;
          applySettings();
          wrap.querySelectorAll('[data-set-font]').forEach((item) => item.classList.toggle('is-selected', item === button));
        }));
        wrap.querySelector('[data-set-contrast]')?.addEventListener('change', (event) => { settings.contrast = event.target.checked; applySettings(); });
      },
    });
  };
  applySettings();

  /* —— 我的条件（画像面板，含多方案） —— */
  const profilesStore = () => { try { return JSON.parse(localStorage.getItem(PROFILES_KEY) || '{}') || {}; } catch { return {}; } };
  const renderBadgeStates = () => {
    document.querySelectorAll('#jobs-search-table tbody tr[data-excluded="1"]').forEach((row) => {
      const badge = row.querySelector('[data-role="excluded-badge"]');
      if (!badge) return;
      const verdict = evaluateTags(row.dataset.tags);
      badge.classList.toggle('is-ok', verdict.ok);
      badge.textContent = verdict.ok ? '定向·符合你的身份' : '定向·不可报';
    });
  };
  document.addEventListener('wanyu:profile-changed', () => {
    renderBadgeStates();
    document.querySelectorAll('[data-profile-summary]').forEach((node) => { node.textContent = profileSummaryText(); });
    const input = document.querySelector('#job-search');
    if (input) input.dispatchEvent(new Event('input', { bubbles: false }));
  });
  const profileSummaryText = () => {
    const on = PROFILE_FIELDS.filter(([key]) => profile[key]).map(([, label]) => label);
    const mode = profile.strict ? '严格模式' : '定向类必拦 · 其余放行';
    return (on.length ? on.join(' · ') : '未设置身份条件') + '（' + mode + '）';
  };

  const openProfile = () => {
    const saved = profilesStore();
    const body = '<p class="wanyu-dialog__lead">勾选你的身份后，检索、对比与分数模拟会自动按资格过滤；被核除的定向岗若与你身份相符会恢复显示并标绿。</p>'
      + '<div class="profile-grid">' + PROFILE_FIELDS.map(([key, label]) => (
        '<label class="profile-check"><input type="checkbox" data-profile-key="' + key + '"' + (profile[key] ? ' checked' : '') + '><span>' + label + '</span></label>'
      )).join('') + '</div>'
      + '<label class="profile-check profile-check--strict"><input type="checkbox" data-profile-strict' + (profile.strict ? ' checked' : '') + '><span><strong>严格模式</strong>：未勾选的应届 / 性别 / 党员 / 法律资格限制也按不可报拦截（默认只拦截身份定向类）</span></label>'
      + '<div class="profile-schemes"><label><span>保存当前条件为方案</span><input id="profile-scheme-name" type="text" placeholder="例如：我的条件 / 帮同学查"></label>'
      + '<select id="profile-scheme-list" aria-label="已存方案">' + (Object.keys(saved).length ? Object.keys(saved).map((name) => '<option>' + name + '</option>').join('') : '<option value="">暂无已存方案</option>') + '</select>'
      + '<button type="button" class="text-button" id="profile-scheme-load">载入</button><button type="button" class="text-button" id="profile-scheme-del">删除</button></div>'
      + '<p class="wanyu-dialog__note" data-profile-summary>' + profileSummaryText() + '</p>';
    openOverlay('我的条件', body, {
      footer: '<button type="button" class="text-button" id="profile-share">复制分享链接</button><button type="button" class="text-button" id="profile-export">导出全部本地状态</button><button type="button" class="text-button" id="profile-import">导入状态</button><button type="button" class="text-button" id="profile-clear">清空条件</button>',
      onMount(wrap, close) {
        wrap.querySelectorAll('[data-profile-key]').forEach((input) => {
          input.addEventListener('change', () => window.wanyuEligibility.setProfileKey(input.dataset.profileKey, input.checked));
        });
        wrap.querySelector('[data-profile-strict]')?.addEventListener('change', (event) => {
          profile.strict = event.target.checked;
          persistProfile();
          document.dispatchEvent(new CustomEvent('wanyu:profile-changed'));
        });
        wrap.querySelector('#profile-scheme-save')?.remove();
        wrap.querySelector('#profile-scheme-load')?.addEventListener('click', () => {
          const name = wrap.querySelector('#profile-scheme-list').value;
          const state = profilesStore()[name];
          if (!state) return;
          PROFILE_FIELDS.forEach(([key]) => { profile[key] = Boolean(state[key]); });
          profile.strict = Boolean(state.strict);
          persistProfile();
          wrap.querySelectorAll('[data-profile-key]').forEach((input) => { input.checked = Boolean(profile[input.dataset.profileKey]); });
          const strict = wrap.querySelector('[data-profile-strict]');
          if (strict) strict.checked = profile.strict;
          document.dispatchEvent(new CustomEvent('wanyu:profile-changed'));
        });
        wrap.querySelector('#profile-scheme-del')?.addEventListener('click', () => {
          const name = wrap.querySelector('#profile-scheme-list').value;
          if (!name) return;
          const store2 = profilesStore();
          delete store2[name];
          try { localStorage.setItem(PROFILES_KEY, JSON.stringify(store2)); } catch {}
          wrap.querySelector('#profile-scheme-list').querySelector('option[value="' + name + '"]')?.remove();
        });
        wrap.querySelector('#profile-scheme-name')?.addEventListener('change', (event) => {
          const name = String(event.target.value || '').trim();
          if (!name) return;
          const store2 = profilesStore();
          store2[name] = { ...profile };
          try { localStorage.setItem(PROFILES_KEY, JSON.stringify(store2)); } catch {}
          const list = wrap.querySelector('#profile-scheme-list');
          if (list && ![...list.options].some((option) => option.textContent === name)) list.appendChild(new Option(name, name));
          event.target.value = '';
        });
        wrap.querySelector('#profile-clear').addEventListener('click', () => {
          PROFILE_FIELDS.forEach(([key]) => { profile[key] = false; });
          profile.strict = false;
          const strictInput = wrap.querySelector('[data-profile-strict]');
          if (strictInput) strictInput.checked = false;
          persistProfile();
          wrap.querySelectorAll('[data-profile-key]').forEach((input) => { input.checked = false; });
          document.dispatchEvent(new CustomEvent('wanyu:profile-changed'));
        });
        wrap.querySelector('#profile-share').addEventListener('click', () => shareState(close));
        wrap.querySelector('#profile-export').addEventListener('click', exportState);
        wrap.querySelector('#profile-import').addEventListener('click', importState);
      },
    });
  };
  document.getElementById('open-profile')?.addEventListener('click', openProfile);

  /* —— 状态导入导出 + 分享码 —— */
  const exportState = () => {
    const payload = { app: 'wanyu', version: 2, exportedAt: new Date().toISOString(), state: {} };
    STATE_KEYS.forEach((key) => { try { const raw = localStorage.getItem(key); if (raw) payload.state[key] = JSON.parse(raw); } catch {} });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 1)], { type: 'application/json' }));
    link.download = '皖域择岗-本地状态.json';
    link.click();
    URL.revokeObjectURL(link.href);
  };
  const importState = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';
    input.addEventListener('change', async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const payload = JSON.parse(await file.text());
        if (payload.app !== 'wanyu' || !payload.state) throw new Error('bad file');
        Object.entries(payload.state).forEach(([key, value]) => { if (STATE_KEYS.includes(key)) localStorage.setItem(key, JSON.stringify(value)); });
        location.reload();
      } catch { alert('导入失败：文件不是本产品导出的状态 JSON。'); }
    });
    input.click();
  };
  const shareState = (close) => {
    const core = window.wanyuCore || {};
    const state = { filters: null, shortlist: null, profile: null, weights: null };
    try { state.filters = JSON.parse(localStorage.getItem(FILTER_KEY) || 'null'); } catch {}
    try { state.shortlist = JSON.parse(localStorage.getItem('wanyu.cityShortlist.v1') || 'null'); } catch {}
    try { state.profile = JSON.parse(localStorage.getItem(PROFILE_KEY) || 'null'); } catch {}
    try { state.weights = JSON.parse(localStorage.getItem('wanyu.matchWeights.v1') || 'null'); } catch {}
    const code = core.encodeShare ? core.encodeShare(state) : '';
    if (!code) { alert('分享码生成失败'); return; }
    const url = location.origin.startsWith('http') ? location.origin + location.pathname + '#share=' + code : location.pathname + '#share=' + code;
    const finish = () => { if (close) close(); openOverlay('分享链接已生成', '<p class="wanyu-dialog__lead">对方用任意浏览器打开这个链接，会自动载入你的筛选条件、城市短名单、身份条件与适配度权重。</p><textarea id="share-url" rows="3" readonly>' + url + '</textarea><p class="wanyu-dialog__note">链接只包含条件设置，不包含收藏岗位；如需完整状态请用“导出全部本地状态”。</p>', { onMount(wrap) { const area = wrap.querySelector('#share-url'); area?.select(); try { navigator.clipboard.writeText(url); } catch {} } }); };
    finish();
  };
  const restoreFromShare = () => {
    const match = /[#&]share=([A-Za-z0-9\-_]+)/.exec(location.hash || '');
    if (!match) return false;
    const core = window.wanyuCore || {};
    const state = core.decodeShare ? core.decodeShare(match[1]) : null;
    if (!state) return false;
    try { if (state.profile) localStorage.setItem(PROFILE_KEY, JSON.stringify(state.profile)); } catch {}
    try { if (state.filters) localStorage.setItem(FILTER_KEY, JSON.stringify(state.filters)); } catch {}
    try { if (state.shortlist) localStorage.setItem('wanyu.cityShortlist.v1', JSON.stringify(state.shortlist)); } catch {}
    try { if (state.weights) localStorage.setItem('wanyu.matchWeights.v1', JSON.stringify(state.weights)); } catch {}
    history.replaceState({}, '', location.pathname + location.search);
    return true;
  };
  if (restoreFromShare()) { location.reload(); return; }

  /* —— 名词解释与数据来源（词条可由构建注入） —— */
  const GLOSSARY = Array.isArray(data.glossary) && data.glossary.length
    ? data.glossary
    : [
      ['有效笔试/达线', '成绩达到最低入围线的人数，是竞争比的首选分母；缺失时回退报名人数并在排名页以 ≈ 标记。'],
      ['最低入围/线', '进入下一环节（资格复审/面试）的最低笔试成绩；事业单位联考满分为 300，省考合成成绩（行测+申论÷2）满分为 100。'],
      ['核减', '报名或缴费达不到开考比例被取消/削减的招录计划；职位库中“核减后人数”为最终招录数。'],
      ['递补', '前排人员放弃资格后，按成绩依次补录。'],
      ['差额补贴', '经费来源为差额拨款的事业单位岗位，待遇稳定性弱于全额拨款。'],
      ['专业测试', '部分岗位在笔试外另设专业测试（如六安“专业测试2”），影响总成绩构成。'],
      ['四项目', '服务基层项目人员：大学生村官、“三支一扶”、西部计划志愿者、特岗教师。'],
      ['员额制', '不属于传统事业编的用人方式（如合肥新站高新区岗位），本档案已排除。'],
    ];
  const openGlossary = () => {
    const sources = [...new Set((data.records || []).map((record) => record?.eligibility?.source_url).filter(Boolean))];
    const body = '<input id="glossary-search" type="search" placeholder="搜索名词…" autocomplete="off">'
      + '<p class="wanyu-dialog__lead">名词解释</p><dl class="glossary-list" data-glossary-list>'
      + GLOSSARY.map(([term, desc]) => '<div data-glossary-term="' + term + '"><dt>' + term + '</dt><dd>' + desc + '</dd></div>').join('') + '</dl>'
      + (sources.length ? '<p class="wanyu-dialog__lead">资格核验来源（' + sources.length + ' 个页面）</p><ul class="source-list">'
        + sources.slice(0, 60).map((url) => '<li><a href="' + url + '" target="_blank" rel="noreferrer">' + url.replace(/^https?:\/\//, '') + '</a></li>').join('')
        + '</ul><p class="wanyu-dialog__note">省考 406 条另与省直 + 16 市职位表逐条比对；完整方法见交付包《定向岗核查报告》。</p>' : '');
    openOverlay('名词与数据来源', body, {
      onMount(wrap) {
        const input = wrap.querySelector('#glossary-search');
        input?.addEventListener('input', () => {
          const q = input.value.trim().toLowerCase();
          wrap.querySelectorAll('[data-glossary-term]').forEach((node) => {
            node.hidden = Boolean(q) && !node.textContent.toLowerCase().includes(q);
          });
        });
      },
    });
  };

  /* —— 快捷键帮助 —— */
  const openHelp = () => {
    const rows = [
      ['Ctrl / Alt + K 或 /', '打开命令面板（搜岗位 / 切视图 / 筛选）'],
      ['j / k', '检索表中向下 / 向上移动'],
      ['s / c', '收藏 / 加入对比当前行'],
      ['Esc', '关闭浮层；检索框内清空关键词'],
      ['?', '打开本帮助'],
    ];
    openOverlay('快捷键与技巧', '<p class="wanyu-dialog__lead">键盘流</p><dl class="glossary-list">' + rows.map(([key, desc]) => '<div><dt>' + key + '</dt><dd>' + desc + '</dd></div>').join('') + '</dl>'
      + '<p class="wanyu-dialog__lead">小技巧</p><ul class="wanyu-help-tips">'
      + '<li>检索表点「1:N」小徽标可在报名期手动修正竞争分母。</li>'
      + '<li>收藏卡可写私人笔记、分组，并用「找平替」查同口径更优岗位。</li>'
      + '<li>分数模拟里把「发挥波动」调高，可看每个岗位的进面概率估计。</li>'
      + '<li>「我的条件 → 复制分享链接」可把筛选与画像发给研友。</li></ul>');
  };

  /* —— 工具按钮注入导航 —— */
  const navTools = document.querySelector('.product-nav__tools');
  if (navTools) {
    const makeButton = (id, title, html) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.id = id;
      button.title = title;
      button.innerHTML = html;
      return button;
    };
    const paletteButton = makeButton('nav-palette', '命令面板（Ctrl+K）', '<span aria-hidden="true">⌘</span><small>搜索</small>');
    const profileButton = makeButton('nav-profile', '我的条件（身份画像）', '<span aria-hidden="true">⚙</span><small>条件</small>');
    const helpButton = makeButton('nav-glossary', '名词解释与数据来源', '<span aria-hidden="true">？</span><small>名词</small>');
    const settingsButton = makeButton('nav-settings', '显示设置（主题 / 字号 / 对比度）', '<span aria-hidden="true">Aa</span><small>显示</small>');
    settingsButton.addEventListener('click', openSettings);
    paletteButton.addEventListener('click', () => openPalette());
    profileButton.addEventListener('click', () => openProfile());
    helpButton.addEventListener('click', () => openGlossary());
    navTools.prepend(settingsButton);
    navTools.prepend(helpButton);
    navTools.prepend(profileButton);
    navTools.prepend(paletteButton);
  } else {
    document.getElementById('open-profile')?.addEventListener('click', openProfile);
  }

  /* —— 命令面板（支持多关键词：城市 / 类别 / 代码） —— */
  const CITY_NAMES = [...new Set([
    ...((data.cities || []).map((item) => String(item.city || item))),
    ...((data.jobs?.cities || []).map((item) => String(item.city))),
  ])].filter(Boolean);
  const EXAM_NAMES = ['省考', '事业单位', '国考'];
  const applyFilterCombo = (cityName, examName) => {
    location.hash = '#jobs_search';
    setTimeout(() => {
      const citySelect = document.querySelector('#city-filter');
      const examSelect = document.querySelector('#exam-filter-search');
      if (citySelect && cityName) { citySelect.value = cityName; citySelect.dispatchEvent(new Event('change', { bubbles: true })); }
      if (examSelect && examName) { examSelect.value = examName; examSelect.dispatchEvent(new Event('change', { bubbles: true })); }
    }, 90);
  };
  const paletteItems = () => {
    const items = [];
    document.querySelectorAll('[data-view-link]').forEach((tab) => {
      items.push({ kind: '视图', label: tab.textContent.trim(), hint: '切换视图', run: () => { location.hash = '#' + tab.dataset.viewLink; } });
    });
    const records = Array.isArray(data.records) ? data.records : [];
    items.push({ kind: '工具', label: '⚙ 我的条件', hint: '身份画像过滤', run: openProfile });
    items.push({ kind: '工具', label: '？名词解释与来源', hint: '口径与依据', run: openGlossary });
    const query = () => String(document.getElementById('palette-input')?.value || '').trim().toLowerCase();
    const comboMatches = () => {
      const q = query();
      if (!q || q.indexOf(' ') < 0) return [];
      const tokens = q.split(/\s+/);
      const cityName = CITY_NAMES.find((name) => tokens.some((token) => name.toLowerCase().startsWith(token) || token === name.toLowerCase())) || '';
      const examName = EXAM_NAMES.find((name) => tokens.some((token) => name.toLowerCase().startsWith(token))) || '';
      if (!cityName && !examName) return [];
      return [{ kind: '筛选', label: '筛选：' + (cityName ? cityName + '市' : '') + (cityName && examName ? ' · ' : '') + (examName || ''), hint: '组合条件应用到岗位检索', run: () => applyFilterCombo(cityName, examName) }];
    };
    const jobMatches = (limit) => {
      const q = query().replace(/\s+/g, '');
      if (!q || !records.length) return [];
      const scored = [];
      for (const record of records) {
        const code = String(record.code || '');
        const unit = String(record.unit_position || '');
        const city = String(record.city || '');
        let score = -1;
        if (code.startsWith(q)) score = 100;
        else if (code.includes(q)) score = 80;
        else if (unit.toLowerCase().includes(q)) score = 60;
        else if (city.includes(q)) score = 40;
        else if ((record.exam || '').includes(q)) score = 30;
        if (score > 0) scored.push({ record, score });
      }
      scored.sort((a, b) => b.score - a.score);
      return scored.slice(0, limit).map(({ record }) => ({
        kind: '岗位',
        label: record.code + ' · ' + record.unit_position,
        hint: record.city + '市 · ' + record.exam + ' · 招' + record.recruits,
        run: () => {
          if (!document.querySelector('#jobs-search-table')) return;
          location.hash = '#jobs_search';
          setTimeout(() => {
            const input = document.querySelector('#job-search');
            if (!input) return;
            input.value = String(record.code);
            input.dispatchEvent(new Event('input', { bubbles: false }));
            document.querySelector('#jobs-search-table')?.scrollIntoView({ block: 'start' });
          }, 80);
        },
      }));
    };
    return { items, jobMatches, comboMatches };
  };
  const openPalette = () => {
    if (document.querySelector('.wanyu-palette')) return;
    const opener = document.activeElement;
    const wrap = document.createElement('div');
    wrap.className = 'wanyu-overlay wanyu-palette';
    wrap.innerHTML = '<div class="wanyu-dialog wanyu-dialog--palette" role="dialog" aria-modal="true" aria-label="命令面板">'
      + '<input id="palette-input" type="text" placeholder="搜岗位代码 / 单位，或“合肥 事业编”组合筛选，回车执行…" autocomplete="off">'
      + '<div class="palette-list" id="palette-list" role="listbox"></div>'
      + '<footer><small>↑↓ 选择 · 回车执行 · Esc 关闭</small></footer></div>';
    document.body.appendChild(wrap);
    const input = wrap.querySelector('#palette-input');
    const list = wrap.querySelector('#palette-list');
    let cursor = 0;
    let current = [];
    const close = () => { wrap.remove(); if (opener instanceof Element && document.contains(opener)) opener.focus({ preventScroll: true }); };
    const render = () => {
      const { items, jobMatches, comboMatches } = paletteItems();
      const combos = comboMatches();
      const jobs = jobMatches(8);
      current = (input.value.trim() ? [...combos, ...jobs, ...items.filter((item) => item.label.toLowerCase().includes(input.value.trim().toLowerCase())).slice(0, 6)] : items.slice(0, 9));
      cursor = Math.min(cursor, Math.max(0, current.length - 1));
      list.innerHTML = current.map((item, index) => '<button type="button" role="option" class="palette-item' + (index === cursor ? ' is-active' : '') + '" data-palette-index="' + index + '"><span class="palette-kind">' + item.kind + '</span><strong>' + item.label + '</strong><small>' + item.hint + '</small></button>').join('')
        || '<p class="palette-empty">没有匹配项</p>';
      list.querySelectorAll('[data-palette-index]').forEach((button) => {
        button.addEventListener('click', () => { close(); current[Number(button.dataset.paletteIndex)]?.run(); });
      });
    };
    input.addEventListener('input', render);
    input.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') { event.preventDefault(); cursor = Math.min(cursor + 1, current.length - 1); render(); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); cursor = Math.max(cursor - 1, 0); render(); }
      else if (event.key === 'Enter') { const item = current[cursor]; close(); item?.run(); }
      else if (event.key === 'Escape') { close(); }
    });
    wrap.addEventListener('click', (event) => { if (event.target === wrap) close(); });
    render();
    input.focus();
  };
  document.addEventListener('keydown', (event) => {
    const target = event.target;
    const editable = target instanceof Element && (target.matches('input, textarea, select') || target.isContentEditable);
    if ((event.ctrlKey || event.altKey) && (event.key === 'k' || event.key === 'K')) { event.preventDefault(); openPalette(); }
    else if (event.key === '/' && !editable && target instanceof Element) { event.preventDefault(); openPalette(); }
    else if (event.key === '?' && !editable && target instanceof Element) { event.preventDefault(); openHelp(); }
  });

  /* —— 检索筛选持久化（先于检索脚本执行，恢复输入框取值） —— */
  const restoreFilters = () => {
    try {
      const stored = JSON.parse(localStorage.getItem(FILTER_KEY) || '{}');
      const search = document.querySelector('#job-search');
      const city = document.querySelector('#city-filter');
      const exam = document.querySelector('#exam-filter-search');
      if (stored.q && search) search.value = String(stored.q);
      if (stored.city && city && [...city.options].some((option) => option.value === stored.city)) city.value = String(stored.city);
      if (stored.exam && exam) exam.value = String(stored.exam);
      window.__wanyuRestoredTags = Array.isArray(stored.tags) ? stored.tags : [];
      window.__wanyuBulkCodes = Array.isArray(stored.codes) ? stored.codes : [];
    } catch {}
  };
  restoreFilters();
  const persistFilters = () => {
    try {
      const search = document.querySelector('#job-search');
      const city = document.querySelector('#city-filter');
      const exam = document.querySelector('#exam-filter-search');
      localStorage.setItem(FILTER_KEY, JSON.stringify({
        q: search?.value || '', city: city?.value || '', exam: exam?.value || '',
        tags: window.__wanyuActiveTags || [], codes: window.__wanyuBulkCodes || [],
      }));
    } catch {}
  };
  window.wanyuPersistFilters = persistFilters;
  document.addEventListener('input', (event) => { if (event.target?.matches?.('#job-search, #city-filter, #exam-filter-search')) persistFilters(); });
  document.addEventListener('change', (event) => { if (event.target?.matches?.('#city-filter, #exam-filter-search')) persistFilters(); });

  /* —— 标签筛选 chips + 批量代码（与检索脚本协作） —— */
  window.__wanyuActiveTags = window.__wanyuRestoredTags || [];
  document.querySelectorAll('[data-tag-filter]').forEach((chip) => {
    const tag = chip.dataset.tagFilter;
    if (window.__wanyuActiveTags.includes(tag)) chip.classList.add('is-active');
    chip.addEventListener('click', () => {
      const set = new Set(window.__wanyuActiveTags);
      if (set.has(tag)) set.delete(tag); else set.add(tag);
      window.__wanyuActiveTags = [...set];
      chip.classList.toggle('is-active', set.has(tag));
      persistFilters();
      document.querySelector('#job-search')?.dispatchEvent(new Event('input', { bubbles: false }));
    });
  });
  const updateBulkChip = () => {
    const button = document.getElementById('clear-bulk-codes');
    if (!button) return;
    const count = (window.__wanyuBulkCodes || []).length;
    button.classList.toggle('is-hidden', count === 0);
    button.textContent = '已限定 ' + count + ' 个代码 ×';
  };
  updateBulkChip();
  document.getElementById('clear-bulk-codes')?.addEventListener('click', () => {
    window.__wanyuBulkCodes = [];
    updateBulkChip();
    persistFilters();
    document.querySelector('#job-search')?.dispatchEvent(new Event('input', { bubbles: false }));
  });
  document.getElementById('bulk-codes')?.addEventListener('click', () => {
    openOverlay('批量代码限定', '<p class="wanyu-dialog__lead">粘贴一批岗位代码——从 Excel 直接复制一列也没问题，空格 / 逗号 / 换行都会自动拆分。检索将只显示这些岗位。</p><textarea id="bulk-codes-input" rows="6" placeholder="例如：0801046 0202007 120005"></textarea><p class="wanyu-dialog__note" id="bulk-codes-count">识别到 0 个代码</p>', {
      footer: '<button type="button" class="primary-button" id="bulk-codes-apply">应用限定</button>',
      onMount(wrap, close) {
        const area = wrap.querySelector('#bulk-codes-input');
        const countNode = wrap.querySelector('#bulk-codes-count');
        area.value = (window.__wanyuBulkCodes || []).join(' ');
        const update = () => {
          const parsed = [...new Set(area.value.split(/[^0-9A-Za-z]+/).filter(Boolean))];
          countNode.textContent = '识别到 ' + parsed.length + ' 个代码';
        };
        area.addEventListener('input', update);
        update();
        wrap.querySelector('#bulk-codes-apply').addEventListener('click', () => {
          window.__wanyuBulkCodes = [...new Set(area.value.split(/[^0-9A-Za-z]+/).filter(Boolean))];
          updateBulkChip();
          persistFilters();
          close();
          document.querySelector('#job-search')?.dispatchEvent(new Event('input', { bubbles: false }));
        });
      },
    });
  });

  /* —— 图表存 PNG（SVG → canvas） —— */
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-export-svg]');
    if (!button) return;
    const svg = document.querySelector(button.dataset.exportSvg);
    if (!svg || !svg.viewBox) return;
    const xml = new XMLSerializer().serializeToString(svg);
    const url = URL.createObjectURL(new Blob([xml], { type: 'image/svg+xml;charset=utf-8' }));
    const image = new Image();
    image.onload = () => {
      const scale = 2;
      const canvas = document.createElement('canvas');
      canvas.width = svg.viewBox.baseVal.width * scale;
      canvas.height = svg.viewBox.baseVal.height * scale;
      const context = canvas.getContext('2d');
      if (context) {
        context.fillStyle = '#ffffff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const link = document.createElement('a');
        link.href = canvas.toDataURL('image/png');
        link.download = (svg.getAttribute('aria-label') || '图表') + '.png';
        link.click();
      }
      URL.revokeObjectURL(url);
    };
    image.onerror = () => URL.revokeObjectURL(url);
    image.src = url;
  });

  /* —— 报考手册：名词搜索 —— */
  const manualSearch = document.querySelector('#manual-search');
  if (manualSearch) {
    const terms = [...document.querySelectorAll('.manual-term')];
    const emptyTip = document.querySelector('#manual-search-empty');
    manualSearch.addEventListener('input', () => {
      const q = manualSearch.value.trim().toLowerCase();
      let visible = 0;
      terms.forEach((node) => {
        const hit = !q || node.textContent.toLowerCase().includes(q);
        node.hidden = !hit;
        if (hit) visible += 1;
      });
      if (emptyTip) emptyTip.hidden = visible > 0;
    });
  }

  /* —— 考试日历倒计时（按预计窗口起点，本机日期实时计算） —— */
  document.querySelectorAll('[data-countdown-date]').forEach((node) => {
    const target = new Date(node.dataset.countdownDate + 'T00:00:00');
    if (Number.isNaN(target.getTime())) return;
    const days = Math.ceil((target.getTime() - Date.now()) / 86400000);
    node.textContent = days > 0 ? '约 ' + days.toLocaleString('en-US') + ' 天' : days === 0 ? '就是今天' : '已过（参考）';
  });

  /* —— 首访引导：三步浮层，只出现一次（wanyu.onboarded.v1） —— */
  const ONBOARD_KEY = 'wanyu.onboarded.v1';
  const store = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key) || fallback); } catch { return null; } };
  const markOnboarded = () => { try { localStorage.setItem(ONBOARD_KEY, JSON.stringify({ at: new Date().toISOString() })); } catch {} };
  const openOnboarding = () => {
    const steps = [
      { title: '第 1 步 · 设置我的条件', text: '勾选身份（应届 / 党员 / 证书等），检索、模拟与对比会自动按资格过滤；身份不符的定向岗已为你核除。', actionLabel: '打开「我的条件」', action: openProfile },
      { title: '第 2 步 · 模拟你的分数', text: '在「分数模拟」拖动两科滑杆，按源表入围线得到 稳 / 达线 / 贴线 / 差分 清单；调高“发挥波动”还能看进面概率。', actionLabel: '去分数模拟', action: () => { location.hash = '#score_sim'; } },
      { title: '第 3 步 · 收藏对比出决策', text: '检索里点 ☆ 收藏、＋加入对比；收藏页可一键生成可打印的报考决策单，把想法落到纸面。', actionLabel: '开始选岗', action: () => { location.hash = '#jobs_search'; } },
    ];
    let index = 0;
    let wrap = null;
    const stepBody = () => {
      const step = steps[index];
      return '<div class="onboard__step"><p class="eyebrow">ONBOARDING · 三步上手</p><h3>' + step.title + '</h3><p class="wanyu-dialog__lead">' + step.text + '</p>'
        + '<button type="button" class="primary-button primary-button--quiet" data-onboard-action>' + step.actionLabel + '</button></div>'
        + '<div class="onboard__dots" aria-hidden="true">' + steps.map((_, dotIndex) => '<i class="' + (dotIndex === index ? 'is-active' : '') + '"></i>').join('') + '</div>';
    };
    const stepFooter = () => '<button type="button" class="text-button" id="onboard-skip">跳过引导</button>'
      + (index > 0 ? '<button type="button" class="text-button" id="onboard-prev">上一步</button>' : '')
      + '<button type="button" class="primary-button" id="onboard-next">' + (index < steps.length - 1 ? '下一步' : '完成') + '</button>';
    const bind = () => {
      wrap.querySelector('[data-onboard-action]')?.addEventListener('click', () => steps[index].action?.());
      wrap.querySelector('#onboard-skip')?.addEventListener('click', () => wrap.querySelector('.wanyu-dialog__close')?.click());
      wrap.querySelector('#onboard-prev')?.addEventListener('click', () => { index = Math.max(0, index - 1); render(); });
      wrap.querySelector('#onboard-next')?.addEventListener('click', () => {
        if (index < steps.length - 1) { index += 1; render(); return; }
        steps[index].action?.();
        wrap.querySelector('.wanyu-dialog__close')?.click();
      });
    };
    const render = () => {
      if (!wrap) wrap = openOverlay('欢迎使用皖域择岗档案', stepBody(), { footer: stepFooter() });
      else {
        wrap.querySelector('.wanyu-dialog__body').innerHTML = stepBody();
        wrap.querySelector('footer').innerHTML = stepFooter();
      }
      bind();
    };
    render();
    const observer = new MutationObserver(() => {
      if (!document.contains(wrap)) { markOnboarded(); observer.disconnect(); }
    });
    observer.observe(document.body, { childList: true });
  };
  if (!store(ONBOARD_KEY, 'null') && Array.isArray(data.records) && data.records.length) {
    // 用户已在操作（有浮层打开）就让路，最多重试两次
    const tryOnboard = (attempt) => {
      if (document.querySelector('.wanyu-overlay')) {
        if (attempt < 2) setTimeout(() => tryOnboard(attempt + 1), 3000);
        return;
      }
      openOnboarding();
    };
    setTimeout(() => tryOnboard(0), 700);
  }

  renderBadgeStates();
})();

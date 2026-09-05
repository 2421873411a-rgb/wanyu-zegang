(() => {
  /* v12 data bridge: expose every allMajors row through the legacy record API. */
  const data = window.productData || {};
  const rows = Array.isArray(data.allMajors?.rows) ? data.allMajors.rows : [];
  if (!rows.length) return;
  const cycle = String(data.cycleRuntime?.cycle || data.cycleInfo?.cycle || data.allMajors?.meta?.cycle || '');
  const existing = Array.isArray(data.records) ? data.records : [];
  const examName = (value) => String(value || '') === '事业编' ? '事业单位' : String(value || '省考');
  const richByKey = new Map(existing.map((record) => [
    [record.city, examName(record.exam), record.code, record.recruits].map((value) => String(value ?? '')).join('|'),
    record,
  ]));
  const valueOrDash = (value) => value === null || value === undefined || value === '' ? '—' : value;
  const natureRules = [
    ['grassroots', '乡镇街道', /乡镇|街道/], ['law', '执法警务', /执法|稽查|公安|监狱|戒毒|警察|司法所|派出所/],
    ['office', '文秘综合', /办公室|文秘|综合|秘书|文字|宣传/], ['finance', '财会审计', /会计|财务|财会|审计|出纳/],
    ['tech', '计算机信息', /计算机|信息|大数据|网络|软件|数据/], ['legal', '法律法务', /法学|法律|法务/],
    ['engineer', '工程规划', /工程|规划|建设|建筑|市政|水利|交通/], ['medical', '医疗卫生', /医[院师疗护]|卫生|疾控|康复|药/],
    ['education', '教育文化', /教育|教师|师范|文化|旅游|广电|体育|文物/], ['econ', '经济金融', /金融|经济|统计|证券|投资|招商/],
  ];
  const derivedNatures = (row) => natureRules.filter(([, , pattern]) => pattern.test(`${row.unit || ''} ${row.zw || ''} ${row.lb || ''}`)).slice(0, 3).map(([key, label]) => ({ key, label }));
  const fieldMap = (row) => {
    const title = String(row.zw || '').trim() || '源表未单列披露';
    return {
    '代码': row.code,
    '市': row.city,
    '考试类别': row.exam || '省考',
    '单位 · 职位': [row.unit, row.zw].filter(Boolean).join(' · '),
    '招录': row.num,
    '报名*': valueOrDash(row.bm),
    '审查合格*': valueOrDash(row.hg),
    '有效笔试/达线/规模参考': valueOrDash(row.adv),
    '最低入围/线': valueOrDash(row.line),
    '最高笔试': valueOrDash(row.top),
    '拟录用参考（笔试/总成绩）': [row.hq, row.ht].map(valueOrDash).join(' / '),
    '机构性质': row.xz,
    '层级': row.cc,
    '职位类别': row.lb,
    '职位名称': title,
    '职级层次': row.zj,
    '学历': row.xl,
    '学位': row.xw,
    '年龄': row.age,
    '专业要求': row.zy,
    '经历要求': row.jl,
    '其他条件': row.qt,
    '申论/专业科目': [row.sl, row.km].filter(Boolean).join(' / '),
    '职位简介': row.bz,
    '官方备注': row.officialRemark || '',
    '咨询电话': row.dh,
    '来源': row.source_note,
    };
  };
  data.records = rows.map((row, index) => {
    const normalizedExam = examName(row.exam);
    const key = [row.city, normalizedExam, row.code, row.num].map((value) => String(value ?? '')).join('|');
    const rich = richByKey.get(key) || {};
    const competition = row.competition_observations || {
      registrations: { value: row.bm ?? null, status: row.bm == null ? 'unavailable' : 'observed' },
      examinees: { value: row.adv ?? null, status: row.adv == null ? 'unavailable' : 'observed' },
      preferred_type: row.adv != null ? 'examinees' : row.bm != null ? 'registrations' : null,
    };
    const preferredType = competition.preferred_type || (normalizedExam === '国考' && row.adv != null ? 'interview_shortlisted' : row.adv != null ? 'examinees' : row.bm != null ? 'registrations' : null);
    const recordId = String(row.row_id || `${cycle}-${String(index + 1).padStart(5, '0')}-${row.code || index + 1}`);
    const sourceFields = fieldMap(row);
    const titleStatus = row.title_status || (String(row.zw || '').trim() ? 'published' : 'not_separately_published');
    const displayTitle = String(row.zw || '').trim() || '源表未单列披露';
    return Object.assign({}, row, rich, {
      record_id: recordId,
      cycle,
      city: row.city || rich.city || '',
      exam: normalizedExam || examName(rich.exam),
      code: String(row.code || rich.code || ''),
      unit_position: [row.unit, row.zw].filter(Boolean).join(' · ') || rich.unit_position || '—',
      recruits: row.num ?? rich.recruits ?? 0,
      registrations: row.bm ?? rich.registrations ?? null,
      examinees: row.adv ?? rich.examinees ?? null,
      competition_base: row.adv ?? row.bm ?? rich.competition_base ?? null,
      competition_source: row.adv != null ? '有效笔试/达线/进面人数' : row.bm != null ? '报名人数' : (rich.competition_source || '未发布'),
      competition_metric_type: preferredType,
      competition_observations: competition,
      score_observation: row.score_observation || rich.score_observation || null,
      title_status: titleStatus,
      display_title: displayTitle,
      eligibility: Object.assign({ tags: Array.isArray(row.tags) ? row.tags : [] }, rich.eligibility || {}),
      natures: Array.isArray(rich.natures) && rich.natures.length ? rich.natures : derivedNatures(row),
      fields: Object.assign({}, rich.fields || {}, sourceFields, { '职位名称': displayTitle }),
      exclusion: rich.exclusion || null,
      source_row: index + 1,
      title: rich.title || displayTitle,
    });
  });
})();

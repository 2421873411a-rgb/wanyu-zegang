/**
 * v17-tools.js - 竞争热力图和城市对比工具
 * 与主站筛选联动：examFilter = '全部' | '公务员' | '事业编'（公务员 = 省考 + 国考）
 * 城市归并逻辑与主站一致：县级条目归入所属地级市
 *
 * 审计 FE-004 口径对齐：
 *  1) 只统计 active 行（record_status 生命周期与主站 isActiveRow 同义）——排除行不入任何分母；
 *  2) 竞争比只在「官方公布报名人数」的岗位子集上计算并标注覆盖率，未公布不推断。
 */
(() => {
  'use strict';

  const PREFECTURES = ['合肥', '芜湖', '蚌埠', '淮南', '马鞍山', '淮北', '铜陵', '安庆', '黄山', '滁州', '阜阳', '宿州', '六安', '亳州', '池州', '宣城'];

  /** 归并到地级市；省直单独保留；无法归并返回 null */
  const normalizeCity = (value) => {
    const city = String(value || '').trim();
    if (!city) return null;
    if (city === '省直') return '省直';
    if (city === '宿松') return '安庆';
    if (city === '广德') return '宣城';
    return PREFECTURES.find((candidate) => city === candidate || city.startsWith(candidate)) || null;
  };

  const cityLabel = (city) => (city === '省直' ? '省直' : `${city}市`);

  // 与主站 isActiveRow 同义（maintainable-site.js）：用户产品统计只认 active
  const isActiveRow = (row) => !row || !row.record_status || row.record_status === 'active';

  // 与主站 hasObservedCompetition 同义：只认官方公布（status==='observed'）的报名人数
  const observedExaminees = (row) => {
    const observations = row?.competition_observations;
    if (!observations || typeof observations !== 'object') return 0;
    const preferred = observations.preferred_type ? observations[observations.preferred_type] : (observations.examinees || null);
    if (!preferred || preferred.status !== 'observed') return 0;
    const value = Number(preferred.value ?? 0);
    return Number.isFinite(value) && value > 0 ? value : 0;
  };

  /** 活行集合 + 按考试口径过滤（公务员 = 省考 + 国考；事业编可按联考上下半年细分） */
  const filterRowsByExam = (rows, examFilter, examSub = '') => rows.filter(isActiveRow).filter((r) => {
    const exam = String(r.exam || '');
    if (examFilter === '公务员' && !(exam.includes('省考') || exam.includes('国考'))) return false;
    if (examFilter === '事业编' && !exam.includes('事业')) return false;
    if (examSub === '国考' && !exam.includes('国考')) return false;
    if (examSub === '省考' && !exam.includes('省考')) return false;
    if ((examSub === '上半年' || examSub === '下半年') && String(r.cycle || '') !== examSub) return false;
    return true;
  });

  /**
   * 生成竞争热力图HTML
   */
  window.renderCompetitionHeatmap = (jobs, cycle, examFilter = '全部', examSub = '') => {
    const cityStats = {};
    const rows = filterRowsByExam(jobs?.allMajors?.rows || [], examFilter, examSub);

    rows.forEach(row => {
      const city = normalizeCity(row.city);
      if (!city) return;
      if (!cityStats[city]) {
        cityStats[city] = { jobs: 0, recruits: 0, observedJobs: 0, observedRecruits: 0, observedExaminees: 0 };
      }
      const stats = cityStats[city];
      const recruits = Number(row.num ?? row.recruits ?? 0);
      stats.jobs++;
      stats.recruits += recruits;
      const examinees = observedExaminees(row);
      if (examinees > 0) {
        stats.observedJobs++;
        stats.observedRecruits += recruits;
        stats.observedExaminees += examinees;
      }
    });

    const cities = Object.entries(cityStats)
      .map(([city, stats]) => ({
        city,
        ...stats,
        // 审计 FE-004：分母只取有官方观测的岗位，覆盖率（observedJobs/jobs）随行标注
        ratio: stats.observedRecruits > 0 ? (stats.observedExaminees / stats.observedRecruits).toFixed(1) : null
      }))
      .sort((a, b) => (Number(b.ratio) || 0) - (Number(a.ratio) || 0));

    if (!cities.length) {
      return `<section class="maint-panel"><header><div><h2>各城市竞争热度</h2></div></header><p class="empty">当前筛选下暂无岗位数据</p></section>`;
    }

    const maxRatio = Math.max(...cities.map(c => Number(c.ratio) || 0));

    const rowsHtml = cities.map((city, idx) => {
      let level = 'easy';
      if (city.ratio >= 8) { level = 'fierce'; }
      else if (city.ratio >= 4) { level = 'high'; }
      else if (city.ratio >= 2) { level = 'medium'; }
      const emoji = { fierce: '🔥', high: '🟠', medium: '🟡', easy: '✅' }[level];
      const label = { fierce: '竞争激烈', high: '竞争较大', medium: '竞争适中', easy: '竞争较小' }[level];

      const barWidth = city.ratio ? (Number(city.ratio) / maxRatio * 100) : 0;
      const tip = city.ratio
        ? `${label} · 官方观测覆盖 ${city.observedJobs}/${city.jobs} 岗`
        : '官方未逐岗公布竞争人数，不做推断';
      const coverage = city.ratio ? `<span class="heatmap-coverage">${city.observedJobs}/${city.jobs}岗</span>` : '';

      return `<div class="heatmap-row" title="${tip}">
        <span class="heatmap-rank">${idx + 1}</span>
        <span class="heatmap-city">${cityLabel(city.city)}</span>
        <div class="heatmap-bar"><div class="heatmap-bar__fill heatmap-bar__fill--${level}" style="width:${barWidth}%"></div></div>
        <span class="heatmap-ratio">${city.ratio ? city.ratio + ':1' : '—'}${coverage}</span>
        <span class="heatmap-jobs">${city.jobs}岗</span>
        <span class="heatmap-emoji">${emoji}</span>
      </div>`;
    }).join('');

    const examLabel = examFilter === '全部' && !examSub ? '' : `（${examFilter}${examSub ? ` · ${examSub}` : ''}）`;
    return `<section class="maint-panel"><header><div><h2>各城市竞争热度${examLabel}</h2></div></header><div class="heatmap">${rowsHtml}</div><p class="heatmap-hint">竞争比 = 官方公布报名人数 ÷ 招录人数，仅统计官方逐岗公布报名人数的岗位（行内 n/M 为观测覆盖），未公布不推断；"—" 表示该城市暂无公布观测。统计口径只含 active 岗位。</p></section>`;
  };

  /**
   * 生成城市对比表格HTML（响应考试类别筛选）
   */
  window.renderCityComparison = (jobs, salary, cycle, examFilter = '全部', examSub = '') => {
    const rows = filterRowsByExam(jobs?.allMajors?.rows || [], examFilter, examSub);

    // 按归并后的城市统计
    const cityStats = {};
    rows.forEach(row => {
      const city = normalizeCity(row.city);
      if (!city) return;
      if (!cityStats[city]) cityStats[city] = { jobs: 0, recruits: 0 };
      cityStats[city].jobs++;
      cityStats[city].recruits += Number(row.num ?? row.recruits ?? 0);
    });

    const salaryData = salary?.series || {};
    const gwyData = salaryData['公务员'] || {};
    const sybData = salaryData['事业编'] || {};

    const cities = Object.entries(cityStats)
      .map(([city, stats]) => ({
        city,
        label: cityLabel(city),
        jobs: stats.jobs,
        recruits: stats.recruits,
        gwySalary: gwyData[city]?.['3年'] || '—',
        sybSalary: sybData[city]?.['3年'] || '—'
      }))
      .sort((a, b) => b.jobs - a.jobs)
      .slice(0, 10);

    if (!cities.length) {
      return `<section class="maint-panel"><header><div><h2>各城市岗位数对比</h2></div></header><p class="empty">当前筛选下暂无岗位数据</p></section>`;
    }

    const tableRows = cities.map(c => `<tr>
      <th>${c.label}</th>
      <td>${c.jobs}</td>
      <td>${c.recruits}</td>
      <td>${c.gwySalary !== '—' ? c.gwySalary + '万' : '—'}</td>
      <td>${c.sybSalary !== '—' ? c.sybSalary + '万' : '—'}</td>
    </tr>`).join('');

    const examLabel = examFilter === '全部' && !examSub ? '' : `（${examFilter}${examSub ? ` · ${examSub}` : ''}）`;

    return `<section class="maint-panel"><header><div><h2>各城市岗位数对比${examLabel}</h2></div></header><div class="table-scroll"><table class="maint-table"><thead><tr><th>城市</th><th>岗位数</th><th>招录人数</th><th>公务员(3年)</th><th>事业编(3年)</th></tr></thead><tbody>${tableRows}</tbody></table></div></section>`;
  };

})();

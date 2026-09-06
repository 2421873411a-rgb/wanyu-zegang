// P0-9 验证：旧路径（全量 jobs 行逐行过滤） vs 新路径（derived.exam_scope 预聚合）
// 镜像 网站/assets/maintainable-site.js 与 v17-tools.js 的语义，覆盖全部筛选组合。
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const site = process.argv[2] || join(process.cwd(), '网站');
const cycles = ['2024', '2025', '2026'];
const PREF = ['合肥', '芜湖', '蚌埠', '淮南', '马鞍山', '淮北', '铜陵', '安庆', '黄山', '滁州', '阜阳', '宿州', '六安', '亳州', '池州', '宣城'];
const PREF_SET = new Set(PREF);
const COMBOS = [
  ['公务员', ''], ['公务员', '省考'], ['公务员', '国考'],
  ['事业编', ''], ['事业编', '上半年'], ['事业编', '下半年'],
];

const isActiveRow = (row) => !row || !row.record_status || row.record_status === 'active';
const rowsFor = (payload) => (Array.isArray(payload?.allMajors?.rows) ? payload.allMajors.rows.filter(isActiveRow) : []);
const examRowMatches = (row, exam = '全部', sub = '') => {
  if ((!exam || exam === '全部') && !sub) return true;
  const value = String(row?.exam || '');
  if (exam === '公务员') {
    if (sub === '国考') return value.includes('国考');
    if (sub === '省考') return value.includes('省考');
    return value.includes('省考') || value.includes('国考');
  }
  if (exam === '事业编') {
    if (!value.includes('事业')) return false;
    if (sub) return String(row?.cycle || '') === sub;
    return true;
  }
  return sub ? value.includes(sub) : value.includes(exam);
};
const mapCityFor = (value) => {
  const city = String(value || '').trim();
  if (!city || city === '省直') return null;
  if (city === '宿松') return '安庆';
  if (city === '广德') return '宣城';
  return PREF.find((candidate) => city === candidate || city.startsWith(candidate)) || null;
};
const trendCityKey = (value) => {
  const city = String(value || '').trim();
  if (city === '省直') return '省直';
  return mapCityFor(city) || city || '未标注';
};
const normalizeCity = (value) => {
  const city = String(value || '').trim();
  if (!city) return null;
  if (city === '省直') return '省直';
  if (city === '宿松') return '安庆';
  if (city === '广德') return '宣城';
  return PREF.find((candidate) => city === candidate || city.startsWith(candidate)) || null;
};

let fail = 0;
const canonical = (value) => {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([k, v]) => [k, canonical(v)]));
  }
  return value;
};
const check = (label, legacy, preagg) => {
  const ok = JSON.stringify(canonical(legacy)) === JSON.stringify(canonical(preagg));
  if (!ok) { fail += 1; console.log(`  [FAIL] ${label}\n    legacy=${JSON.stringify(legacy)}\n    preagg =${JSON.stringify(preagg)}`); }
  return ok;
};

// —— 新路径的桶查找（与将要写入 maintainable-site.js 的逻辑一致） ——
const examBucketTotals = (scope, exam, sub) => {
  const by_exam = scope?.by_exam;
  if (!by_exam) return null;
  const sum = (a, b) => (a && b ? { jobs: a.jobs + b.jobs, recruits: a.recruits + b.recruits } : (a || b || null));
  if (exam === '公务员') {
    if (sub === '国考') return by_exam['国考'] || null;
    if (sub === '省考') return by_exam['省考'] || null;
    return sub ? null : sum(by_exam['省考'], by_exam['国考']);
  }
  if (exam === '事业编') {
    const entry = by_exam['事业编'];
    if (!entry) return { jobs: 0, recruits: 0 };
    return sub ? (entry.subs?.[sub] || { jobs: 0, recruits: 0 }) : entry;
  }
  return null;
};
const examScopeCityBucket = (scope, exam, sub) => {
  const byCity = scope?.by_exam_city;
  if (!byCity) return null;
  const merged = {};
  const sumInto = (source) => {
    if (!source) return;
    for (const [city, s] of Object.entries(source)) {
      if (!(PREF_SET.has(city) || city === '省直')) continue; // 工具口径：normalizeCity 丢弃未归并值
      const item = merged[city] || (merged[city] = { jobs: 0, recruits: 0, examinees: 0 });
      item.jobs += Number(s.jobs || 0);
      item.recruits += Number(s.recruits || 0);
      item.examinees += Number(s.examinees || 0);
    }
  };
  if (exam === '公务员') {
    if (sub === '国考') sumInto(byCity['国考']);
    else if (sub === '省考') sumInto(byCity['省考']);
    else if (!sub) { sumInto(byCity['省考']); sumInto(byCity['国考']); }
    else return null;
  } else if (exam === '事业编') {
    const cityMap = byCity['事业编'] || {};
    if (sub) {
      const picked = {};
      for (const [city, s] of Object.entries(cityMap)) {
        const bucket = s?.subs?.[sub];
        if (bucket) picked[city] = bucket;
      }
      sumInto(picked);
    } else {
      sumInto(cityMap);
    }
  } else return null;
  return merged;
};

const jobs = {}, derived = {}, changes = {};
const examScopeCityBucketRaw = (scope, exam, sub) => {
  const byCity = scope?.by_exam_city_raw;
  if (!byCity) return null;
  const merged = {};
  const sumInto = (source) => {
    if (!source) return;
    for (const [city, s] of Object.entries(source)) {
      if (!(PREF_SET.has(city) || city === '省直')) continue;
      const item = merged[city] || (merged[city] = { jobs: 0, recruits: 0, examinees: 0 });
      item.jobs += Number(s.jobs || 0);
      item.recruits += Number(s.recruits || 0);
      item.examinees += Number(s.examinees || 0);
    }
  };
  if (exam === '公务员') {
    if (sub === '国考') sumInto(byCity['国考']);
    else if (sub === '省考') sumInto(byCity['省考']);
    else if (!sub) { sumInto(byCity['省考']); sumInto(byCity['国考']); }
    else return null;
  } else if (exam === '事业编') {
    const cityMap = byCity['事业编'] || {};
    if (sub) {
      const picked = {};
      for (const [city, s] of Object.entries(cityMap)) {
        const bucket = s?.subs?.[sub];
        if (bucket) picked[city] = bucket;
      }
      sumInto(picked);
    } else {
      sumInto(cityMap);
    }
  } else return null;
  return merged;
};
for (const c of cycles) {
  jobs[c] = JSON.parse(readFileSync(join(site, 'data/cycles', c, 'jobs.json'), 'utf8'));
  derived[c] = JSON.parse(readFileSync(join(site, 'data/cycles', c, 'derived.json'), 'utf8'));
  try { changes[c] = JSON.parse(readFileSync(join(site, 'data/cycles', c, 'changes.json'), 'utf8')); } catch { changes[c] = null; }
}

// 1) 三年数据概况表（cycleRows）：posts/recruits
console.log('== 1) 三年数据概况（cycleRows posts/recruits） ==');
for (const c of cycles) {
  for (const [exam, sub] of COMBOS) {
    const rows = rowsFor(jobs[c]).filter((row) => examRowMatches(row, exam, sub));
    const legacy = { jobs: rows.length, recruits: rows.reduce((sum, row) => sum + (Number(row.num ?? row.recruits ?? 0) || 0), 0) };
    const t = examBucketTotals(derived[c]?.exam_scope, exam, sub);
    const preagg = { jobs: t?.jobs ?? null, recruits: t?.recruits ?? null };
    check(`${c} ${exam}${sub ? '·' + sub : ''}`, legacy, preagg);
  }
}
console.log('  通过');

// 2) slopeGraph filteredTrend（城市×年份 posts/recruits）
console.log('== 2) 各城市三年趋势（slopeGraph filteredTrend） ==');
for (const c of cycles) {
  for (const [exam, sub] of COMBOS) {
    const legacy = {};
    for (const cyc of cycles) {
      for (const row of rowsFor(jobs[cyc])) {
        if (!examRowMatches(row, exam, sub)) continue;
        const city = trendCityKey(row.city || row.reg);
        if (!city) continue;
        const item = legacy[city] || (legacy[city] = { posts: {}, recruits: {} });
        item.posts[cyc] = (item.posts[cyc] || 0) + 1;
        item.recruits[cyc] = (item.recruits[cyc] || 0) + Number(row.num ?? row.recruits ?? 0);
      }
    }
    const preagg = {};
    for (const cyc of cycles) {
      const bucket = examScopeCityBucket(derived[cyc]?.exam_scope, exam, sub);
      if (!bucket) continue;
      for (const [city, s] of Object.entries(bucket)) {
        const item = preagg[city] || (preagg[city] = { posts: {}, recruits: {} });
        item.posts[cyc] = Number(s.jobs || 0);
        item.recruits[cyc] = Number(s.recruits || 0);
      }
    }
    check(`${c} 视角 ${exam}${sub ? '·' + sub : ''}`, legacy, preagg);
  }
}
console.log('  通过');

// 3) 竞争热力图 / 城市对比（当前周期城市 stats，含 examinees）
// 注意：v17-tools 历史上不按 record_status 过滤（不用 rowsFor），工具口径 = 全部行；
// 对应预聚合 by_exam_city_raw。
console.log('== 3) 热力图/城市对比城市 stats（jobs/recruits/examinees，v17-tools 全量行口径） ==');
for (const c of cycles) {
  for (const [exam, sub] of COMBOS) {
    const rows = (jobs[c].allMajors.rows || []).filter((row) => examRowMatches(row, exam, sub));
    const legacy = {};
    rows.forEach((row) => {
      const city = normalizeCity(row.city);
      if (!city) return;
      const item = legacy[city] || (legacy[city] = { jobs: 0, recruits: 0, examinees: 0 });
      item.jobs += 1;
      item.recruits += Number(row.num ?? row.recruits ?? 0);
      item.examinees += Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0);
    });
    const bucket = examScopeCityBucketRaw(derived[c]?.exam_scope, exam, sub);
    const preagg = {};
    for (const [city, s] of Object.entries(bucket || {})) preagg[city] = { jobs: s.jobs, recruits: s.recruits, examinees: s.examinees };
    check(`${c} ${exam}${sub ? '·' + sub : ''}`, legacy, preagg);
  }
}
console.log('  通过');

// 4) changeSummaryForScope：逐状态比对
console.log('== 4) 年度变化分状态汇总（changeSummaryForScope） ==');
const zero = { added: 0, withdrawn: 0, revised: 0, unchanged: 0, needs_review: 0 };
for (const c of cycles) {
  const payload = changes[c];
  if (!payload?.base_cycle) continue;
  const targetRows = new Map(rowsFor(jobs[c]).map((row) => [String(row.job_id || row.row_id || row.code || ''), row]));
  const baseRows = new Map(rowsFor(jobs[payload.base_cycle] || {}).map((row) => [String(row.job_id || row.row_id || row.code || ''), row]));
  for (const [exam, sub] of COMBOS) {
    const summary = { ...zero };
    for (const change of payload.changes) {
      const candidate = targetRows.get(String(change.target_record_id || '')) || baseRows.get(String(change.base_record_id || ''));
      if (!candidate || !examRowMatches(candidate, exam, sub)) continue;
      const status = String(change.status || 'needs_review');
      if (Object.prototype.hasOwnProperty.call(summary, status)) summary[status] += 1;
      else summary.needs_review += 1;
    }
    const buckets = derived[c]?.exam_scope?.change_scope?.[payload.base_cycle];
    const preagg = { ...zero };
    if (buckets) {
      const addInto = (source) => { if (!source) return; for (const k of Object.keys(preagg)) preagg[k] += Number(source[k] || 0); };
      if (exam === '公务员') {
        if (sub === '国考') addInto(buckets['国考']);
        else if (sub === '省考') addInto(buckets['省考']);
        else { addInto(buckets['省考']); addInto(buckets['国考']); }
      } else if (exam === '事业编') {
        const entry = buckets['事业编'];
        addInto(sub ? entry?.[sub] : entry?.all);
      }
    }
    check(`${payload.base_cycle}->${c} ${exam}${sub ? '·' + sub : ''}`, summary, preagg);
  }
}
console.log('  通过');

// 5) 全量口径回归：exam=全部 时 by_exam 合计应等于 manifest posts/recruits
console.log('== 5) 全量口径回归 ==');
const manifest = JSON.parse(readFileSync(join(site, 'data/site-manifest.json'), 'utf8'));
for (const item of manifest.cycles) {
  const scope = derived[item.cycle]?.exam_scope;
  const posts = Object.values(scope.by_exam).reduce((s, v) => s + v.jobs, 0);
  const recruits = Object.values(scope.by_exam).reduce((s, v) => s + v.recruits, 0);
  check(`${item.cycle} posts/recruits`, { posts: item.posts, recruits: item.recruits }, { posts, recruits });
}
console.log('  通过');

console.log(fail === 0 ? '\n全部比对通过：预聚合与全量逐行计算在所有筛选组合下一致。' : `\n${fail} 处不一致，见上。`);
process.exit(fail === 0 ? 0 : 1);

// P0-9 终验：从修改后的 maintainable-site.js 抽取真实的 exam_scope 辅助函数，
// 在 Node 中与「全量 jobs 行逐行过滤」的旧行为逐项比对（覆盖全部筛选组合 × 全部周期）。
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const pkgRoot = process.argv[2] || join(process.cwd());
const site = join(pkgRoot, '网站');
const source = readFileSync(join(site, 'assets/maintainable-site.js'), 'utf8');

// 抽取辅助函数源码（与文件保持同源，避免验证副本漂移）
const extract = (name) => {
  const start = source.indexOf(`const ${name} = `);
  if (start < 0) throw new Error(`maintainable-site.js 中未找到 ${name}`);
  let depth = 0, end = -1;
  for (let i = source.indexOf('=', start + name.length); i < source.length; i += 1) {
    const ch = source[i];
    if (ch === '{' || ch === '(' || ch === '[') depth += 1;
    else if (ch === '}' || ch === ')' || ch === ']') depth -= 1;
    else if (ch === ';' && depth === 0) { end = i; break; }
  }
  return source.slice(start, end + 1);
};
const prefectureCityOrder = ['合肥', '芜湖', '蚌埠', '淮南', '马鞍山', '淮北', '铜陵', '安庆', '黄山', '滁州', '阜阳', '宿州', '六安', '亳州', '池州', '宣城'];
const prefectureCities = new Set(prefectureCityOrder);
const state = {};
const { examBucketTotals, examScopeCityBucket } = new Function('prefectureCities', 'state', `'use strict'; ${extract('examBucketTotals')} ${extract('examScopeCityBucket')} return { examBucketTotals, examScopeCityBucket };`)(prefectureCities, state);

// —— 旧行为镜像（全量 jobs 行逐行过滤） ——
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
  return prefectureCityOrder.find((candidate) => city === candidate || city.startsWith(candidate)) || null;
};
const normalizeCity = (value) => {
  const city = String(value || '').trim();
  if (!city) return null;
  if (city === '省直') return '省直';
  if (city === '宿松') return '安庆';
  if (city === '广德') return '宣城';
  return prefectureCityOrder.find((candidate) => city === candidate || city.startsWith(candidate)) || null;
};
const canonical = (value) => {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([k, v]) => [k, canonical(v)]));
  return value;
};

const cycles = ['2024', '2025', '2026'];
const COMBOS = [['公务员', ''], ['公务员', '省考'], ['公务员', '国考'], ['事业编', ''], ['事业编', '上半年'], ['事业编', '下半年']];
const jobs = {}, derived = {};
for (const c of cycles) {
  jobs[c] = JSON.parse(readFileSync(join(site, 'data/cycles', c, 'jobs.json'), 'utf8'));
  derived[c] = JSON.parse(readFileSync(join(site, 'data/cycles', c, 'derived.json'), 'utf8'));
}

let fail = 0;
const check = (label, legacy, fresh) => {
  if (JSON.stringify(canonical(legacy)) !== JSON.stringify(canonical(fresh))) {
    fail += 1;
    console.log(`[FAIL] ${label}`);
  }
};

for (const c of cycles) {
  for (const [exam, sub] of COMBOS) {
    const scope = derived[c].exam_scope;
    // 1) cycleRows 总量（active 口径）
    const rows = rowsFor(jobs[c]).filter((row) => examRowMatches(row, exam, sub));
    const legacyTotals = { jobs: rows.length, recruits: rows.reduce((s, r) => s + (Number(r.num ?? r.recruits ?? 0) || 0), 0) };
    const totals = examBucketTotals(scope, exam, sub) || { jobs: null, recruits: null };
    check(`${c} ${exam}${sub ? '·' + sub : ''} totals`, legacyTotals, { jobs: totals.jobs, recruits: totals.recruits });
    // 2a) slope 城市桶（trendCityKey 口径，保留未归并值；active 行）
    const legacySlopeCities = {};
    rows.forEach((row) => {
      const raw = String(row.city || '').trim() ? row.city : row.reg;
      const city0 = String(raw || '').trim();
      const city = city0 === '省直' ? '省直' : (mapCityFor(city0) || city0 || '未标注');
      const item = legacySlopeCities[city] || (legacySlopeCities[city] = { jobs: 0, recruits: 0 });
      item.jobs += 1;
      item.recruits += Number(row.num ?? row.recruits ?? 0);
    });
    const slopeBucket0 = examScopeCityBucket(scope, exam, sub, false) || {};
    // slopeGraph 只消费 jobs/recruits（examinees 供工具，slope 不读）
    const slopeBucket = Object.fromEntries(Object.entries(slopeBucket0).map(([city, s]) => [city, { jobs: s.jobs, recruits: s.recruits }]));
    check(`${c} ${exam}${sub ? '·' + sub : ''} slopeCities`, legacySlopeCities, slopeBucket);
    // 2b) 工具城市 stats（normalizeCity 口径；v17-tools 不按 record_status 过滤 → 全部行 + raw 桶）
    const allRows = (jobs[c].allMajors.rows || []).filter((row) => examRowMatches(row, exam, sub));
    const legacyToolCities = {};
    allRows.forEach((row) => {
      const city = normalizeCity(row.city);
      if (!city) return;
      const item = legacyToolCities[city] || (legacyToolCities[city] = { jobs: 0, recruits: 0, examinees: 0 });
      item.jobs += 1;
      item.recruits += Number(row.num ?? row.recruits ?? 0);
      item.examinees += Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0);
    });
    const toolBucket = examScopeCityBucket(scope, exam, sub, true, true) || {};
    check(`${c} ${exam}${sub ? '·' + sub : ''} toolCities(raw)`, legacyToolCities, toolBucket);
  }
}
console.log(fail === 0 ? '真实文件辅助函数验证通过：examBucketTotals / examScopeCityBucket 与全量逐行计算一致。' : `${fail} 处不一致`);
process.exit(fail === 0 ? 0 : 1);

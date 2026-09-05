/* 皖域择岗 · 纯函数核心层：分档 / 蒙特卡洛 / 适配度评分 / 分享码（node 可直接单测） */
(() => {
  const BAND_KEYS = ['safe', 'hit', 'near', 'miss'];

  /* 档位：稳＝高于入围线 5 分以上；达线＝≥线；贴线＝差 3 分以内；miss＝未达 */
  const bandOf = (score, line) => {
    if (score >= line + 5) return 'safe';
    if (score >= line) return 'hit';
    if (score >= line - 3) return 'near';
    return 'miss';
  };

  /* 标准正态采样（Box-Muller），接受可注入的 rng 便于确定性测试 */
  const gauss = (rng = Math.random) => {
    let u = 0;
    let v = 0;
    while (u === 0) u = rng();
    while (v === 0) v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };

  /* 蒙特卡洛：给定 composite 分数、入围线与波动 σ，返回各档概率（0..1）与进面概率 reached */
  const monteCarlo = (score, line, vol, iterations = 600, rng = Math.random) => {
    const sigma = Math.max(0, Number(vol) || 0);
    const result = { safe: 0, hit: 0, near: 0, miss: 0, samples: 0, reached: 0 };
    if (!(Number.isFinite(score) && Number.isFinite(line))) return result;
    if (sigma <= 0) {
      const band = bandOf(score, line);
      result[band] = 1;
      result.samples = 1;
      result.reached = band === 'miss' ? 0 : 1;
      return result;
    }
    const counts = { safe: 0, hit: 0, near: 0, miss: 0 };
    let reached = 0;
    for (let index = 0; index < iterations; index += 1) {
      const band = bandOf(score + gauss(rng) * sigma, line);
      counts[band] += 1;
      if (band !== 'miss') reached += 1;
    }
    BAND_KEYS.forEach((key) => { result[key] = counts[key] / iterations; });
    result.samples = iterations;
    result.reached = reached / iterations;
    return result;
  };

  /* 线性归一化；区间退化时返回 0.5（中性） */
  const normalize = (value, min, max) => {
    if (!Number.isFinite(value)) return 0;
    if (!Number.isFinite(min) || !Number.isFinite(max) || max - min <= 1e-9) return 0.5;
    return Math.min(1, Math.max(0, (value - min) / (max - min)));
  };

  /* 适配度：factors 各项 0..1，weights 自动归一化，返回 0..100 整数 */
  const matchScore = (factors, weights) => {
    let total = 0;
    let score = 0;
    Object.entries(weights || {}).forEach(([key, weight]) => {
      const w = Number(weight) || 0;
      if (w <= 0) return;
      total += w;
      score += w * (Number(factors?.[key]) || 0);
    });
    if (total <= 0) return 0;
    return Math.round((score / total) * 100);
  };

  /* 分享码：JSON → URL 安全 base64（支持中文） */
  const encodeShare = (state) => {
    try {
      const bytes = encodeURIComponent(JSON.stringify(state));
      return btoa(bytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    } catch {
      return '';
    }
  };
  const decodeShare = (code) => {
    try {
      const base = String(code || '').replace(/-/g, '+').replace(/_/g, '/');
      const padded = base + '='.repeat((4 - (base.length % 4)) % 4);
      return JSON.parse(decodeURIComponent(atob(padded)));
    } catch {
      return null;
    }
  };

  /* 平替检索：同类别、同竞争分母类型、竞争更缓（ratio 更大）、入围线相近 */
  const findSubstitutes = (target, records, limit = 12) => {
    if (!target) return [];
    const targetCompetitionType = String(target.competition_metric_type || '');
    const ratioOf = (record) => {
      if (!targetCompetitionType || String(record.competition_metric_type || '') !== targetCompetitionType) return -1;
      const base = Number(record.competition_base || 0);
      return base > 0 ? Number(record.recruits || 0) / base : -1;
    };
    const targetRatio = ratioOf(target);
    const targetLine = Number.parseFloat(String(target.fields?.['最低入围/线'] ?? target.fields?.['最低面试线'] ?? '').replace(/[^0-9.]/g, ''));
    const hasLine = Number.isFinite(targetLine);
    return records
      .filter((record) => record.exam === target.exam && String(record.competition_metric_type || '') === targetCompetitionType && record.record_id !== target.record_id && String(record.code) !== String(target.code))
      .map((record) => {
        const ratio = ratioOf(record);
        const line = Number.parseFloat(String(record.fields?.['最低入围/线'] ?? record.fields?.['最低面试线'] ?? '').replace(/[^0-9.]/g, ''));
        const lineOk = hasLine
          ? (Number.isFinite(line) && Math.abs(line - targetLine) <= 3)
          : record.city === target.city;
        return { record, ratio, lineOk, easier: ratio > targetRatio || (targetRatio < 0 && ratio > 0) };
      })
      .filter((item) => item.lineOk && item.easier)
      .sort((a, b) => b.ratio - a.ratio)
      .slice(0, limit)
      .map((item) => item.record);
  };

  const api = { BAND_KEYS, bandOf, gauss, monteCarlo, normalize, matchScore, encodeShare, decodeShare, findSubstitutes };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.wanyuCore = api;
  else if (typeof globalThis !== 'undefined') globalThis.wanyuCore = api;
})();

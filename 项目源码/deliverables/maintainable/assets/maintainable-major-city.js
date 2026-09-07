(() => {
  const PREFECTURE_CITY_ORDER = ['合肥', '芜湖', '蚌埠', '淮南', '马鞍山', '淮北', '铜陵', '安庆', '黄山', '滁州', '阜阳', '宿州', '六安', '亳州', '池州', '宣城'];
  const normalize = (value) => String(value || '').replace(/\s+/g, '').toLocaleLowerCase();
  const integer = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0 ? Math.trunc(parsed) : 0;
  };
  const entryFor = (index, key) => {
    const keywords = index?.keywords;
    return keywords && typeof keywords === 'object' && !Array.isArray(keywords) ? keywords[key] : null;
  };
  const majorIndexKey = (index, query) => {
    const needle = normalize(query);
    if (!needle || index?.schema !== 'wanyu-maintainable-major-city/v1' || !index?.keywords || typeof index.keywords !== 'object') return '';
    return Object.keys(index.keywords).find((key) => normalize(key) === needle) || '';
  };
  const citySummary = (city, value) => {
    const item = value && typeof value === 'object' ? value : {};
    const jobs = integer(item.jobs ?? item.rows);
    return {
      city,
      jobs,
      recruits: integer(item.recruits ?? item.num),
      rows: integer(item.rows ?? jobs),
      rawCities: Array.isArray(item.rawCities) ? item.rawCities.filter(Boolean).map(String) : [city],
    };
  };
  const unmappedSummary = (city, value) => {
    const item = citySummary(city, value);
    return { city: item.city, jobs: item.jobs, recruits: item.recruits };
  };
  const aggregateIndexedMajorCities = (index, query) => {
    const key = Object.prototype.hasOwnProperty.call(index?.keywords || {}, query) ? query : majorIndexKey(index, query);
    const source = entryFor(index, key);
    if (!key || !source || typeof source !== 'object' || !source.cities || typeof source.cities !== 'object') return null;
    const direct = citySummary('省直', source.cities['省直']);
    const cities = PREFECTURE_CITY_ORDER.map((city) => citySummary(city, source.cities[city]));
    const known = new Set([...PREFECTURE_CITY_ORDER, '省直']);
    const unmapped = [];
    Object.entries(source.cities).forEach(([city, value]) => {
      if (!known.has(city)) unmapped.push(unmappedSummary(city, value));
    });
    Object.entries(source.unmapped || {}).forEach(([city, value]) => unmapped.push(unmappedSummary(city, value)));
    const mappedRows = cities.reduce((sum, item) => sum + item.rows, 0) + direct.rows;
    return {
      cities,
      direct,
      unmapped,
      sourceRows: integer(source.jobs),
      mappedRows,
      totalRecruits: integer(source.recruits),
    };
  };
  const majorIndexOptions = (index) => Object.keys(index?.keywords || {})
    .map((value) => [value, integer(index.keywords[value]?.jobs)])
    .filter((item) => item[0] && item[1] > 0)
    .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]), 'zh'));
  const api = Object.freeze({ majorIndexKey, aggregateIndexedMajorCities, majorIndexOptions, prefectureCityOrder: PREFECTURE_CITY_ORDER });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.WanyuMajorCityIndex = api;
})();

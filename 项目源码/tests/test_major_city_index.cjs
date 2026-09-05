const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const helper = require(path.join(__dirname, '..', '..', 'site', 'assets', 'maintainable-major-city.js'));
const index = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'site', 'data', 'cycles', '2026', 'major_city.json'), 'utf8'));

test('exact readable major keys use the indexed city summary', () => {
  const key = helper.majorIndexKey(index, ' 法学类 ');
  assert.equal(key, '法学类');
  const summary = helper.aggregateIndexedMajorCities(index, key);
  assert.equal(summary.sourceRows, index.keywords[key].jobs);
  assert.equal(summary.totalRecruits, index.keywords[key].recruits);
  assert.equal(summary.cities.length, 16);
  assert.equal(summary.direct.city, '省直');
  assert.equal(summary.mappedRows, summary.sourceRows);
});

test('unknown or empty major keys do not claim an indexed hit', () => {
  assert.equal(helper.majorIndexKey(index, '不存在的专业'), '');
  assert.equal(helper.majorIndexKey(index, ''), '');
  assert.equal(helper.aggregateIndexedMajorCities(index, ''), null);
});

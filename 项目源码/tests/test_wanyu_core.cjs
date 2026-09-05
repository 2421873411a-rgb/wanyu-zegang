/* product-core.js 纯函数层单测：node --test tests/test_wanyu_core.cjs */
const { test } = require('node:test');
const assert = require('node:assert');
const core = require('../tools/anhui_web/templates/product-core.js');

test('bandOf 分档边界', () => {
  assert.equal(core.bandOf(80, 70), 'safe');
  assert.equal(core.bandOf(75, 70), 'safe');
  assert.equal(core.bandOf(70, 70), 'hit');
  assert.equal(core.bandOf(67.5, 70), 'near');
  assert.equal(core.bandOf(66.9, 70), 'miss');
});

test('monteCarlo 零波动退化为确定档位', () => {
  const result = core.monteCarlo(80, 70, 0);
  assert.equal(result.safe, 1);
  assert.equal(result.reached, 1);
  assert.equal(core.monteCarlo(50, 70, 0).miss, 1);
});

test('monteCarlo 概率单调：分数越高进面概率越高（固定种子）', () => {
  const rng = () => 0.42;
  const low = core.monteCarlo(65, 70, 3, 800, rng).reached;
  const mid = core.monteCarlo(70, 70, 3, 800, rng).reached;
  const high = core.monteCarlo(78, 70, 3, 800, rng).reached;
  assert.ok(low <= mid && mid <= high, `${low} <= ${mid} <= ${high}`);
  const bands = core.monteCarlo(70, 70, 5, 400, rng);
  const total = bands.safe + bands.hit + bands.near + bands.miss;
  assert.ok(Math.abs(total - 1) < 1e-9, '各档概率之和应为 1');
});

test('matchScore 权重归一化', () => {
  assert.equal(core.matchScore({ opportunity: 1, competition: 0, salary: 0, city: 0 }, { opportunity: 50, competition: 50, salary: 0, city: 0 }), 50);
  assert.equal(core.matchScore({ opportunity: 1, competition: 1, salary: 1, city: 1 }, { opportunity: 10, competition: 10, salary: 10, city: 10 }), 100);
  assert.equal(core.matchScore({ opportunity: 1 }, { opportunity: 0 }), 0);
});

test('normalize 区间与钳制', () => {
  assert.equal(core.normalize(5, 0, 10), 0.5);
  assert.equal(core.normalize(-1, 0, 10), 0);
  assert.equal(core.normalize(11, 0, 10), 1);
  assert.equal(core.normalize(3, 3, 3), 0.5);
});

test('分享码中英混排往返', () => {
  const state = { profile: { fresh: true, strict: false }, filters: { q: '合肥 大数据', tags: ['party'] }, note: '中文测试 ✓' };
  const code = core.encodeShare(state);
  assert.ok(!code.includes('+') && !code.includes('/') && !code.includes('='));
  assert.deepEqual(core.decodeShare(code), state);
  assert.equal(core.decodeShare('@@bad@@'), null);
});

test('findSubstitutes：同类别、同分母口径、竞争更缓、线差 ≤3', () => {
  const target = { record_id: 'a', code: 'A1', exam: '省考', city: '合肥', recruits: 2, competition_base: 2000, competition_metric_type: 'examinees', fields: { '最低入围/线': '70' } };
  const records = [
    target,
    { record_id: 'b', code: 'A2', exam: '省考', city: '合肥', recruits: 2, competition_base: 1000, competition_metric_type: 'examinees', fields: { '最低入围/线': '71' } },
    { record_id: 'c', code: 'A3', exam: '省考', city: '合肥', recruits: 2, competition_base: 3000, competition_metric_type: 'examinees', fields: { '最低入围/线': '71' } },
    { record_id: 'd', code: 'A4', exam: '省考', city: '合肥', recruits: 2, competition_base: 1000, competition_metric_type: 'examinees', fields: { '最低入围/线': '80' } },
    { record_id: 'e', code: 'A5', exam: '事业单位', city: '合肥', recruits: 2, competition_base: 1000, competition_metric_type: 'examinees', fields: { '最低入围/线': '70' } },
  ];
  const subs = core.findSubstitutes(target, records);
  assert.deepEqual(subs.map((item) => item.code), ['A2']);
});

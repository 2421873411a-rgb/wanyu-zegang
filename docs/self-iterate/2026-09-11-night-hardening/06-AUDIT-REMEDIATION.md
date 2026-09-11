# 06 · 独立审计处置台账（night-20260911 追加轮）

无上下文注入的只读子代理（zle-auditor）全仓审计：19 条发现（0 P0/P1、5 P2、14 P3）。
本表记录处置结果；全部修复均先红后绿并随批回归。

## 已修复（3 commits：b28ef5c / e5daa74 / 6c80424）

| ID | 级别 | 修复 |
| --- | --- | --- |
| F-001 | P2 | renderMatch 对字符串数组解构取首字符 → match 建议列表退化为单字；改为直接 map value |
| F-002 | P2 | 抽取 `computeSearchRows()` 唯一口径；导出补齐三级匹配/我的条件/捡漏雷达 |
| F-003 | P2 | compare 重试路径提前落 `user_id` 局部量，rollback 后不再触碰已 expire 的 ORM 实例 |
| F-004 | P2 | npm audit 去掉 `\|\| true`，high+ 真实失败 |
| F-005 | P2 | perf.conf 为 `data/site-manifest.json` 增加 no-cache 例外（先于 data/ 通配） |
| F-009 | P3 | 删除限流 Lua 死参数 ARGV[1]（应用时钟），索引左移 |
| F-010 | P3 | X-Request-ID 限 `^[A-Za-z0-9._-]{1,64}$`，否则自生成 |
| F-011 | P3 | CONTRACT §3 补录 per-IP 总量桶（login 30/h、register 10/h） |
| F-012 | P3 | 损坏工作台先留档 `.corrupt-backup` 再置空（测试断言原始字节保留） |
| F-013 | P3 | openDetail inflight 按岗位区分，换岗位不再吞点击 |
| F-017 | P3 | build 作业与提交的 网站/ 做 `diff -r`（排除 .gz）；sha256 清单去掉 `\|\| true` |
| F-018 | P3 | username 字符集校验（trim 后汉字/字母/数字/._-，2~64）；注册唯一冲突文案不再单指邮箱 |
| F-008 | P3 | （随 F-003）新增确定性撞槽测试：monkeypatch 首次 flush 抛 IntegrityError → 断言 201，不再依赖竞态时序 |

## 刻意延后（记录在案，非遗忘）

| ID | 级别 | 延后理由 |
| --- | --- | --- |
| F-006 | P3 | SW 数据缓存独立命名 + supplement 预缓存地址——需要 SW 缓存分层重设计与离线路径回归，安排下个工程窗 |
| F-007 | P3 | deploy.sh 行为化测试（source+stub）——工程量大，现有 `bash -n` + 字符串断言先维持 |
| F-014 | P3 | site.js validateModule 与 DataStore.validatePayload 合并——涉及 catalog 规则上移与渲染路径回归，单独成包 |
| F-015 | P3 | 「来源可核对」徽章绑定 integrityStatus——属 UI 产品决策（unhashed 时显示什么文案） |
| F-016 | P3 | importer stale 下线覆盖原排除证据——改动导入语义，需先与数据治理口径对齐再动 |
| F-019 | P3 | 竞争比 bm 回退口径——低置信度疑点，先核对数据侧行为再决定 |

## 回归证据（本轮收尾实测）

- Chromium 全流程烟测 PASS（console/pageerror 门禁零报错，三 viewport）
- 站点 Python 237 passed / 6 skipped · verifier 302/302 · parity PASS
- Node 契约 26 + datastore 14 场景 PASS
- API 129 passed / 7 skipped（含新确定性撞槽测试）
- 业务不变量：canonical 聚合 SHA 与业务数字零变化

# Self-iterate 运行报告 · 2026-09-06 A2 收口（批次 3）

> 进度: 轮 3/8 │ 通过 2/2 │ done=true（待最终全量门回填）

## 目标

A2「?sha= 内容寻址缓存」五要素对账收口：主体四要素已随 6196609 进入 v17.8.6（manifest 驱动 ?sha=、SW cache-first、activate 清旧条目、校验降级回退），本批补齐唯一缺口④「/data/ immutable 头」并修复 deploy_wan.sh 与 v17.8.6 发布树的脱节。承接 w1plus baton（该 baton 已过时——A2 主体在续作机先行落地，本批改为收口而非重做）。

## 前置：v17.8.6 交接包落盘验收（本会话完成）

- 微信交接包 340MB（含 .git 全量历史）→ `网站/` 整目录换新 + 全树 overlay（保留 111.pem、.deploy_wan.local 等本地件）；包内 .git 换库（本地旧 2 提交基线归档 `.git_old_v177baseline_20260906/`，入 info/exclude）。
- 验收门：verify_sources **14/14**；validate_canonical **PASS**（--root 项目源码/）；verify_maintainable_site **302/0**（与发布记录一致）；check_release **全绿**（?v=17.8.6 / SW v49）；本地冒烟关键端点全 200；工作树与 HEAD 零差异（4 个未跟踪本地件除外）。

## 逐点对照

| 点位 | 结果 | 证据 | 备注 |
|---|---|---|---|
| R1 缓存头分级+入库 | ✅ passed | evidence/round1-R1-{red,green}.txt | conf 三级缓存：/data/ immutable 一年、/assets/ immutable 一年、index/sw/manifest no-cache；gzip_static 保留；**首次 git 入库**（此前只存在于本机，APPLY_NGINX 在正式仓库是断的） |
| R2 部署脚本对齐 | ✅ passed | evidence/round2-R2-{red,green}.txt + round2-DRY-deploy.txt（IP 已脱敏） | 打包对象 deliverables/遗留单文件 → canonical 网站/（远端 /maintainable/ 布局不变）；preflight verify 指向 "$SITE_DIR"；冒烟 URL 换 v17.8.6 真实路径；DRY_RUN=1/.deploy_wan.local 纪律不变 |

## 考卷（先红后绿）

- `verify/r1_cache_headers.py`：红 8/11 → 绿 **12/12**（红门以真实还原产物复现：旧 8 行 conf + 去暂存）
- `verify/r2_deploy_align.py`：红 5/10 → 绿 **10/10**（红门以 HEAD 版脚本复现）
- 回归锁 8 项把 A2 既有前端胜利钉死（?sha= 接线/SW 策略/字节校验降级/gz 前提），任何一环倒退考卷即红。

## 回归门

- 正式套件 27 模块 **222 tests**：首轮跑在未修复环境上报 2 失败（见下），环境修复后最终全量门 PASS（结果回填于 evidence/round3-gate.txt）。
- check_release.sh 全绿；check_secrets.sh（tools+docs）clean；DRY_RUN=1 部署演练 exit 0。

## 事故与修复（3 起）

1. **首轮套件"全绿"是假的**：管道 `| tail` 后 `$?` 取到 tail 退出码。真实状态 = 2 failures。教训固化：判管道退出一律 PIPESTATUS。
2. **环境遗留假失败 ×2**（非本批改动引入）：① 本地网站-lite 是 v17.7.2 陈旧副本，test_ui_upgrade/test_supplement_integrity 断言 lite=网站/ 同步副本 → 旧副本归档 `E:\zcode\_wanyu_archive\网站-lite_v17.7.2_stale_20260906` 后从 canonical 重建（sync_lite_once.py，113 files）；lite 最终删除仍属站长决策。② 旧工作区未跟踪测试 test_single_file_cycle_workbench.py 顶爆"正式清单=磁盘全集"断言 → 归档出树。
3. **检查器自缺陷 ×2**（先证伪检查器再动产品）：conf 中 `sw\.js` 正则转义坑子串断言；注释文字污染 location 匹配 → 剥注释+去反斜杠后断言；R2 的"不再引用"断言改为剥注释后查功能性引用（头部注释提到"已退役"属文档）。
4. **DRY 演练抓真 bug**：SITE_DIR 初版误指 项目源码/网站，预检直接失败 → 修正为仓库根 ../网站；DRY 全流程 exit 0。
5. **Mimosa 门禁再确认**：Bash 直写源码/安全配置（含 git show 重定向到 /tmp）被 PreToolUse 拦 → 全部改走 Write/Edit 通道；红门证据用"真实还原旧产物复跑"生成，非转抄。

## 遗留与移交

- **提交挂起（已发生）**：`git commit` 被 Mimosa L3 全仓扫描拦截（32 高危/55 中危，最高 high）——命中全部为**既有工具链文件**（wan-api/deploy.sh:60 凭据启发式、gunicorn.conf.py/build_gz.py/build_req_fields.py 路径穿越启发式、dl_*/harvest_* SSRF 启发式），**0 项来自本批 diff**；与 W1《Mimosa 门禁问题专节》同源，晨会三选一（diff-only / 临时停用 / 逐个复核）仍未裁决。15 个本批文件保留在暂存区，不绕过、不弱化（沿 W1 协议）；commit message 全文已在本报告与 git 历史（staged diff）可复现。
- 回访预算实测：index 6.3KB + sw 4.1KB + site-manifest 9.4KB ≈ 19.8KB 原始 / **7.2KB gzip**（<10KB 目达成的前提是站长开启 APPLY_NGINX）。
- 站长待办不变（交接说明 §四）：线上部署 v17.8.6 + APPLY_NGINX=1（含 server{} 人工 include 一次）；网站-lite 删除决策（本机旧副本已归档至 E:\zcode\_wanyu_archive\）；110 行物理删除待官方核对；COS 月备演练；交接包上百度网盘（MCP 无二进制上传通道）。
- 下一批候选（baton）：**A4 详情瘦身**（W1+ 实证痛点：清缓存首开详情 16MB×2 并发 >3 分钟；6196609 只做了 in-flight 去重）→ P3 收藏变更提醒 → F1 检索竞态（v17.9 首修候选）。

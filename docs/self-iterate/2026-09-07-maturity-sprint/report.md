# 皖域择岗 · 成熟度冲刺终局报告（2026-09-08）

## 一句话

**从 v17.9.10（Staging Ready）出发，7 轮"对抗审计→证伪→规划→修复→全量验证→PR 合入"循环，关闭 P0×3、P1×18、P2×50+；连续两轮干净（Round 6/7）达成收敛；已完成 S8 安全回归与生产部署——wan.kaogong.art API 现已上线 v17.9.17。**

## 轮次总表

| 轮 | 版本 | PR | 审计镜头 | 关闭 | 干净 |
|---|---|---|---|---|---|
| 1 | v17.9.11 | #10 | 部署链/数据完整性/CI真实性/版本文档（4代理） | P0×1 P1×8 P2×18 | 否 |
| 2 | v17.9.12 | #11 | 认证安全/API迁移/供应链性能运维（3代理） | P0×1 P1×8 P2×16 P3×4 | 否 |
| 3 | v17.9.13/14 | #12#13 | 回归对抗×3（复审自抓 v17.9.12 新引入缺陷） | P1×3 P2×27 | 否 |
| 5 | v17.9.15 | #14 | 数据回归/文档真相/运维推演（3代理） | P0×1 P2×13 | 否 |
| 6 | v17.9.16 | #15 | 认证API回归+全链一致性（2代理） | P2×9 | **是** |
| 7 | v17.9.17 | #16 | 部署数据终审+安全API终审（2代理，119探针） | P2×3 | **是** |

（轮次 4 并入轮次 3 的 v17.9.14 补修；无跳号实质。）

## 关键修复（择要）

- **P0×3**：日志目录权限（首署必死）、用户快照端点双向 500（前端静默吞错）、deploy 载荷行续行符损坏（部署 100% 中止）
- **P1×18**：pg_get_userby 拼错、nginx alias 缺陷、provenance 绕过、复核事件翻倍、幽灵引用、APP_VERSION 十版漂移、record_status 词表冲突、限流并发穿透、SECRET_KEY 弱密钥、pg_dump 强制、审计日志丢弃、/health 探活、GIN 索引性能、反斜杠转义、首署 mkdir、release 列宽等
- **机制建设**：API 版本单一真源（wan-api/release.json）、部署面 linkage 门禁（11 条）、canonical CI discovery 全量（18 模块+4 cjs）、真数据 e2e 进 CI、限流双后端（原子 memory + Redis Lua）、迁移 0004（GIN+回填）、RUNBOOK/备份/回滚链

## 收敛与 S8 证据

- 干净轮：Round 6（33/33 探针）、Round 7（119/119 探针）连续干净
- 压测（生产本机 127.0.0.1:8000，n=60）：/health 1.8ms、search 9.3ms、cycle=2026 15.1ms、keyword 130ms（PG+GIN）、stats 命中 1.1ms、cycles 2.1ms
- 安全回归：Round 7 终审 119 探针（认证全链/授权矩阵/导入 18 向量/转义正反/暴露面）全 PASS
- fresh-host 演练：服务器 /opt/wanyu/rehearsal-20260908 独立 venv+8050 端口+真实数据导入（10017/10150/8511 与基线一致）→ 已清理

## 生产部署（2026-09-08）

- 服务器：ubuntu@175.27.132.225（Ubuntu 24.04，多站点共用）
- 布局适配：API=/opt/wanyu/api（www-data）；静态数据=/var/www/wan.kaogong.art/maintainable/data（现网站点数据直接复用，零迁移）；nginx 只增量插入 /api/+/health（备份于 sites-available/*.bak-deploy-20260908；绕过 sites-enabled 为普通文件副本的坑——补丁必须写入 sites-enabled 实际加载的文件）
- 部署后公网验证：/health={ok,v17.9.17,db:ok}、search 2026=8401、/api/docs 200、静态站 200 不受影响、301 强跳、其他站点正常
- 认证全链路（公网）：register→login→me→refresh 轮换→重用检测（family 撤销）全 OK
- 管理员：admin@kaogong.art 已引导，凭据在服务器 /opt/wanyu/credentials/admin.txt（600）
- 回滚锚点：/opt/wanyu/backup/wanyu_db-post-import.dump（600）+ RUNBOOK

## 残余风险与后续

1. zcode.kaogong.art 502 为既有问题（其自身 upstream 7310 未运行，与本次部署无关）
2. 关键词搜索 CJK 短词（2 字）走扫描路径 ~130ms（GIN trgm 对 <3 字符模式收益有限）——可接受，后续可加专用索引
3. SSH 密钥轮换仍未做（wanyu111_fixed.pem 随交接包分发过）——建议站长尽快执行
4. 多 worker 扩容前提：RATE_LIMIT_BACKEND=redis 已是生产默认；stats 跨 worker TTL ≤60s
5. 交接包 txt 已加时点声明；wan-api README/CONTRACT/RUNBOOK 已随版本滚动

## 流程教训（进 memory）

1. PR 必须基于当刻 origin/main；重构删函数前全仓 grep 调用方（含 shell heredoc）
2. heredoc 多层转写会写坏转义敏感代码——此类修改走 Read+Edit/字节验证，且必须带**正向**门禁（只测反向挡不住"把功能改坏"）
3. "声称修复"以落盘字节+针对性门禁为准，不以提交信息为准
4. CI 真绿三查：日志实跑、无 skip 掩盖、无同名 status 顶替（branch protection 绑 Actions app）
5. 分支/重置操作后必须立即核对 HEAD 与目标分支（本轮曾因 reset --hard 丢过一版终局报告——已重写）

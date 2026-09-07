# Round 3 审计 · 文档真相 + 静态站消费面（子代理产出，逐条对照代码）

- P1 README 快速开始被 SECRET_KEY 门禁打断（.env.example 自带 denylist 密钥值，实测 import 拒启）。【修复中】
- P1 版本真源在 CONTRACT §4/RUNBOOK/.env.example 指向错误文件（项目源码/release.json 是网站产品；API 真源=wan-api/release.json）。【修复中】
- P1 _escape_like 缺陷实现（同数据链审计，CHANGELOG 宣称未真实生效）。【已修】
- P2 CONTRACT 'num/bm 必须整数' 对 bm 为假（浮点 bm 静默 NULL）。【修复中：validate bm】
- P2 CONTRACT §2.5 级联承诺过度（在场 excluded 行不清理）。【修复中】
- P2 CONTRACT 限流描述落后（Redis 已落地为生产默认；refresh/logout 限流未入契约）。【修复中】
- P2 README 端点表缺一半/测试数不符/§引用错/定位语夸大。【修复中】
- P2 RUNBOOK pg_restore 缺 sudo -u postgres（peer 认证下必失败）。【修复中】
- P2 静态站对 API 真实消费面为零，README 定位语需改为"为未来动态站预建"。【修复中】
- P2 CHANGELOG stats 条目半真（查询曾照跑）。【已随 stats 修复变为真】
- P2 交接包 txt 状态陈述严重过时。【修复中：加时点声明】
- P2 3 个未跟踪 _audit_probe*.py 会被 deploy 载荷带进生产。【已删+deploy 排除清单加固】
- P2 CONTRACT "无 || true" 绝对化表述与唯一白名单豁免不符。【修复中】
- 零发现：record-status 三方词表一致；网站两轮零改动；canonical core PASS；EXCLUDED 理由交叉核验无矛盾；CONTRACT 其余声明逐条为真。

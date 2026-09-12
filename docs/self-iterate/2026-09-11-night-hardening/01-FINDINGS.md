# 01 · 审阅清单核实结论（2026-09-11，main@9f87d772 基线）

对外部审阅提出的每个问题做了代码级核实，**全部属实、零误报**，并据此定位修复。

| 编号 | 问题 | 核实位置（main@9f87d772） | 结论 |
| --- | --- | --- | --- |
| P1-01 | profile 输入依赖隐式全局 event | maintainable-site.js:1896 `event.target.id.replace(...)`（函数签名只有 `id,value`） | 属实，Chromium 靠 window.event 兜底 |
| P1-02 | manifest SHA 实际只当缓存键 | maintainable-data.js:43 `if (!addressed && entry?.sha256…)`，而 addressed=Boolean(sha256) | 属实，校验被短路 |
| P1-03 | 管理员导入 commit 前清缓存 | admin.py:220 invalidate 先于 get_db 的 return-后-commit；bulk 脚本路径（import_service.py:545）反而是对的 | 属实，仅 admin 端点有竞态窗口 |
| P1-04 | 64MB body 上限共享全 API | deploy.sh:488 `location /api/ { client_max_body_size 64m }` | 属实 |
| P1-05 | bcrypt 同步占事件循环 | auth.py:100/130/133/143 直接调用同步 hash/verify（含 dummy 路径） | 属实 |
| P1-07 | num/bm 接受 3.0 与 CONTRACT 漂移 | import_service.py `_to_int`：`value.is_integer()` 放行 3.0；CONTRACT.md:22「浮点拒绝」 | 属实，合同-实现-测试三者不一致 |
| P2-08 | 快照 50 上限并发可穿透 | user.py count→insert 无锁 | 属实（PG CI 才能实测） |
| P2-09 | compare 撞槽误报「已存在」 | user.py free_slots[0] 插入，IntegrityError 统一报重复 | 属实 |
| P2-10 | Redis 降级限流按 4 worker 稀释 | rate_limit.py:143 `min(RATE_LIMIT_FALLBACK_WORKERS,4)` 默认 4，生产 1 worker | 属实，login 5次/窗 变 1次/窗 |
| P2-11 | npm 未进 dependabot/audit | .github/dependabot.yml 仅 pip×2+actions | 属实 |
| P2-12 | localStorage 属性访问/配额无防护 | user-store.js:6 getStorage 无 try；:25 setItem 无 catch | 属实 |
| P2-13 | workspace 导入不去重 | user-store.js importAll 仅 filter/map/slice | 属实 |
| P1-CI | Required CI ≠ 完整 release 验证 | canonical-ci 明确排除需构建产物/浏览器的套件；无三浏览器门禁 | 属实 |
| P1-06 数据 | review queue 7 open / 1 high risk 属实缺口 | manifest + review-queue.json 核对一致 | 不动数据，等官方材料 |

未在本轮处理的审阅项（刻意延后，理由见 02-EXECUTION 末节）：maintainable-site.js 大规模拆分、legacy builder 退休、provenance attestation、真 fresh-host 演练、COS 实弹。

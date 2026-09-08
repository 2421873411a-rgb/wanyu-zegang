# v17.9.18 Production Hardening Acceptance — RETRACTED

**状态：2026-09-08 撤回，不得再作为 PASS 证据。**

原文件只有“All 15 items verified PASS”结论，没有命令、输出、执行机器、commit、时间戳、
fresh-host 日志或 restore 日志。对 `main@7c2d011917482ae7cf5d1c7285094b74d6bf7c23`
重新审查后，确认以下可复现断链：

1. P0：`setup_secret_env` 早于 APP_VERSION 解析，可能写入空版本。
2. P0：fresh-host HTTPS `/` 返回 302，而 smoke 不跟随跳转却只接受 200。
3. P0：外部 `wanyu.env` 只给 systemd；Alembic、导入和管理员 CLI 未加载它。
4. P1：restore drill DROP 后未 CREATE 目标库。
5. P1：restore drill 错用 `current/app/venv/bin/alembic`。
6. P1：restore 失败没有退出清理保证；旧 `LATEST` 迁移锚点与 immutable 架构断链。
7. P2：weekly/monthly 没有复制 checksum。
8. P2：`--build-only` 维护了与生产 `build_release()` 不同的复制实现。
9. P2：fresh-host Nginx 模板与 CONTRACT 的 `root` 约束冲突，回退为 `alias + try_files`。

代码级修复见 v17.9.19 Round-9 记录。新的 fresh-host、生产 smoke、COS 异机下载与 restore
在真实机器完成并归档前，S8 和 Production Hardening 继续是 **NOT VERIFIED**。

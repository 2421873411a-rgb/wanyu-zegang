本目录是一次 /self-iterate 运行。恢复步骤：① 读 `state.json`；② 用一句话向用户复述目标与点位状态；③ 按 `baton` 继续；④ 遵守铁律（证据在案、每轮一个焦点、仅双条件门达成才 done=true）。

**目标一句话**：A2 收口——?sha= 内容寻址缓存的五要素在 v17.8.6 已有四要素（6196609），本批补齐「/data/ immutable 头」（perf conf 分级缓存并入库），并把 deploy_wan.sh 从遗留 deliverables 布局对齐到 canonical 网站/ 发布树。

**关键现场**：
- 树：`E:\zcode\择岗`（v17.8.6-1 = 05eae45，工作树与 HEAD 一致；.git 为交接包全量库）
- 考卷：`verify/r1_cache_headers.py`（conf 内容+入库）、`verify/r2_deploy_align.py`（部署脚本对齐）；先红后绿
- conf 目标文件：`项目源码/docs/ops/wan-kaogong-perf.conf`（本机遗留未入库版只有 gzip_static）
- 红线：不连生产/不部署（DRY_RUN=1 默认不动）；不动 网站/ 内容树；111.pem/.deploy_wan.local 不入库；Mimosa 门禁若拦 commit 如实记录不绕过
- 回归门：正式套件 27 模块 + check_release.sh + check_secrets.sh + verify_maintainable_site.py 网站

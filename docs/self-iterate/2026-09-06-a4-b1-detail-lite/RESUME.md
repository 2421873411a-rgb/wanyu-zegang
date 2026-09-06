本目录是一次 /self-iterate 运行。恢复步骤：① 读 `state.json`；② 用一句话向用户复述目标与点位状态；③ 按 `baton` 继续；④ 遵守铁律（证据在案、每轮一个焦点、verify/ 只加强不削弱、先红后绿、仅双条件门达成才 done=true）。

**目标一句话**：A4-B1 详情瘦身——详情列并入 jobs_lite（6 字段等值 + ss 分类码 + ji 行号 + 周期级来源登记），openDetail lite-first（排除行整包回退），详情打开从 16.7MB 整包降为零额外下载。

**关键现场**：
- 改动文件：`项目源码/tools/anhui_web/build_maintainable_site.py`（_LITE_ROW_KEYS/_lite_payload/两调用点）、`templates/maintainable-site.js`（deriveSource/openDetail）、`verify_maintainable_site.py`（values_match_source 口径演化+强校验）、站点树 lite×3/major_city×3/manifest/资产 site.js/.gz
- 再生工具：`regen_lite_b1.py`（装配级，幂等；改 lite 后必须跑它 + `build_gz.py 网站`）
- 考卷：`verify/r1_lite_detail_fields.py`（builder+模板）、`verify/r2_site_tree_b1.py`（站点树）
- 红线：不连生产/不部署；版本号不动（发布属站长/发布动作）；commit 挂起（Mimosa 全仓扫描，与批次3 同源）
- 回归门：正式套件 27 模块 + node 4 套件 + verify_maintainable_site 302/0 + check_release

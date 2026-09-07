# Round 2 审计报告 · 镜头：API 行为 + 迁移漂移（子代理产出，全部含复现；主控复核）

- A1 **P0** /api/v1/user/snapshots 全坏：写路径把 dict 绑到 Text 列（500），读路径 str→Dict 校验失败（500）；
  前端 SyncUserStore 静默吞 500 造成"已保存"假象；零测试覆盖。修法：JSON 序列化成对处理 + 门禁测试。
- A2 P2 LIKE 通配符注入：keyword='%%' 语义=全匹配、'单位_' 命中'单位aaa'。修法：转义 %/_/\\。
- A3 P2 page 无上限：page=1e18 → OFFSET int64 溢出 → 未认证 500。修法：le 上限或 clamp。
- A4 P2 迁移 0002 对已 populated 库无回填：record_status 全 NULL → 全站公共查询清空
  （deploy.sh 的 upgrade→import 顺序掩盖了窗口）。修法：新迁移 alter server_default + UPDATE 回填。
- A5 P2 init_db 对 alembic_version 多行 fail-open（fetchone 无 ORDER BY，结果取决于物理行序）。
  修法：fetchall + 行数!=1 → RuntimeError（backlog #9 实锤）。
- A6 P2 api-data-store.js 调 /cycles/{cycle}/{module}、/map、/audit/three-year 三个不存在的端点
  （从未被页面引用，API-first 路径从未工作，纯靠静态 JSON fallback）。处置：文档化真实消费面 + 标记。
- A7 P2 note 600 字符超列宽被 SQLite 静默接受，PG 将 500（方言漂移）。修法：schema max_length 对齐列宽。
- A8 P2 salary value_wan=0 被 falsy 吞成 null（违反"零不冒充未知"数据原则）。修法：is not None。
- A9 P2 深嵌套 JSON RecursionError → 500 而非 400。修法：并入 JSONDecodeError 捕获。
- A10 P2 CompareListCreate.position 被接受但服务端忽略（契约误导）；收藏 note 无更新端点。
  修法：删 position 字段；note 编辑端点按需。

已验证无问题（全部实测复现）：跨用户隔离无 IDOR；compare 四槽+UNIQUE/CHECK；admin 导入对抗矩阵
（幂等/顶层/坏 JSON/超大字段名/周期错配零写入/级联清理 SQL trace）；迁移链干净可逆、check 零漂移；
空库行为全 200/404 合理；lifespan fail-closed；keyword emoji/西里尔/10k 字符安全；stats 不被单参路由遮蔽。

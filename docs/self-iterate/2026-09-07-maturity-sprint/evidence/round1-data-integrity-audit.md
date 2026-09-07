# Round 1 审计报告 · 镜头：数据完整性（子代理产出，含实测复现）

- D1 P1 provenance 指纹可被"整段删除"绕过（fail-open by omission）：import_service.py:180-185 `if declared is not None` 才比对；实测删 provenance 键 → ACCEPTED。修法：canonical schema(wanyu-cycle-bundle/v1) 文档强制 provenance 必填，静态 allMajors 允许缺席。
- D2 P1 import_all_data 非幂等：review 事件 7→14（jobs/salary 幂等，review 无去重 upsert）。每次重部署翻倍。
- D3 P1 收藏/对比接受任意 record_id：user.py add 端点不查 Job 存在/active；excluded 岗位成"列表可见、详情 404"幽灵引用；伪造 id 永久占对比槽。
- D4 P2 排除证据三字段校验强制要求但导入即丢弃（Job 无列）→ 审计痕迹只剩状态词
- D5 P2 meta 双口径可混搭（total=raw + recruits=active 通过）→ 守恒报警弱化
- D6 P2 admin dashboard 含 excluded（28678 vs 28568 口径矛盾）
- D7 P2 canonical vs 静态 xl 归一口径漂移：canonical 覆盖导入静默改 1442 行 xl（行数/哈希/MirrorState 全不变）
- D8 P2 num 浮点静默截断（3.7→3）
- D9 P2 Cycle.snapshot_date 永远 NULL（只活在 label 字符串）
- D10 P2 双入口事务语义不一致：admin 单周期提交可造成跨周期版本拼盘
- D11 P2 /api/v1/audit/review-queue 无鉴权（注：同数据已在静态站公开，见 triage）
- D12 已验证无问题：_upsert_mirror_state 的 if v is not None 是死分支（现状无害）
- D13 已验证无问题：6 真快照全过/全量导入对账正确/幂等/exact overwrite/active 过滤/对抗输入全拒（基线可信）

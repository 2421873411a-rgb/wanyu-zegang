# Round 5 审计 · 数据回归验证镜头（子代理产出，含探针实测）

受审五项 v17.9.14 修复全部实证生效：
1. 反斜杠转义字节级确认（类含反斜杠/chr(92) 替换/5 处 ilike 全带 escape）+ 门禁种子无退格陷阱 + 端到端语义四例全对
2. release 32 字符 422；全文件其余 Field 与列宽核对无漏网（record_id/EmailStr 有替代封顶）
3. 级联两分支真覆盖（stale 路径 + incoming_excluded 同 id 路径分别锁定）；MirrorState.release 三轮探针（保留/更新）正确
4. stats 缓存命中 0 SQL（事件探针）；invalidate 钩子两处；跨进程陈述与部署一致
5. bm/num 边界矩阵（3.7 拒/null/缺省/0 全对）
全套件 73+5skip、e2e PASS 与基线一致。

新发现（全 P2，已当场修复）：
- R5-1 app/schemas/__init__.py __all__ 残留空串（Round-4 引入；star-import 崩）→ 已清 + 冒烟
- R5-2 stats 缓存键空间无界（cycle 未校验；3000 匿名请求实测不释放）→ cycle max_length 8 + 缓存容量 64 整体失效
- R5-3 admin 导入字符串无列宽校验（label→String(64) 风险；管理员信任边界内）→ label ≤64 校验 + 其余在 CONTRACT 豁免记录
- R5-4 audit.py 注释写 100 代码 200（同"声称与落盘一致"教训复发）→ 已改 200

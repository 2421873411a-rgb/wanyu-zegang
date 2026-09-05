# Self-iterate 运行报告 · 2026-09-05 W1+ 增量（批次 2）

> 进度: 轮 1/20 │ 04:50/截止 09:00 │ 通过 1/5 │ done=false

## 目标

承接批次 1（W1 止损 11/11 EXIT），继续 v2 计划增量：A5 死代码清理、U1a 抽屉层级、D3a 2024 city 归一（源头+干跑）、D6a floor 哨兵（源头）、U10a 浅色对比度残留。

## 逐点对照

| 点位 | 结果 | 证据 | 备注 |
|---|---|---|---|
| Q1 A5 清理 | ✅ passed | evidence/round1-Q1.txt | 11/11；误吞事故已修复并固化为断言 |
| Q2 U1a 抽屉 | pending | — | |
| Q3 D6a floor | pending | — | |
| Q4 D3a city | pending | — | |
| Q5 U10a 对比度 | pending | — | |

---

## 续作（轮 2 · 2026-09-05 上午 · 续作机 D:\AI\zcode\皖域择岗）

> 网盘换代后本机接管批次 2 剩余四点，全部通过（done=true）。版本推进 v17.7.1 → **v17.7.2 / SW v42**（未发布态）。

| 点位 | 结果 | 证据 | 备注 |
|---|---|---|---|
| Q2 U1a 抽屉 | ✅ passed | evidence/round2-Q2.txt | z 30→60 + 滚动锁；双开竞态 bug 实测复现并修复 |
| Q3 D6a floor | ✅ passed | evidence/round2-Q3.txt | 源头改 None，断言全过，哈希链未动 |
| Q4 D3a city | ✅ passed | evidence/round2-Q4.txt | 干跑 3,989/3,989 全对账，2025/26 零误伤 |
| Q5 U10a 对比度 | ✅ passed | evidence/round2-Q5.txt | 18 处全 ≥4.5:1；深色统计三色补齐 |

发版工程：index 12 处 ?v=17.7.2、SW v42+PRECACHE 对齐、manifest release 同步、.gz 重预压缩（92.8MB→8.1MB）、templates 反向同步、网站-lite 同步。
门禁：check_release.sh 全绿 · verify_maintainable_site 226/226 · test_ui_upgrade 9/9 · node --check 过。
事故记录：①Windows write_text CRLF 事故（test_ui_upgrade 抓出，LF 归一+模板同步）②滚动锁真值守卫 bug（浏览器实测复现，in 守卫修复）③bundle 导入插错 try 块（语法解析抓出）。
实证痛点（强化 A4 优先级）：清缓存后首开岗位详情 = jobs.json×2 并发下载 + 16MB SHA 校验，实测 >3 分钟未完成渲染（双开竞态+CPU 校验），详情瘦身势在必行。

# 皖域择岗 v17.6.4 · 换设备交接说明

## 先打开哪里

解压交接包后，优先打开：

```text
网站/index.html
```

这是当前完整维护站，包含 2024、2025、2026 三个周期、岗位检索、岗位地图、三年对照、数据审计和补充证据台账。`网站-lite/index.html` 是轻量输出。

如果浏览器直接双击后不能读取外置 JSON，请在“网站”目录启动本地静态服务：

```powershell
cd .\网站
python -m http.server 18766 --bind 127.0.0.1
```

然后访问 `http://127.0.0.1:18766/?cycle=2026#overview`。

## 交接包内容

- `网站/`：完整维护站，入口为 `网站/index.html`。
- `网站-lite/`：轻量维护站。
- `项目源码/`：源数据、工具、测试、文档和 API 目录；不含 `node_modules`、Python 缓存和临时下载缓存。
- `发布资料/`：当前交接说明、发布记录、审计报告和 manifest。
- `原始交接包/`：原始 `E:\zcode\皖域择岗交接包_20260904_v17.6.4.tar.gz` 的只读副本。

## 当前数据边界

- supplement 实际归档 43 个 raw 文件：41 个可解析文档、2 个 404 HTML 阻断响应。
- SHA-256 为 43/43 匹配，正式岗位基线未因补充台账追加记录。
- 116 条成绩仍待唯一归属复核；835 条拟聘用记录只在独立 evidence inventory 中，不计入岗位总数。
- 三年正式基线：2024 为 10,017 岗 / 15,331 人，2025 为 10,150 岗 / 14,721 人，2026 为 8,511 岗 / 12,006 人。
- 完整证据台账：`项目源码/source_data/supplement_20260904/integrity_audit.json`。

## 在新设备继续开发

进入 `项目源码/` 后：

```powershell
python -m unittest tests.test_supplement_integrity -q
python tools/anhui_web/verify_maintainable_site.py deliverables/maintainable
python tools/anhui_web/sync_supplement_evidence.py
```

`node_modules` 未打包；若需要运行 Node 浏览器 smoke，先执行 `npm install`。原始交接包缺少部分全量构建所需的已审计页面输入，因此从原始包直接一键全量重建仍可能触发 `CycleBundleError`；当前已验证网站输出可以直接使用。

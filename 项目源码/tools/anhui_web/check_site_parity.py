#!/usr/bin/env python3
"""生成漂移门禁（v17.9.2 PR-4）：网站/ 是派生产物，必须与模板字节一致。

校验三件事：
1. 复制类资产（builder 里 shutil.copyfile 的 12 个文件）模板 == 网站/assets；
2. sw.js 由模板 + release.json 版本令牌注入后与 网站/sw.js 一致；
3. gzip 伴生：网站内所有可压缩文本文件都有 .gz 且内容一致（nginx gzip_static 消费）。

任何漂移 → exit 1 并列出差异。CI 与本地均可直接运行。
"""
import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT_SRC = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
SITE = ROOT / "网站"

COPIED_ASSETS = (
    "maintainable-site.js", "maintainable-site.css", "v17-ui-upgrade.css",
    "maintainable-tokens.css", "maintainable-data.js", "maintainable-major-city.js",
    "maintainable-user-store.js", "v17-exam-picker.css", "v17-search.css",
    "v17-tools.css", "v17-tools.js", "og-card.png",
)
GZIP_TYPES = {".js", ".css", ".json", ".html", ".webmanifest", ".svg", ".txt", ".map"}
GZIP_SKIP = {".gz", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff2", ".woff"}


def render_sw() -> bytes:
    import json

    release = json.loads((PROJECT_SRC / "release.json").read_text(encoding="utf-8"))
    text = (TEMPLATE_DIR / "maintainable-sw.js").read_text(encoding="utf-8")
    text = text.replace("__SW_VERSION__", release["service_worker_version"])
    text = text.replace("__ASSET_VERSION__", release["asset_version"])
    return text.encode("utf-8")


def main() -> int:
    drifts: list[str] = []

    for name in COPIED_ASSETS:
        template = TEMPLATE_DIR / name
        deployed = SITE / "assets" / name
        if not deployed.exists():
            drifts.append(f"缺失派生资产：assets/{name}")
        elif template.read_bytes() != deployed.read_bytes():
            drifts.append(f"字节漂移：assets/{name}（模板 != 网站，请重新构建）")

    deployed_sw = SITE / "sw.js"
    if not deployed_sw.exists():
        drifts.append("缺失派生资产：sw.js")
    elif render_sw() != deployed_sw.read_bytes():
        drifts.append("字节漂移：sw.js（模板/版本令牌 != 网站）")

    gz_expected = 0
    for target in [*(SITE / "assets").rglob("*"), *(SITE / "data").rglob("*"),
                   SITE / "index.html", SITE / "sw.js", SITE / "manifest.webmanifest"]:
        if not target.is_file() or target.suffix in GZIP_SKIP or target.suffix not in GZIP_TYPES:
            continue
        gz = target.with_name(target.name + ".gz")
        gz_expected += 1
        if not gz.exists():
            drifts.append(f"缺 .gz 伴生：{target.relative_to(SITE)}")
        elif gzip.decompress(gz.read_bytes()) != target.read_bytes():
            drifts.append(f".gz 内容漂移：{target.relative_to(SITE)}")

    if drifts:
        print("site parity: FAIL")
        for item in drifts:
            print(f"  - {item}")
        return 1
    print(f"site parity: PASS（{len(COPIED_ASSETS)} 复制资产 + sw.js + {gz_expected} .gz 伴生全部一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

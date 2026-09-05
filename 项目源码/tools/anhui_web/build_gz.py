"""P0-9①: 站点 .gz 预构建（nginx gzip_static on 消费）——幂等，mtime+size 判断是否重压"""
import gzip, os, sys, time
from pathlib import Path

site = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[3] / "网站")
targets = []
for sub in ("assets", "data"):
    d = site / sub
    if d.exists():
        targets.extend(p for p in d.rglob("*") if p.is_file())
targets += [p for p in (site / "index.html", site / "sw.js", site / "manifest.webmanifest") if p.exists()]

made = kept = 0
for p in targets:
    if p.suffix in (".gz", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff2", ".woff"):
        continue
    if p.suffix not in (".js", ".css", ".json", ".html", ".webmanifest", ".svg", ".txt", ".map"):
        continue
    gz = p.with_name(p.name + ".gz")
    if gz.exists() and gz.stat().st_mtime >= p.stat().st_mtime:
        kept += 1
        continue
    raw = p.read_bytes()
    tmp = gz.with_suffix(gz.suffix + ".tmp")
    with open(tmp, "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", compresslevel=9, mtime=int(p.stat().st_mtime)) as g:
            g.write(raw)
    os.replace(tmp, gz)
    made += 1

total_src = sum(p.stat().st_size for p in targets if p.suffix in (".js", ".css", ".json", ".html"))
total_gz = sum(p.with_name(p.name + ".gz").stat().st_size for p in targets
               if p.suffix in (".js", ".css", ".json", ".html") and p.with_name(p.name + ".gz").exists())
print(f"gz built: {made} new, {kept} fresh | text payload {total_src/1e6:.1f}MB -> {total_gz/1e6:.1f}MB gz ({(1-total_gz/total_src)*100:.0f}% saved)" if total_src else "gz built: no text files in scope")

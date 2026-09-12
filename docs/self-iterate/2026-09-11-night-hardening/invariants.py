#!/usr/bin/env python3
"""业务事实不变量快照：工程改动前后各跑一次，逐字比对。

用法：python invariants.py [--save PATH] [--compare PATH]
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MANIFEST = os.path.join(ROOT, "网站", "data", "site-manifest.json")
REVIEW = os.path.join(ROOT, "网站", "data", "audit", "review-queue.json")
CANONICAL = os.path.join(ROOT, "项目源码", "canonical")


def canonical_tree_sha() -> str:
    """canonical 目录所有文件内容的聚合 SHA（路径+内容），零变更即零漂移。"""
    digest = hashlib.sha256()
    for base, dirs, files in os.walk(CANONICAL):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, CANONICAL).replace(os.sep, "/")
            digest.update(rel.encode("utf-8"))
            with open(path, "rb") as fh:
                digest.update(fh.read())
    return digest.hexdigest()


def snapshot() -> dict:
    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    cycles = {}
    for entry in manifest.get("cycles", []):
        cycles[str(entry.get("cycle"))] = {
            key: entry.get(key)
            for key in ("raw_posts", "posts", "active_posts", "excluded_posts", "raw_recruits", "recruits", "score_unresolved", "sha256", "bytes")
        }
    review = {}
    if os.path.exists(REVIEW):
        with open(REVIEW, encoding="utf-8") as fh:
            queue = json.load(fh)
        summary = queue.get("summary") or {}
        review = {"summary": summary, "events": len(queue.get("events") or queue.get("items") or [])}
    return {
        "site_release": manifest.get("release"),
        "cycles": cycles,
        "review_queue": review,
        "canonical_tree_sha256": canonical_tree_sha(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save")
    parser.add_argument("--compare")
    args = parser.parse_args()
    current = snapshot()
    if args.save:
        with open(args.save, "w", encoding="utf-8") as fh:
            json.dump(current, fh, ensure_ascii=False, indent=2)
        print(f"saved -> {args.save}")
    if args.compare:
        with open(args.compare, encoding="utf-8") as fh:
            baseline = json.load(fh)
        if baseline != current:
            print("INVARIANT DRIFT DETECTED")
            print(json.dumps({"baseline": baseline, "current": current}, ensure_ascii=False, indent=2))
            return 1
        print("invariants: IDENTICAL")
    if not args.save and not args.compare:
        print(json.dumps(current, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""环境修复（A2 收口批次附带）：本机遗留物导致正式套件 2 处假失败——
1) 网站-lite 是 v17.7.2 陈旧派生副本，而 v17.8.6 正式门（test_ui_upgrade /
   test_supplement_integrity）断言 lite=网站/ 同步副本（源机器如此）。
   → 旧副本整体归档出仓库树，再从 canonical 网站/ 重建同步副本。
   lite 的最终删除决策仍属站长（v2 计划 §九.2），本脚本不删只归档。
2) 项目源码/tests/test_single_file_cycle_workbench.py 是旧工作区未跟踪遗留
   （v17.8.6 已把单文件遗留套件重分类为 tests/test_single_file_legacy.py），
   test_release_integrity 的"正式清单=磁盘全集"断言被它顶爆。
   → 归档出树。
"""
import shutil
from pathlib import Path

REPO = Path(r'E:\zcode\择岗')
ARCH = Path(r'E:\zcode\_wanyu_archive')
STAMP = '20260906'
ARCH.mkdir(exist_ok=True)

lite = REPO / '网站-lite'
stale_test = REPO / '项目源码' / 'tests' / 'test_single_file_cycle_workbench.py'

if lite.exists():
    dst = ARCH / f'网站-lite_v17.7.2_stale_{STAMP}'
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(lite), str(dst))
    print('archived lite ->', dst)

if stale_test.exists():
    dst = ARCH / f'test_single_file_cycle_workbench.py.old-workspace_{STAMP}'
    shutil.move(str(stale_test), str(dst))
    print('archived stale test ->', dst)

shutil.copytree(REPO / '网站', lite)
n = sum(1 for _ in lite.rglob('*') if _.is_file())
print(f'resynced lite <- 网站/ ({n} files)')

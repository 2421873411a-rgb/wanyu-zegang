"""P3 (P0-2): 移动端变更通报入口 + 视图术语单一命名源
校准说明（round3 执行前）：原 n<=2 字面量断言会把 h1 文档全称误算进去；
本点位验收的是"导航类表面共用唯一命名源 + 移动端入口存在"，据此断言：
  1) VIEW_META 单一命名源存在且覆盖 changes；
  2) 移动端"更多"面板含 data-maintain-view="changes" 入口；
  3) 命令面板动作表由 VIEW_META 派生（含 changes，且不再内联旧标签表）；
  4) 加载标题 viewTitles 由 VIEW_META 派生；
  5) 移动端底部宫格短名也引用 VIEW_META。
"""
import re, sys
sys.path.insert(0, os.path.dirname(__file__) if False else '.')
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import check, finish, read, js_path

js = read(js_path())

check('VIEW_META single naming source exists', 'const VIEW_META = {' in js and bool(re.search(r"changes:\s*\{\s*full:\s*'变更通报'", js)))
check('mobile more-panel includes changes entry',
      bool(re.search(r"maint-mobile-more__grid[^`]*\['cycle_compare',\s*'salary_map',\s*'jobs_ranking',\s*'changes'", js)) and
      'data-maintain-view="${view}"' in js)
check('paletteActions derived from VIEW_META (changes reachable)',
      bool(re.search(r'Object\.entries\(VIEW_META\)\.map\(\(\[view, names\]\)\s*=>\s*\(\{\s*kind:\s*\'view\'', js)))
check('old inline palette label map removed', "overview: '周期总览'" not in js)
check('viewTitles derived from VIEW_META', bool(re.search(r'viewTitles\s*=\s*Object\.fromEntries\(Object\.entries\(VIEW_META\)', js)))
check('mobile bottom bar references VIEW_META.short', js.count('VIEW_META.') >= 4)
finish()

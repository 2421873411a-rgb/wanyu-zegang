"""P5 (P0-4): 关键词搜索框恢复 + state.keyword 入保存白名单
校准（round5 执行前）：Legacy 渲染函数是 const 箭头式（原 function 检测失效）。
现役判定改为：live renderSearch 的 h1（"找到适合你的岗位"，全文件唯一）之后、
下一个 const render 之前，必须存在 keyword 输入框。
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import check, finish, read, js_path

js = read(js_path())

h1 = js.find('找到适合你的岗位')
check('live renderSearch located by unique h1', h1 > -1)
next_render = js.find('const render', h1 + 10)
seg = js[h1:next_render] if (h1 > -1 and next_render > -1) else ''
check('keyword <input> present in LIVE toolbar (first position)',
      bool(seg) and 'id="maint-search-keyword"' in seg and seg.find('maint-search-keyword') < seg.find('maint-search-major'),
      f'live segment {len(seg)} chars')
check('keyword input exists in BOTH legacy and live templates', js.count('maint-search-keyword') >= 3,
      f"{js.count('maint-search-keyword')} occurrences (template x2 + handler)")

check('state.keyword wired to an input value', "case 'maint-search-keyword': state.keyword = value" in js)
check('keyword in saved filter object', '{ keyword: state.keyword, major: state.searchMajor' in js)
finish()

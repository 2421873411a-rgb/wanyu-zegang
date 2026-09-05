"""P9 (P0-8): wan-api 止血三处 + 明文默认密码清零"""
import re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import SRC, check, finish, read

api = os.path.join(SRC, 'wan-api')
dep = read(os.path.join(api, 'deploy.sh'))
start = read(os.path.join(api, 'start.sh')) if os.path.exists(os.path.join(api, 'start.sh')) else ''

check('no plaintext default password', 'wanyu_secure_password' not in dep and 'wanyu_secure_password' not in start)
check('gunicorn module app.main:app', 'app.main:app' in dep and (not start or 'app.main:app' in start))
check('no wan-api.main:app module', 'wan-api.main:app' not in dep and 'wan-api.main:app' not in start)

# limit_req_zone must live in http context (top-level), not inside server{ }
top = re.sub(r'server\s*\{[\s\S]*?\n\}', '', dep)
check('limit_req_zone declared outside server block',
      bool(re.search(r'^\s*limit_req_zone\s', top, re.M)) and not re.search(r'server\s*\{[^}]*limit_req_zone', dep, re.S))

# SECRET_KEY must not be assigned inside a QUOTED heredoc (quoted 'EOF' blocks $() unexpanded → literal in .env)
sec_ok = True
for m in re.finditer(r'<<\s*([\'"]?)(\w+)\1', dep):
    quoted, delim = bool(m.group(1)), m.group(2)
    body = dep.split(m.group(0), 1)[1]
    body = body.split('\n' + delim, 1)[0] if ('\n' + delim) in body else body[:2000]
    if quoted and re.search(r'SECRET_KEY\s*=', body):
        sec_ok = False
check('SECRET_KEY not assigned inside quoted heredoc', sec_ok)
finish()

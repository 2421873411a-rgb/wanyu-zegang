"""Build v17.8.6+b1 handoff zip to Desktop."""
import hashlib, os, time, zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
OUT = os.path.join(os.path.expanduser('~'), 'Desktop', '皖域择岗交接包_v17.8.6+b1_20260906.zip')
SKIP_DIRS = {'.git_old_v177baseline_20260906', '__pycache__', '.pytest_cache', 'node_modules', '.mimosa'}
SKIP_FILES = {'111.pem', '111.pem.bak'}
SKIP_EXTS = {'.pyc', '.db', '.part'}

t0 = time.time()
count = total_bytes = 0
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, ROOT).replace(os.sep, '/')
        if rel_dir == '.':
            rel_dir = ''
        if '.git_old' in rel_dir:
            continue
        for f in filenames:
            if f in SKIP_FILES or os.path.splitext(f)[1] in SKIP_EXTS:
                continue
            if '.deploy_wan.local' in f:
                continue
            fp = os.path.join(dirpath, f)
            arc = f'{rel_dir}/{f}' if rel_dir else f
            zf.write(fp, arc)
            total_bytes += os.path.getsize(fp)
            count += 1
            if count % 500 == 0:
                print(f'  {count} files, {total_bytes / 2**20:.0f} MiB, {time.time() - t0:.0f}s')

sz = os.path.getsize(OUT)
sha = hashlib.sha256(open(OUT, 'rb').read()).hexdigest()
elapsed = time.time() - t0
print(f'DONE: {count} files, {total_bytes / 2**20:.0f} MiB raw -> {sz / 2**20:.0f} MiB zip, {elapsed:.0f}s')
print(f'OUT: {OUT}')
print(f'SHA-256: {sha}')

"""Fetch the Wiki's public content graph. Read-only HTTP; never execute site code."""
import argparse
import concurrent.futures
import gzip
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'artifacts/wiki'
ASSETS = 'https://assets.wanxiangqiwiki.com/assets/'
ENDPOINTS = {f'{k}.json': f'https://wzwxq.com/explorer-catalogs/{k}.json' for k in ('hero', 'equipment', 'effect', 'talent')}
ENDPOINTS.update({f'{k}.json': f'https://wzwxq.com/{k}.json' for k in ('search-index', 'achievement-text', 'diamond-frenzy', 'lineup-card-index', 'lineup-featured-presets')})
ENDPOINTS.update({'dps-bootstrap.json': 'https://wzwxq.com/dps-runtime/bootstrap.json', 'equipment-manifest.json': 'https://assets.wanxiangqiwiki.com/equipment-value-v30/manifest.json'})

def fetch(url):
    with urlopen(url, timeout=60) as r:
        raw = r.read()
    return gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw

def sync(reuse=False, tools=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    sources = []
    def save(pair):
        name, url = pair
        p = CACHE / name
        raw = p.read_bytes() if reuse and p.exists() else fetch(url)
        if raw[:2] == b'\x1f\x8b': raw = gzip.decompress(raw)
        p.write_bytes(raw)
        return {'file': name, 'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    sources.append(save(('index.html', 'https://wzwxq.com/')))
    html = (CACHE / 'index.html').read_text(encoding='utf-8')
    queue = set(re.findall(r'https://assets\.wanxiangqiwiki\.com/assets/([\w-]+\.js)', html))
    seen = set()
    while queue:
        batch = sorted(queue-seen)
        if not batch: break
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            sources.extend(pool.map(save, [(n, ASSETS+n) for n in batch]))
        seen.update(batch); queue=set()
        for name in batch:
            text = (CACHE / name).read_text(encoding='utf-8')
            queue.update(re.findall(r'["\x27]\./([\w-]+\.js)["\x27]', text))
            queue.update(re.findall(r'"([\w-]+\.js)"', text[:4000]))
        queue -= seen
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        sources.extend(pool.map(save, ENDPOINTS.items()))
    subprocess.run(['node', str(ROOT / 'scripts/extract_wiki.cjs')], check=True, cwd=ROOT)
    manifest = {'collected_at': datetime.now(timezone.utc).isoformat(), 'sources': sources,
                'boundary': '公开导航、公开静态数据与内嵌文本；不读取私人棋盘、分享码、账号数据，不提交模拟请求。'}
    (CACHE/'sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    if tools:
        m=json.loads((CACHE/'equipment-manifest.json').read_text(encoding='utf-8'))
        target=ROOT/'data/wiki/tool-snapshots'; target.mkdir(parents=True,exist_ok=True)
        def shard(hero):
            name=hero['id'].replace(':','-')+'.json.gz'; p=target/name
            url='https://assets.wanxiangqiwiki.com/equipment-value-v30/heroes/'+hero['id'].replace(':','-')+'.json?v='+m['source']['snapshotHash'][:12]
            raw=gzip.decompress(p.read_bytes()) if reuse and p.exists() else fetch(url)
            d=json.loads(raw)
            if d.get('heroId') != hero['id']: raise ValueError('Wrong equipment shard')
            p.write_bytes(gzip.compress(raw,mtime=0))
            return {'file':name,'url':url,'hero_id':hero['id'],'levels':len(d['levels']),'sha256':hashlib.sha256(raw).hexdigest()}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            result=list(pool.map(shard,m['heroes']))
        (target/'manifest.json').write_text(json.dumps({'source':m['source'],'items':result},ensure_ascii=False,indent=2),encoding='utf-8')
        print('equipment shards',len(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reuse-cache',action='store_true');p.add_argument('--tools',action='store_true')
    a=p.parse_args();sync(a.reuse_cache,a.tools)

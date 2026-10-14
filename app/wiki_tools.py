"""Read published equipment-value snapshots, never simulate a real match."""
import gzip
import json
import re
from functools import lru_cache
from .config import ROOT

@lru_cache(maxsize=1)
def manifest():
    return json.loads((ROOT/'data/wiki/equipment-manifest.json').read_text(encoding='utf-8'))

@lru_cache(maxsize=4)
def shard(hero_id):
    return json.loads(gzip.decompress((ROOT/'data/wiki/tool-snapshots'/f'{hero_id.replace(":","-")}.json.gz').read_bytes()))

def equipment_context(query, mode='万象大赛'):
    if mode!='万象大赛' or '钻石狂潮' in query or not re.search('装备价值|装备评分|装备排名',query):return None
    m=manifest(); heroes=[h for h in m['heroes'] if h['name'] in query]
    level_match=re.search(r'(?<!\d)(\d{1,3})\s*级',query)
    if len(heroes)!=1 or not level_match:return None
    level=int(level_match[1])
    if not 1<=level<=100:return None
    hero=heroes[0];data=shard(hero['id'])
    if data['source']['snapshotHash']!=m['source']['snapshotHash']:return None
    state=data['levels'][level-1]
    view='frontline' if re.search('抗伤|防御|前排',query) else 'output'
    fixture=state['fixtures']['base']
    named=[i for i,e in enumerate(m['equipment']) if e['name'] in query]
    results=[]
    for i in named or range(len(m['equipment'])):
        item=m['equipment'][i];row=fixture[view][i];detail=fixture['details'][i]
        result={'装备':item['name'],'分类':['可排名','条件场景','其他视角','未量化'][row[0]]}
        if row[0]==0:result.update(分数=row[1],排名=row[2],参评数=row[3])
        elif row[0]==1:result.update(分数=row[1],条件=row[2],解释=row[3])
        elif row[0]==2:result.update(其他视角分数=row[1],适用视角=row[2])
        if len(detail)>4 and detail[4]:result['未解决问题']=detail[4]
        results.append(result)
    return {'id':f'TOOL-equipment-{hero["id"].replace(":","-")}-{level}-{view}',
            'title':f'{hero["name"]}{level}级·装备价值模型快照',
            'body':json.dumps({'性质':'站点固定条件模型结果，不是实战强度或胜率，不能跨条件套用','视角':view,'等级':level,
                               '条件':next(x for x in m['fixtures'] if x['id']=='base'),'结果':results},ensure_ascii=False),
            'source_title':'万象棋知识站','source_url':'https://wzwxq.com/analysis/equipment-value',
            'collected_at':m['collected_at'],'version_scope':'本地归档装备价值模型快照；'+m['source']['snapshotId'],
            'claim_type':'site_model','verification':'wiki_snapshot','mode':'万象大赛'}

"""Evaluate query planning/retrieval independently of answer writing."""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import ROOT, load_settings
from app.llm import LLM, AgentError
from app.query import fallback_plan
from app.retrieval import Retriever

CASES=[
    ('purchase','我只有2点能量，够买人吗？',lambda rows:any(r['id']=='E03' or r.get('object_id')=='guide-energy-2' for r in rows)),
    ('hero','貂蝉到100级时技能有什么变化？',lambda rows:any(r.get('entity')=='貂蝉' and r.get('field')=='officialSkill' for r in rows)),
    ('mechanic','棋子写的“整备”指什么？',lambda rows:any(r.get('section')=='mechanics' and r.get('entity')=='整备' for r in rows)),
    ('achievement','独狼这个成就怎么解锁？',lambda rows:any(r.get('section')=='achievements' and r.get('entity')=='独狼' for r in rows)),
    ('biography','武凤哪天过生日？',lambda rows:any(r.get('entity')=='武凤' and r.get('field')=='biography' for r in rows)),
    ('update','10月8日版本更新了什么？',lambda rows:any('10月8日版本更新' in r['title'] for r in rows)),
    ('diamond','钻石狂潮里能逛商店买牌吗？',lambda rows:any(r.get('mode')=='钻石狂潮' and '没有商店' in r['body'] for r in rows)),
    ('summon','狼魂的技能和成长说明是什么？',lambda rows:any(r.get('section')=='summons' and r.get('entity')=='狼魂' for r in rows)),
    ('effect','研读会怎么买，费用是多少？',lambda rows:any(r.get('entity')=='研读会' and r.get('field')=='acquisition_limits' for r in rows)),
    ('lineup','常小娥马瑶经典阵容怎么搭配？',lambda rows:any(r.get('section')=='lineups' and '常小娥马瑶' in r['title'] for r in rows)),
]

async def run(live,output):
    s=load_settings();llm=LLM(s);retriever=Retriever();rows=[]
    for cid,q,check in CASES:
        plan=fallback_plan(q);status='rules';error=None
        if live:
            try:
                async with asyncio.timeout(s.planner_timeout):
                    plan=await llm.plan_query(q,[],retriever.catalog_hint(q))
                status='model'
            except (AgentError,TimeoutError) as exc:
                status='fallback';error=exc.code if isinstance(exc,AgentError) else 'planner_timeout'
        hits=retriever.search_plan(q,plan)
        result={'case_id':cid,'question':q,'planner_status':status,'error':error,'plan':plan.model_dump(),
                'retrieved':[{'id':r['id'],'title':r['title']} for r in hits],'retrieval_pass':check(hits)}
        rows.append(result);print(cid,status,result['retrieval_pass'],flush=True)
    out={'created_at':datetime.now(timezone.utc).isoformat(),'live':live,'planner_attempts':len(CASES) if live else 0,
         'planner_successes':sum(r['planner_status']=='model' for r in rows),'retrieval_passes':sum(r['retrieval_pass'] for r in rows),
         'total':len(rows),'notice':'仅检索与关键词规划评测，不是回答质量或关键词普遍正确性的证明。评测标签不发送给规划器。','rows':rows}
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');p.add_argument('--output',default=str(ROOT/'eval/reports/wiki-query.json'));a=p.parse_args()
    asyncio.run(run(a.live,a.output))

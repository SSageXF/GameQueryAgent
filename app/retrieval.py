import json
import math
import re
from collections import Counter

from .config import ROOT
from .query import QueryPlan, fallback_plan


def tokens(text: str) -> list[str]:
    chunks=re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+',text.lower())
    stop={'什么','是什','怎么','如何','多少','的是','有什','为什','么是','哪些','一下'}
    return [t for c in chunks for t in ([c] if len(c)<2 or c.isascii() else [c[i:i+2] for i in range(len(c)-1)]) if t not in stop]


class Retriever:
    def __init__(self,records=None,enhanced=True):
        self.enhanced=enhanced
        if records is None:
            full=ROOT/'data/wiki/records.json'
            paths=['data/knowledge.json', 'data/wiki/records.json' if full.exists() else 'data/wzwxq.json']
            records=sum((json.loads((ROOT/p).read_text(encoding='utf-8')) for p in paths),[])
        self.records=records
        ids=[r['id'] for r in records]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate knowledge IDs')
        self.by_id={r['id']:r for r in records}
        self.counts=[Counter(tokens(r['title']+' '+r['body'])) for r in records]
        self.lengths=[sum(c.values()) for c in self.counts]
        self.titles=[set(tokens(r['title'])) for r in records]
        self.df=Counter(t for c in self.counts for t in c)
        self.avg_len=sum(self.lengths)/max(len(records),1)
        self.idf={t:math.log(1+(len(records)-n+.5)/(n+.5)) for t,n in self.df.items()}
        self.names=sorted({r['entity'] for r in records if r.get('entity')},key=lambda x:(-len(x),x))
        self.context_entities=sorted({r['entity'] for r in records if r.get('entity') and r.get('section') in {'hero','equipment','effect','talent','players','summons'}})

    def pending(self,query):
        return [r for r in self.records if r.get('claim_type')=='pending' and r.get('entity') and r['entity'] in query
                and len(set(tokens(query))&set(tokens(r['body'])))>=2
                and re.search(r'是否|能否|能不能|顺序|时点|重复|独立|冲突',query)
                and r.get('mode')==fallback_plan(query).mode][:3]

    def rank(self,query,mode='万象大赛',include_history=False):
        q=set(tokens(query));found=[n for n in self.names if n in query]
        entities={n for n in found if not any(n!=other and n in other for other in found)}
        leveling=bool(re.search(r'(?:要不要|该不该|是否|先|建议).{0,4}升级|升级.{0,6}(?:还是|划算)',query))
        general_purchase=bool(re.search(r'(?:购买|买|招募).{0,2}(?:英雄|人)|英雄.{0,2}(?:购买|费用)',query)) and not entities
        date_terms=re.findall(r'\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2}',query)
        ranked=[]
        for i,(row,counts) in enumerate(zip(self.records,self.counts)):
            if row.get('mode') not in {mode,'通用'}:continue
            if row.get('verification') not in {'official_page_checked','official_data_matched','wiki_snapshot'}:continue
            if row.get('eligible') is False or row.get('claim_type')=='pending':continue
            if row.get('field') in {'profileState','skillEvidence','portraitBoundary','rawBaseStats','imageStatus','sourceNames','combatCategory','temporarilyOffShelf','evidenceLayer'}:continue
            publication=row.get('publication_status','')
            if (publication.startswith('historical') or publication in {'off_shelf','associated_preview'}) and not include_history:continue
            if row.get('claim_type')=='site_model' and not re.search('木桩|装备价值|模型|模拟器|计算器',query):continue
            entity=row.get('entity')
            if leveling and entity and row.get('section') in {'hero','equipment','talent','effect'}:continue
            if general_purchase and row.get('section') in {'hero','equipment','talent','effect'}:continue
            if entities and not leveling and entity and entity not in entities and row.get('section') in {'hero','equipment','talent','effect','players','summons','achievements','diamond'}:continue
            if date_terms and row.get('section') in {'official_updates','site_updates'} and not any(t in row['title'] or t in row['version_scope'] for t in date_terms):continue
            anchors=[a for a in row.get('aliases',[]) if a and a in query]
            overlap=q&self.titles[i]
            if not anchors and len(overlap)<2:continue
            score=sum(3+min(len(a),6) for a in anchors)+len(overlap)*1.5
            for t in q:
                tf=counts[t]
                if tf:score+=self.idf[t]*tf*2.2/(tf+1.2*(.25+.75*self.lengths[i]/self.avg_len))
            if entity and entity in entities:score+=18
            for word in ('秘技','专属','觉醒','技能','成长','成就','费用','获取','阵容','解释','搭配'):
                if word in query and word in row['title']:score+=18
            if re.search('搭配|配合|怎么用',query) and row.get('field') in {'formal','receivers','failures'}:score+=20
            if date_terms and any(t in row['title'] for t in date_terms):score+=80
            if row.get('field')=='original':score+=3
            if len(row['body'])<12 and row.get('field') not in {'original','awakening'}:score-=12
            if score>=6:ranked.append((score,row))
        ranked.sort(key=lambda x:(-x[0],x[1]['id']))
        return ranked

    def search(self,query,k=3,include_interpretations=False,mode=None,include_history=None):
        default=fallback_plan(query)
        ranked=self.rank(query,mode or default.mode,default.include_history if include_history is None else include_history)
        selected=[r for _,r in ranked[:k]]
        if self.enhanced:
            related={'C04':['E04','T01'],'A01':['A02']}
            for row in list(selected):
                for linked in related.get(row['id'],[]):
                    candidate=self.by_id.get(linked)
                    if candidate and linked not in {r['id'] for r in selected} and len(selected)<k:selected.append(candidate)
        return selected

    def catalog_hint(self,query):
        plan=fallback_plan(query)
        hits=self.search(query,k=10,mode=plan.mode,include_history=plan.include_history)
        return {'sections':sorted({r.get('section',r.get('topic','')) for r in self.records}),
                'nearby_titles':[r['title'] for r in hits],
                'entity_names':sorted({r['entity'] for r in self.records if r.get('entity') and r.get('section') in {'hero','equipment','effect','talent','players','summons'}})}

    def search_plan(self,original,plan:QueryPlan,k=6):
        mode=plan.mode
        if '钻石狂潮' in original:mode='钻石狂潮'
        elif '万象大赛' in original:mode='万象大赛'
        queries=list(dict.fromkeys([original,*plan.queries,' '.join(plan.entities+plan.keywords)]))
        batches=[self.rank(q,mode,plan.include_history) for q in queries if q.strip()]
        selected=[];seen=set()
        for depth in range(k):
            for batch in batches:
                if depth<len(batch):
                    row=batch[depth][1]
                    if row['id'] not in seen:
                        selected.append(row);seen.add(row['id'])
                        if len(selected)==k:return selected
        return selected

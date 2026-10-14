import json
import math
import re
from collections import Counter
from functools import lru_cache

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
        sections={'talent':'天赋','hero':'英雄','equipment':'装备','effect':'效果牌'}
        self.counts=[Counter(tokens(r['title']+' '+r['body']+' '+sections.get(r.get('section'),''))) for r in records]
        self.lengths=[sum(c.values()) for c in self.counts]
        self.titles=[set(tokens(r['title'])) for r in records]
        self.df=Counter(t for c in self.counts for t in c)
        self.avg_len=sum(self.lengths)/max(len(records),1)
        self.idf={t:math.log(1+(len(records)-n+.5)/(n+.5)) for t,n in self.df.items()}
        self.names=sorted({r['entity'] for r in records if r.get('entity')},key=lambda x:(-len(x),x))
        self.context_entities=sorted({r['entity'] for r in records if r.get('entity') and r.get('section') in {'hero','equipment','effect','talent','players','summons'}})

    @staticmethod
    def eligible(row, mode, include_history):
        publication=row.get('publication_status','')
        return (row.get('mode') in {mode,'通用'}
                and row.get('verification') in {'official_page_checked','official_data_matched','wiki_snapshot'}
                and row.get('eligible') is not False and row.get('claim_type')!='pending'
                and (include_history or not (publication.startswith('historical') or publication in {'off_shelf','associated_preview'})))

    def fetch_many(self, ids):
        return [self.by_id[key] for key in ids if key in self.by_id]

    @lru_cache(maxsize=8)
    def catalog_records(self, section):
        # The vector backend fetches these payloads from Qdrant in one batch.
        # Category labels alone cannot answer questions about an object's effects.
        ids=[r['id'] for r in self.records if r.get('section')==section
             and r.get('field') in {'original','faction','relatedCards'}]
        return self.fetch_many(ids)

    def select_catalog(self, selection, mode, include_history, limit=24):
        groups={}
        for row in self.catalog_records(selection.section):
            if self.eligible(row,mode,include_history):
                groups.setdefault(row.get('object_id') or row.get('entity'),[]).append(row)
        matches=[]
        names=set(selection.names)
        terms=[term.casefold() for term in selection.related_to]
        for rows in groups.values():
            originals=[r for r in rows if r.get('field')=='original']
            if not originals:continue
            original=sorted(originals,key=lambda r:r['id'])[0]
            if names and original.get('entity') not in names:continue
            direct=[original,*[r for r in rows if r.get('field')=='faction']]
            direct_text='\n'.join(r['title']+'\n'+r['body'] for r in direct).casefold()
            missing=[term for term in terms if term not in direct_text]
            related=[r for r in rows if r.get('field')=='relatedCards']
            # Every requested condition must have a documented match. Include the
            # relation record when the card text itself doesn't establish the link.
            support=[r for r in related if any(t in r['body'].casefold() for t in missing)]
            if any(not any(t in r['body'].casefold() for r in support) for t in missing):continue
            if not support:
                support=[r for r in direct[1:] if any(t not in (original['title']+'\n'+original['body']).casefold()
                                                     and t in r['body'].casefold() for t in terms)]
            matches.append((original,support,'related_card' if missing else 'direct_text'))
        matches.sort(key=lambda item:(item[2]=='related_card',item[0]['entity'],item[0]['id']))
        total=len(matches)
        selected=matches[:limit]
        evidence=[]
        for original,support,kind in selected:
            for row in [original,*support[:1]]:
                evidence.append({**row,'relation_kind':kind,'selection_total':total,'selection_returned':len(selected)})
        return evidence

    def pending(self,query):
        return [r for r in self.records if r.get('claim_type')=='pending' and r.get('entity') and r['entity'] in query
                and len(set(tokens(query))&set(tokens(r['body'])))>=2
                and re.search(r'是否|能否|能不能|顺序|时点|重复|独立|冲突',query)
                and r.get('mode')==fallback_plan(query).mode][:3]

    def rank(self,query,mode='万象大赛',include_history=False,semantic_scores=None):
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
            semantic=(semantic_scores or {}).get(row['id'],0)
            # A fixed 0.8 gate discarded relevant BGE hits even when their body
            # contained the requested subject. Keep body matches as lexical evidence.
            body_overlap=q & counts.keys()
            if not anchors and len(overlap)<2 and not (semantic>=0.5 and len(body_overlap)>=2) and semantic<0.8:continue
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
            score+=semantic*20
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

    def routing_hint(self, query):
        # Metadata only: no preliminary embedding/search and no full entity catalog.
        names=[name for name in self.names if name in query][:32]
        objects={}
        for row in self.records:
            if row.get('entity') not in names or not self.eligible(row,row.get('mode'),False):continue
            key=(row['entity'],row.get('section'),row.get('mode'))
            fields=objects.setdefault(key,{})
            if row.get('field'):fields.setdefault(row['field'],row['title'])
        return {'sections': ['英雄', '棋手', '装备', '天赋', '机制', '成就', '攻略', '公告', '钻石狂潮'],
                'mentioned_entities': names,
                'matching_rule_titles': [r['title'] for r in self.records if not r.get('entity')
                                         and any(alias and alias in query for alias in r.get('aliases',[]))][:12],
                'objects': [{'name':name,'section':section,'mode':mode,
                             'fields':[{'field':field,'title':title} for field,title in fields.items()]}
                            for (name,section,mode),fields in objects.items()]}

    def catalog_fast_path(self, plan, mode):
        """Only enumerate lists here; a named object needs its full searchable fields."""
        if plan.selection is None or len(plan.selection.names)==1:
            return []
        return self.select_catalog(plan.selection,mode,plan.include_history)

    @staticmethod
    def matches_selection_names(row, selection):
        # A failed catalog filter is not proof of absent knowledge. Search across
        # sections, while keeping explicitly named objects so fallback cannot
        # replace an unknown object with a vaguely related known one.
        if selection is None or not selection.names:return True
        names={name.casefold() for name in selection.names}
        identities={str(value).casefold() for value in [row.get('entity',''),*row.get('aliases',[])] if value}
        return bool(names & identities)

    def supporting_mechanics(self, evidence, mode, limit=2):
        """Expand explicit trigger labels, so the model need not guess their meaning."""
        body='\n'.join(r['body'] for r in evidence)
        seen={r['id'] for r in evidence}
        rows=[]
        for meta in self.records:
            name=meta.get('entity','')
            if (meta.get('section')!='mechanics' or not name or meta['id'] in seen
                or meta.get('mode') not in {mode,'通用'} or meta.get('eligible') is False
                or meta.get('claim_type')=='pending'
                or meta.get('verification') not in {'official_page_checked','official_data_matched','wiki_snapshot'}
                or meta.get('publication_status','').startswith('historical')
                or meta.get('publication_status') in {'off_shelf','associated_preview'}):
                continue
            if re.search(re.escape(name)+r'[:：]',body):
                record=self.by_id.get(meta['id'])
                if record: rows.append(record)
            if len(rows)==limit:break
        return rows

    def search_plan(self,original,plan:QueryPlan,k=6):
        mode=plan.mode
        if '钻石狂潮' in original:mode='钻石狂潮'
        elif '万象大赛' in original:mode='万象大赛'
        catalog=self.catalog_fast_path(plan,mode)
        if catalog:return catalog
        queries=list(dict.fromkeys([original,*plan.queries,' '.join(plan.entities+plan.keywords)]))
        batches=[[hit for hit in self.rank(q,mode,plan.include_history)
                  if self.matches_selection_names(hit[1],plan.selection)] for q in queries if q.strip()]
        selected=[];seen=set()
        for depth in range(k):
            for batch in batches:
                if depth<len(batch):
                    row=batch[depth][1]
                    if row['id'] not in seen:
                        selected.append(row);seen.add(row['id'])
                        if len(selected)==k:return selected
        return selected

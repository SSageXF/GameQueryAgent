import json
from contextlib import closing
from types import SimpleNamespace

import numpy as np
import pytest
from app import vector_store as vs
from app.vector_store import QdrantClient, models
from app.query import fallback_plan
from app.query import CatalogSelection, QueryPlan


class FixedEncoder:
    def query_embed(self, query):
        yield np.array([1.0, 0.0])


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(vs, 'fingerprint', lambda: 'fixture')
    rows=[]
    for key,mode,status,claim in [('current','万象大赛','current','wiki_original'),
                                  ('old','万象大赛','historical','wiki_original'),
                                  ('pending','万象大赛','current','pending'),
                                  ('diamond','钻石狂潮','current','wiki_original')]:
        rows.append(dict(id=key,mode=mode,publication_status=status,claim_type=claim,
                         verification='wiki_snapshot',title='不同措辞',body='一段没有查询字面的有效资料正文',aliases=[]))
    with closing(QdrantClient(path=str(tmp_path/'qdrant'))) as client:
        client.create_collection('test',vectors_config=models.VectorParams(size=2,distance=models.Distance.COSINE))
        client.upsert('test',points=[models.PointStruct(id=vs.point_id(r['id']),vector=[1.0,0.0],payload=r) for r in rows])
    manifest={'model':vs.MODEL,'fingerprint':'fixture','collection':'test','count':len(rows),
              'records':[{k:v for k,v in r.items() if k!='body'} for r in rows],'pending':[]}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    retriever=vs.VectorRetriever(tmp_path,model=FixedEncoder())
    yield retriever
    retriever.client.close()


def test_semantic_recall_without_keyword_overlap_and_filters(store):
    assert [r['id'] for _,r in store.rank('获胜途径')] == ['current']
    assert {r['id'] for _,r in store.rank('获胜途径',include_history=True)} == {'current','old'}
    assert [r['id'] for _,r in store.rank('获胜途径',mode='钻石狂潮')] == ['diamond']
    assert all('body' not in r for r in store.records)
    assert store.by_id.get('current')['body']
    assert [r['id'] for r in store.search_plan('获胜途径',QueryPlan(queries=['获胜途径'],mode='通用'))]==['current']


def test_vector_partial_catalog_reserves_each_requested_skill(store):
    rows=[]
    for key,name,section,field in [('s-card','苏烈','hero','original'),('s-skill','苏烈','hero','officialSkill'),
                                    ('b-skill','白歌','players','skillSections')]:
        rows.append(dict(id=key,entity=name,section=section,field=field,title=name+'技能',body=name+'技能正文',
                         mode='万象大赛',verification='wiki_snapshot',aliases=[name],claim_type='wiki_original'))
    store.client.upsert('test',points=[models.PointStruct(id=vs.point_id(r['id']),vector=[1.0,0.0],payload=r) for r in rows])
    store.records.extend({k:v for k,v in r.items() if k!='body'} for r in rows)
    store.names=['苏烈','白歌']
    plan=QueryPlan(queries=['苏烈和白歌技能'],selection=CatalogSelection(section='hero',names=store.names))
    result=store.search_plan('苏烈和白歌的技能分别是什么？',plan,k=2)
    assert {r['id'] for r in result}=={'s-skill','b-skill'}


def test_missing_index_has_actionable_error(tmp_path):
    with pytest.raises(RuntimeError,match='index_knowledge'):
        vs.VectorRetriever(tmp_path,model=FixedEncoder())


def test_multi_hero_purchase_reserves_entity_and_cost_sources(store):
    rows=[]
    for key,name,field in [('a','曹操','original'),('b','李白','original'),*[(f'a{i}','曹操','awakening') for i in range(7)]]:
        rows.append(dict(id=key,entity=name,section='hero',field=field,title=name+'技能',body=name+'技能原文',
                         mode='万象大赛',verification='wiki_snapshot',aliases=[name],publication_status='current'))
    rows.append(dict(id='E03',title='英雄购买费用',body='英雄购买需要3能量',mode='万象大赛',verification='wiki_snapshot',aliases=['英雄购买费用']))
    store.client.upsert('test',points=[models.PointStruct(id=vs.point_id(r['id']),vector=[1.0,0.0],payload=r) for r in rows])
    store.records.extend({k:v for k,v in r.items() if k!='body'} for r in rows)
    store.names=['曹操','李白']
    question='商店里曹操和李白怎么买？'
    result=store.search_plan(question,fallback_plan(question),k=3)
    assert {r['id'] for r in result}=={'E03','a','b'}


def test_changed_snapshot_rejects_stale_index(store, monkeypatch, tmp_path):
    (tmp_path/'manifest.json').write_text(json.dumps({'model':vs.MODEL,'fingerprint':'old'}))
    with pytest.raises(RuntimeError,match='重建索引'):
        vs.VectorRetriever(tmp_path,model=FixedEncoder())


def test_catalog_reads_qdrant_originals_and_applies_version_mode_filters(store,monkeypatch):
    rows=[]
    for name,mode,status,claim in [('甲','万象大赛','current','wiki_original'),
                                 ('乙','万象大赛','historical','wiki_original'),
                                 ('丙','万象大赛','current','pending'),
                                 ('丁','钻石狂潮','current','wiki_original')]:
        for field,body in [('original','为指定英雄提升等级。'),('relatedCards','关联英雄属于河洛。'),('talentGroup','初始天赋')]:
            rows.append(dict(id=name+field,entity=name,object_id=name,section='talent',field=field,title=name+'天赋',body=body,
                             mode=mode,verification='wiki_snapshot',claim_type=claim,publication_status=status))
    store.client.upsert('test',points=[models.PointStruct(id=vs.point_id(r['id']),vector=[1.0,0.0],payload=r) for r in rows])
    store.records.extend({k:v for k,v in r.items() if k!='body'} for r in rows)
    monkeypatch.setattr(store.model,'query_embed',lambda *args:pytest.fail('Structured catalog needs no embedding'))
    plan=QueryPlan(queries=['河洛天赋'],selection=CatalogSelection(section='talent',related_to=['河洛']))
    hits=store.search_plan('河洛天赋',plan)
    assert {r['id'] for r in hits}=={'甲original','甲relatedCards'}
    assert all(r['selection_total']==1 for r in hits)
    assert all('body' not in r for r in store.records)
    plan.include_history=True
    assert {r['entity'] for r in store.search_plan('河洛天赋',plan)}=={'甲','乙'}
    plan.mode='钻石狂潮'
    assert {r['entity'] for r in store.search_plan('河洛天赋',plan)}=={'丁'}


def test_base_rule_alias_recalls_record_missed_by_semantic_top_k(store,monkeypatch):
    row=dict(id='cost-rule',title='购买卡牌消耗',body='购买英雄牌基础消耗3点能量。',
             aliases=['购买','费用'],mode='万象大赛',verification='official_page_checked',claim_type='rule')
    store.client.upsert('test',points=[models.PointStruct(id=vs.point_id(row['id']),vector=[0.0,1.0],payload=row)])
    store.records.append({k:v for k,v in row.items() if k!='body'})
    monkeypatch.setattr(store.client,'query_points',lambda *a,**kw:SimpleNamespace(points=[]))
    ranked=store.rank('王者万象棋中英雄的购买费用是多少')
    assert [r['id'] for _,r in ranked]==['cost-rule']

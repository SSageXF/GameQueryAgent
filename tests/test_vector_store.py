import json
from contextlib import closing

import numpy as np
import pytest
from app import vector_store as vs
from app.vector_store import QdrantClient, models
from app.query import fallback_plan


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

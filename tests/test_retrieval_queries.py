"""Regression: equivalent questions must not lose records behind catalog filters."""
import json
from contextlib import closing
from unittest.mock import patch

import numpy as np
import pytest

from app.config import ROOT
from app.query import CatalogSelection, QueryPlan
from app.retrieval import Retriever
from app import vector_store as vs


class Encoder:
    def query_embed(self, query):
        yield np.array([1.0, 0.0])


@pytest.fixture(scope='module', params=['lexical', 'vector'])
def retriever(request, tmp_path_factory):
    rows=sum((json.loads((ROOT/path).read_text(encoding='utf-8'))
              for path in ('data/knowledge.json','data/wiki/records.json')),[])
    rows=[r for r in rows if r.get('entity') in {'白歌','苏烈','李白','瑶妹'} or r['id'] in {'B01','B02','B03'}]
    if request.param=='lexical':
        yield Retriever(rows)
        return
    path=tmp_path_factory.mktemp('named-records')
    with closing(vs.QdrantClient(path=str(path/'qdrant'))) as client:
        client.create_collection('test',vectors_config=vs.models.VectorParams(size=2,distance=vs.models.Distance.COSINE))
        client.upsert('test',points=[vs.models.PointStruct(id=vs.point_id(r['id']),vector=[1.0,0.0],payload=r) for r in rows])
    (path/'manifest.json').write_text(json.dumps({'model':vs.MODEL,'fingerprint':'fixture','collection':'test',
        'count':len(rows),'records':[{k:v for k,v in r.items() if k!='body'} for r in rows],
        'pending':[r for r in rows if r.get('claim_type')=='pending']}),encoding='utf-8')
    with patch.object(vs,'fingerprint',return_value='fixture'):
        store=vs.VectorRetriever(path,model=Encoder())
    try:
        yield store
    finally:
        store.client.close()


@pytest.mark.parametrize('question,selection,expected',[
    ('白歌的技能是什么？',CatalogSelection(section='hero',names=['白歌']),'WIKI-a707692151fe8ded9573'),
    ('白歌的专属天赋是什么？',CatalogSelection(section='talent',names=['白歌']),'WIKI-a707692151fe8ded9573'),
    ('苏烈觉醒的效果是什么？',CatalogSelection(section='hero',names=['苏烈']),'WX-hero-sulie-awakening'),
    ('苏烈觉醒卡面的效果是什么？',CatalogSelection(section='hero',names=['苏烈'],related_to=['觉醒']),'WX-hero-sulie-awakening'),
    ('苏烈觉醒卡面的效果是什么？',CatalogSelection(section='hero',related_to=['苏烈','觉醒']),'WX-hero-sulie-awakening'),
    ('苏烈的技能是什么？',CatalogSelection(section='hero',names=['苏烈']),'WX-hero-sulie-skill'),
    ('英雄李白的技能是什么？',CatalogSelection(section='hero',names=['李白']),'WX-hero-1311-skill'),
    ('钻石狂潮里苏烈的技能是什么？',CatalogSelection(section='hero',names=['苏烈']),'WIKI-837c20cc5ea7b9ad1c64'),
])
def test_specific_object_survives_wrong_catalog_route(retriever,question,selection,expected):
    plan=QueryPlan(queries=[question],selection=selection)
    rows=retriever.search_plan(question,plan)
    assert expected in {row['id'] for row in rows}
    expected_mode='钻石狂潮' if '钻石狂潮' in question else '万象大赛'
    assert all(retriever.eligible(row,expected_mode,False) for row in rows)


def test_empty_multi_object_catalog_still_searches_known_entities(retriever):
    plan=QueryPlan(queries=['白歌和瑶妹棋手技能'],selection=CatalogSelection(section='hero',names=['白歌','瑶妹']))
    rows=retriever.search_plan('白歌和瑶妹的技能分别是什么？',plan)
    assert {'白歌','瑶妹'} <= {row.get('entity') for row in rows}
    assert all(row.get('entity') in {'白歌','瑶妹'} or row['id'] in {'B01','B02','B03'} for row in rows)


def test_empty_named_catalog_cannot_substitute_other_entities(retriever):
    plan=QueryPlan(queries=['苏烈技能'],selection=CatalogSelection(section='hero',names=['没有收录的角色']))
    assert retriever.search_plan('没有收录的角色的技能',plan)==[]


def test_routing_metadata_distinguishes_type_and_available_fields(retriever):
    hint=retriever.routing_hint('白歌的技能、苏烈觉醒卡面')
    objects={(r['name'],r['section']):r for r in hint['objects']}
    assert 'skillSections' in {f['field'] for f in objects['白歌','players']['fields']}
    assert {'awakening','original','officialSkill'} <= {f['field'] for f in objects['苏烈','hero']['fields']}
    assert '白歌的技能与复制' in retriever.routing_hint('棋手李白技能')['matching_rule_titles']
    assert all('body' not in field for obj in hint['objects'] for field in obj['fields'])

import gzip
import hashlib
import json

import httpx
import pytest

from app.agent import Agent
from app.config import ROOT, Settings
from app.llm import LLM
from app.query import QueryPlan, fallback_plan
from app.retrieval import Retriever
from app.schemas import ChatRequest


@pytest.fixture(scope='module')
def retriever(): return Retriever()


def test_all_public_index_objects_covered():
    report=json.loads((ROOT/'data/wiki/coverage.json').read_text(encoding='utf-8'))
    snapshot=json.loads(gzip.decompress((ROOT/'data/wiki/snapshot.json.gz').read_bytes()))
    assert report['search_index_count']==len(snapshot['documents']['search-index']['items'])
    assert report['search_index_missing']==[]
    objects={o['id']:o for o in report['objects']}
    for kind,catalog in snapshot['catalogs'].items():
        assert {x['id'] for x in catalog['items']} <= objects.keys()
        assert all(objects[x['id']]['record_ids'] for x in catalog['items'])
    assert {'players','mechanics','summons','guide','achievements','lineups','official_updates','site_updates','diamond','tools'} <= {s['section'] for s in report['sections']}


def test_all_equipment_tool_shards_archived():
    folder=ROOT/'data/wiki/tool-snapshots'
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['items'])==85
    for item in manifest['items']:
        raw=gzip.decompress((folder/item['file']).read_bytes())
        assert hashlib.sha256(raw).hexdigest()==item['sha256']
        data=json.loads(raw)
        assert data['heroId']==item['hero_id']
        assert [x['level'] for x in data['levels']]==list(range(1,101))
        assert all(len(level['fixtures']['base']['output'])==32 for level in data['levels'])


@pytest.mark.parametrize('question,title',[
    ('貂蝉100级技能是什么','貂蝉·技能'),
    ('独狼成就怎么做','独狼·成就'),
    ('整备是什么意思','整备'),
    ('10月8日更新了什么','10月8日版本更新'),
    ('武凤的生日是哪天','武凤·人物档案'),
    ('狼魂的技能是什么','狼魂'),
    ('研读会的商店费用是多少','研读会·商店费用'),
])
def test_new_columns_retrievable(retriever,question,title):
    rows=retriever.search_plan(question,fallback_plan(question))
    assert any(title in r['title'] for r in rows)


def test_diamond_is_separate_and_now_supported(retriever):
    rows=retriever.search_plan('钻石狂潮有没有商店',fallback_plan('钻石狂潮有没有商店'))
    assert rows and all(r['mode'] in {'钻石狂潮','通用'} for r in rows)
    assert any('没有商店' in r['body'] for r in rows)


def test_model_cannot_override_explicit_mode(retriever):
    plan=QueryPlan(queries=['英雄商店'],mode='万象大赛')
    rows=retriever.search_plan('钻石狂潮有没有商店',plan)
    assert all(r['mode'] in {'钻石狂潮','通用'} for r in rows)


def test_history_excluded_until_requested(retriever):
    assert all(r.get('publication_status')!='historical' for r in retriever.search('明先生秘技'))
    assert any(r.get('publication_status')=='historical' for r in retriever.search('10月8日更新公告'))
    historical=next(r for r in retriever.records if r.get('publication_status')=='historical_pending')
    assert not Retriever([historical]).search(historical['title'])


def test_new_entity_followup_uses_full_catalog(retriever):
    from app.context import prepare
    from app.schemas import Message
    result=prepare('那她的生日呢？',[Message(role='user',content='武凤的技能是什么')],entity_names=retriever.context_entities)
    assert not result.ambiguous and '武凤' in result.query


def test_equipment_model_lookup_keeps_conditions():
    from app.wiki_tools import equipment_context
    row=equipment_context('苏烈40级红莲炎甲的装备价值是多少？')
    body=json.loads(row['body'])
    assert row['claim_type']=='site_model'
    assert body['等级']==40 and body['条件']['id']=='base'
    assert len(body['结果'])==1 and body['结果'][0]['装备']=='红莲炎甲'
    assert equipment_context('苏烈装备价值是多少') is None
    assert equipment_context('钻石狂潮苏烈40级装备价值') is None


async def test_real_adapter_plans_then_generates(retriever):
    calls=[]
    def handler(request):
        payload=json.loads(request.content);data=json.loads(payload['messages'][1]['content']);calls.append(data)
        if 'catalog' in data:
            answer={'queries':['购买英雄牌能量消耗'],'keywords':['英雄','购买','费用'],'entities':[],'mode':'万象大赛','include_history':False}
        else:
            assert any('3点能量' in r['body'] for r in data['evidence'])
            answer={'answer':'普通英雄牌基础购买需要3点能量。','source_ids':[next(r['id'] for r in data['evidence'] if '3点能量' in r['body'])]}
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(answer,ensure_ascii=False)}}]})
    settings=Settings(retrieval_backend='lexical', base_url='https://model.test/v1',model='test',api_key='TEST_SECRET')
    result=await Agent(settings,llm=LLM(settings,httpx.MockTransport(handler)),retriever=retriever).chat(ChatRequest(message='我只有2点能量，够买人吗？'))
    assert len(calls)==2
    assert result.retrieval_plan['status']=='model'
    assert result.retrieval_plan['keywords']==['英雄','购买','费用']
    assert 'expected' not in json.dumps(calls)


@pytest.mark.parametrize('bad',['not-json','{"queries":[]}','{"queries":["购买"],"mode":"王者荣耀"}'])
async def test_planner_failure_falls_back_without_leaking(retriever,bad):
    def handler(request):
        data=json.loads(json.loads(request.content)['messages'][1]['content'])
        answer=bad if 'catalog' in data else json.dumps({'answer':'普通英雄购买需要3点能量。','source_ids':[data['evidence'][0]['id']]})
        return httpx.Response(200,json={'choices':[{'message':{'content':answer}}]})
    settings=Settings(retrieval_backend='lexical', base_url='https://model.test/v1',model='test',api_key='TEST_SECRET')
    result=await Agent(settings,llm=LLM(settings,httpx.MockTransport(handler)),retriever=retriever).chat(ChatRequest(message='英雄购买费用是多少？'))
    assert result.retrieval_plan['status']=='fallback'
    assert result.sources
    assert 'TEST_SECRET' not in result.model_dump_json()


async def test_chitchat_does_not_plan(retriever):
    class Fake:
        async def plan_query(self,*args):raise AssertionError('No retrieval needed')
        async def generate(self,*args):
            from app.llm import Generation
            return Generation(answer='你好，我是弈宝。',source_ids=[])
    result=await Agent(Settings(retrieval_backend='lexical', mode='mock'),llm=Fake(),retriever=retriever).chat(ChatRequest(message='你好'))
    assert result.retrieval_plan is None

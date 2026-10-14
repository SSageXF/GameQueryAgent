import json

import httpx
import pytest

from app.agent import Agent
from app.config import Settings
from app.llm import LLM
from app.query import CatalogSelection, QueryPlan
from app.retrieval import Retriever
from app.schemas import ChatRequest


@pytest.fixture(scope='module')
def retriever():
    return Retriever()


def selection(section='talent', names=(), related_to=()):
    return QueryPlan(queries=['查阅对象效果原文'], selection=CatalogSelection(
        section=section, names=list(names), related_to=list(related_to)))


def test_faction_catalog_returns_effects_and_relationship_evidence(retriever):
    evidence= retriever.search_plan('和河洛相关的天赋有哪些？',selection(related_to=['河洛']))
    originals={r['entity']:r for r in evidence if r['field']=='original'}
    assert len(originals)==17
    assert {'钱生战力','自我奉献','最终守卫','河洛来客','河洛新援','河洛精兵','河洛增援','河洛强援'} <= originals.keys()
    assert '2能量' in originals['河洛新援']['body']
    assert '非【河洛】' in originals['多彩古币']['body']
    assert originals['古币翻新']['relation_kind']=='related_card'
    assert any(r['entity']=='古币翻新' and r['field']=='relatedCards' and '河洛' in r['body'] for r in evidence)
    assert all(r['selection_total']==r['selection_returned']==17 for r in evidence)
    assert all(r['body'] != '初始天赋' for r in evidence)


def test_named_catalog_includes_all_previous_objects(retriever):
    names=['河洛来客','河洛精兵','河洛增援','河洛强援','河洛新援']
    rows=retriever.search_plan('每一个天赋的具体效果是什么',selection(names=names))
    assert {r['entity'] for r in rows}==set(names)
    assert all(r['field']=='original' for r in rows)
    assert retriever.search_plan('不存在的天赋',selection(names=['不存在的天赋']))==[]


def test_catalog_generalizes_to_equipment_and_reports_partial_lists(retriever):
    names=['风暴巨剑','圣者法典']
    rows=retriever.search_plan('分别讲讲',selection('equipment',names=names))
    assert {r['entity'] for r in rows}==set(names)
    assert all(r['field']=='original' for r in rows)
    all_rows=retriever.search_plan('所有天赋效果',selection())
    assert len([r for r in all_rows if r['field']=='original'])==24
    assert all(r['selection_total']>r['selection_returned']==24 for r in all_rows)


def test_body_and_section_match_is_not_discarded_at_moderate_similarity(retriever):
    row=retriever.by_id['WX-talent-636219-original']
    ranked=Retriever([row]).rank('和河洛相关的天赋有哪些？',semantic_scores={row['id']:.59})
    assert ranked and ranked[0][1]['entity']=='钱生战力'


@pytest.mark.parametrize('names,section,current',[
    (['河洛来客','河洛精兵','河洛增援','河洛强援','河洛新援'],'talent','每一个天赋的具体效果是什么'),
    (['风暴巨剑','圣者法典'],'equipment','把这两件分别讲清楚，先讲第二件'),
])
async def test_both_model_stages_receive_entire_chronological_dialogue(retriever,names,section,current):
    history=[{'role':'user','content':'之前聊过的局面：'+('我有3能量。'*1100)},
             {'role':'assistant','content':'我记住这个条件了。'},
             {'role':'user','content':'接下来聊这些：'+'、'.join(names)},
             {'role':'assistant','content':'这些分别是：'+'、'.join(names)+'。之前的数值说成999能量，需要重新核对。'}]
    calls=[]
    def handler(request):
        payload=json.loads(request.content)
        assert payload['messages'][1:-1]==history
        assert [m['role'] for m in payload['messages']]==['system','user','assistant','user','assistant','user']
        data=json.loads(payload['messages'][-1]['content'])
        assert 'history' not in data
        calls.append(data)
        if 'catalog' in data:
            assert data['question']==current
            result={'intent':'knowledge','query':'这些对象的具体效果','search':selection(section,names=names).model_dump()}
        else:
            assert data['query']==current  # No phrase-specific query rewrite at generation.
            assert {r['entity'] for r in data['evidence']}==set(names)
            assert all('999能量' not in r['body'] for r in data['evidence'])
            result={'answer':'来，按刚才的对象逐个看。','source_ids':[r['id'] for r in data['evidence']],
                    'quotes':[{'source_id':r['id'],'quote':r['body'][:360]} for r in data['evidence']]}
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(result,ensure_ascii=False)},'finish_reason':'stop'}]})
    settings=Settings(retrieval_backend='lexical',base_url='https://model.test/v1',api_key='test',model='deepseek-test')
    result=await Agent(settings,llm=LLM(settings,httpx.MockTransport(handler)),retriever=retriever).chat(ChatRequest(message=current,history=history))
    assert result.status=='answered' and len(result.sources)==len(names)
    assert len(calls)==2
    assert all(call['history_messages']==4 for call in result.model_calls)


@pytest.mark.parametrize('model,thinking,expected',[
    ('deepseek-test','auto',{'type':'enabled'}),
    ('deepseek-test','disabled',{'type':'disabled'}),
    ('other-model','auto',None),
])
async def test_thinking_is_configurable(model,thinking,expected):
    def handler(request):
        payload=json.loads(request.content)
        assert payload.get('thinking')==expected
        assert payload['max_tokens']==4096
        result={'intent':'chitchat','query':'你好','reply':'你好呀。'}
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(result)},'finish_reason':'stop'}]})
    settings=Settings(base_url='https://model.test/v1',api_key='test',model=model,thinking=thinking)
    await LLM(settings,httpx.MockTransport(handler)).decide('你好',[],{})

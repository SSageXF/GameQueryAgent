import asyncio
import json
import httpx
import pytest
from app.agent import Agent
from app.config import Settings
from app.intent import Decision
from app.llm import LLM, AgentError
from app.query import fallback_plan
from app.retrieval import Retriever
from app.schemas import ChatRequest

@pytest.fixture(scope='module')
def retriever():
    return Retriever()

def settings(**kwargs):
    return Settings(retrieval_backend='lexical', base_url='https://model.test/v1', api_key='TEST_SECRET', model='deepseek-test', **kwargs)

def response(value):
    return httpx.Response(200, json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value,ensure_ascii=False)}}],
                                   'usage':{'prompt_tokens':100,'completion_tokens':40,'completion_tokens_details':{'reasoning_tokens':0}}})

async def test_model_decides_unseen_wording_and_combines_plan(retriever):
    calls=[]
    def handler(request):
        payload=json.loads(request.content); data=json.loads(payload['messages'][1]['content']); calls.append(data)
        assert payload['thinking']=={'type':'enabled'}
        if 'catalog' in data:
            assert 'entity_names' not in data['catalog']
            assert data['question']=='兜里就两点，还能从店里带个英雄走不？'
            return response({'intent':'advice','query':'只有2点能量，能购买英雄吗？','search':fallback_plan('英雄购买费用').model_dump()})
        row=next(r for r in data['evidence'] if r['id']=='E03')
        return response({'answer':'普通英雄要3点能量，你现在只有2点，还差1点。','source_ids':[row['id']],
                         'quotes':[{'source_id':row['id'],'quote':row['body'][:100]}]})
    result=await Agent(settings(),llm=LLM(settings(),httpx.MockTransport(handler)),retriever=retriever).chat(ChatRequest(message='兜里就两点，还能从店里带个英雄走不？'))
    assert result.intent=='advice' and result.routing['status']=='model'
    assert len(calls)==2
    assert [c['stage'] for c in result.model_calls]==['intent_planning','generation']
    assert all(c['reasoning_tokens']==0 for c in result.model_calls)
    assert result.sources[0].excerpt in retriever.by_id['E03']['body']
    assert '资料范围：' not in result.answer

@pytest.mark.parametrize('decision,expected_status',[
    ({'intent':'chitchat','query':'又输了，有点泄气','reply':'先歇一会儿，等你想复盘了我陪你看。'},'answered'),
    ({'intent':'out_of_scope','query':'帮我登录领奖','reply':'我没法登录账号或领取奖励，你需要在游戏里操作。'},'unsupported'),
    ({'intent':'advice','query':'这轮怎么站','clarification':'你场上有哪些英雄呀？'},'needs_clarification'),
])
async def test_model_direct_routes_do_not_retrieve_or_generate(retriever,monkeypatch,decision,expected_status):
    monkeypatch.setattr(retriever,'search_plan',lambda *a:pytest.fail('must not retrieve'))
    seen=[]
    def handler(request):
        data=json.loads(json.loads(request.content)['messages'][1]['content']);seen.append(data)
        assert 'catalog' in data
        return response(decision)
    result=await Agent(settings(),llm=LLM(settings(),httpx.MockTransport(handler)),retriever=retriever).chat(ChatRequest(message=decision['query']))
    assert result.status==expected_status and not result.sources
    assert len(seen)==len(result.model_calls)==1

@pytest.mark.parametrize('quote',['普通英雄需要八点能量','普通英雄…能量',None])
async def test_inexact_quote_keeps_answer_and_uses_real_reference(retriever,quote):
    data={'answer':'普通英雄需要3点能量。','source_ids':['E03'],'quotes':[] if quote is None else [{'source_id':'E03','quote':quote}]}
    result = await LLM(settings(),httpx.MockTransport(lambda r:response(data))).generate('买牌费用',[],[retriever.by_id['E03']],'knowledge')
    assert result.answer == data['answer']
    assert result.source_ids == ['E03']
    assert result.quotes[0].quote in retriever.by_id['E03']['body']
    assert result.quotes[0].kind == 'reference'

async def test_irrelevant_evidence_may_return_no_source(retriever):
    data={'answer':'这部分我还没查到，能补充卡牌原文吗？','source_ids':[],'quotes':[],'insufficient_evidence':True}
    result=await LLM(settings(),httpx.MockTransport(lambda r:response(data))).generate('不存在的技能',[],[retriever.by_id['E03']],'knowledge')
    assert result.insufficient_evidence and not result.source_ids

async def test_generation_failure_returns_sources_and_diagnostics(retriever):
    def handler(request):
        data=json.loads(json.loads(request.content)['messages'][1]['content'])
        if 'catalog' in data:
            return response({'intent':'knowledge','query':'英雄购买费用','search':fallback_plan('英雄购买费用').model_dump()})
        return httpx.Response(500,text='secret')
    result=await Agent(settings(),llm=LLM(settings(),httpx.MockTransport(handler)),retriever=retriever).chat(ChatRequest(message='英雄购买费用'))
    assert result.intent=='knowledge' and result.status=='partial_answer'
    assert result.generation_error=='model_failure'
    assert 'E03' in result.retrieved_ids and result.sources
    assert len(result.model_calls)==2
    assert result.model_calls[-1]['success'] is False
    assert 'secret' not in result.model_dump_json()

async def test_request_traces_isolated_during_concurrent_chat(retriever):
    async def handler(request):
        data=json.loads(json.loads(request.content)['messages'][1]['content'])
        await asyncio.sleep(.01)
        return response({'intent':'chitchat','query':data['question'],'reply':'在呢，慢慢聊。'})
    agent=Agent(settings(),llm=LLM(settings(),httpx.MockTransport(handler)),retriever=retriever)
    results=await asyncio.gather(*(agent.chat(ChatRequest(message=q)) for q in ['在吗','聊会儿']))
    assert all(len(r.model_calls)==1 for r in results)


def test_non_search_intent_ignores_unused_example_fields():
    result=Decision.model_validate({'intent':'chitchat','query':'陪我聊聊','reply':'我在呢。',
                                    'search':{'queries':[]},'clarification':'unused'})
    assert result.search is None and result.clarification is None


def test_advice_adds_trigger_definitions_without_guessing(retriever):
    evidence=[retriever.by_id['WX-hero-1111-original'],retriever.by_id['WX-hero-1281-original']]
    support=retriever.supporting_mechanics(evidence,'万象大赛')
    assert {r['entity'] for r in support}=={'登场','整备'}
    assert any('进入场上时触发' in r['body'] for r in support)

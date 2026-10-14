import json

import httpx
import pytest

from app.agent import Agent, ROUTING_UNAVAILABLE
from app.config import Settings
from app.intent import Decision
from app.llm import LLM
from app.query import fallback_plan
from app.retrieval import Retriever
from app.schemas import ChatRequest


@pytest.fixture(scope='module')
def retriever():
    return Retriever()


async def test_unsupported_replies_are_model_generated_for_each_context(retriever,monkeypatch):
    monkeypatch.setattr(retriever,'search_plan',lambda *a:pytest.fail('Unsupported requests must not retrieve'))
    history=[]
    pairs=[('查询我的战绩','我无法读取你的战绩。如果你愿意提供对局数据，我可以帮你分析。'),
           ('查询我的好友在线情况呢','我没有好友在线状态的数据接口，需要你在游戏内查看。'),
           ('王者荣耀的小乔技能是啥','我目前专注王者万象棋，王者荣耀的技能资料不在这个助手的范围内。')]
    def handler(request):
        payload=json.loads(request.content)
        assert payload['messages'][1:-1]==history
        query=json.loads(payload['messages'][-1]['content'])['question']
        assert 'evidence' not in payload['messages'][-1]['content']
        result={'intent':'out_of_scope','query':query,'reply':dict(pairs)[query]}
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(result)}}]})
    settings=Settings(base_url='https://model.test/v1',api_key='test',model='test',retrieval_backend='lexical')
    agent=Agent(settings,llm=LLM(settings,httpx.MockTransport(handler)),retriever=retriever)
    for question,reply in pairs:
        result=await agent.chat(ChatRequest(message=question,history=history))
        assert result.answer==reply and result.status=='unsupported'
        assert len(result.model_calls)==1 and not result.sources and not result.retrieved_ids
        history.extend([{'role':'user','content':question},{'role':'assistant','content':reply}])


def test_unsupported_decision_cannot_silently_drop_model_reply():
    with pytest.raises(ValueError,match='short reply'):
        Decision(intent='out_of_scope',query='好友在线吗？')


async def test_mixed_request_uses_model_limitation_and_answers_supported_part(retriever):
    limitation='我读不到你的好友在线状态，你可以在游戏内查看。'
    def handler(request):
        data=json.loads(json.loads(request.content)['messages'][-1]['content'])
        if 'catalog' in data:
            result={'intent':'knowledge','query':'英雄购买费用','restricted':True,'limitation':limitation,
                    'search':fallback_plan('英雄购买费用').model_dump()}
        else:
            result={'answer':'英雄牌基础消耗3点能量。','source_ids':['E03'],
                    'quotes':[{'source_id':'E03','quote':retriever.by_id['E03']['body']}]}
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(result)}}]})
    settings=Settings(base_url='https://model.test/v1',api_key='test',model='test',retrieval_backend='lexical')
    result=await Agent(settings,llm=LLM(settings,httpx.MockTransport(handler)),retriever=retriever).chat(
        ChatRequest(message='看看我好友在不在线，再说说英雄买牌费用'))
    assert result.answer.startswith(limitation) and '3点能量' in result.answer
    assert '个人战绩' not in result.answer and len(result.model_calls)==2


async def test_router_outage_is_reported_as_degraded_reply(retriever):
    settings=Settings(base_url='https://model.test/v1',api_key='test',model='test',retrieval_backend='lexical')
    llm=LLM(settings,httpx.MockTransport(lambda r:httpx.Response(500)))
    result=await Agent(settings,llm=llm,retriever=retriever).chat(ChatRequest(message='查询我的战绩'))
    assert result.answer==ROUTING_UNAVAILABLE
    assert result.status=='partial_answer' and result.generation_error=='model_failure'
    assert result.routing['status']=='fallback' and not result.sources

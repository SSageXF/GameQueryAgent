import json

import httpx
import pytest

from app.context import prepare
from app.intent import classify
from app.config import Settings
from app.llm import LLM, AgentError
from app.query import fallback_plan
from app.retrieval import Retriever
from app.schemas import Message


@pytest.mark.parametrize('followup', ['你上面说的讲详细点', '再详细解释一下', '展开说说'])
def test_topic_elaboration(followup):
    history = [Message(role='user', content='万象大赛有几个人，怎么赢？'),
               Message(role='assistant', content='不可信的历史答案：八个人。')]
    context = prepare(followup, history)
    assert '万象大赛' in context.query
    assert '八个人' not in context.query
    assert 'R01' in {r['id'] for r in Retriever().search_plan(context.query, fallback_plan(context.query))}


def test_purchase_intent_and_fallback_cost():
    question = '现在我场上有曹操，商店里有李白，孙尚香，蔡文姬，武则天，我只有3能量，我可以怎么买？'
    assert classify(question).intent == 'advice'
    assert '英雄购买费用 能量' in fallback_plan(question).queries


@pytest.mark.parametrize('always_truncated', [False, True])
async def test_truncation_retries_once_with_bounded_budget(always_truncated):
    budgets = []
    def handler(request):
        budgets.append(json.loads(request.content)['max_tokens'])
        truncated = len(budgets) == 1 or always_truncated
        return httpx.Response(200, json={'choices': [{
            'finish_reason': 'length' if truncated else 'stop',
            'message': {'content': '' if truncated else json.dumps({'answer': '你好', 'source_ids': []})}}]})
    model = LLM(Settings(retrieval_backend='lexical', base_url='https://test.invalid/v1', api_key='test', model='test'), httpx.MockTransport(handler))
    if always_truncated:
        with pytest.raises(AgentError, match='完整生成') as error:
            await model.generate('你好', [], [], 'chitchat')
        assert error.value.code == 'model_output_truncated'
    else:
        assert (await model.generate('你好', [], [], 'chitchat')).answer == '你好'
    assert budgets == [700, 4000]

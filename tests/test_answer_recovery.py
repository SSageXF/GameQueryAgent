import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agent import Agent
from app.answers import resolve_answer
from app.config import Settings
from app.llm import LLM
from app.main import create_app
from app.query import fallback_plan
from app.retrieval import Retriever


@pytest.fixture
def short_record():
    return {'id': 'SHORT', 'title': '河洛新援·天赋组', 'body': '初始天赋', 'source_title': '万象棋知识站',
            'source_url': 'https://wzwxq.com/explore/talent-635014', 'collected_at': '2026-10-13',
            'version_scope': '测试快照', 'mode': '万象大赛', 'verification': 'wiki_snapshot', 'claim_type': 'wiki_reference'}


def encoded(**kwargs):
    return json.dumps({'answer': '河洛新援属于初始天赋。', **kwargs}, ensure_ascii=False)


def test_four_character_verbatim_quote_is_valid(short_record):
    result = resolve_answer(encoded(source_ids=['SHORT'], quotes=[{'source_id': 'SHORT', 'quote': '初始天赋'}]), [short_record])
    assert result.source_ids == ['SHORT']
    assert result.quotes[0].quote == '初始天赋' and result.quotes[0].kind == 'quote'


@pytest.mark.parametrize('quote', ['改写后的说法', '', None, 123, ['初始天赋']])
def test_invalid_quote_does_not_discard_answer(short_record, quote):
    result = resolve_answer(encoded(source_ids=['SHORT'], quotes=[{'source_id': 'SHORT', 'quote': quote}]), [short_record])
    assert result.answer == '河洛新援属于初始天赋。'
    assert result.quotes[0].quote == short_record['body']
    assert result.quotes[0].kind == 'reference'


def test_unknown_and_duplicate_ids_do_not_create_sources(short_record):
    result = resolve_answer(encoded(source_ids=['FAKE', 'SHORT', 'SHORT', {}], quotes=[
        {'source_id': 'FAKE', 'quote': '不在库里'}, {'source_id': 'SHORT', 'quote': '不匹配'},
        {'source_id': 'SHORT', 'quote': '初始天赋'}]), [short_record])
    assert result.source_ids == ['SHORT'] and len(result.quotes) == 1
    assert result.quotes[0].kind == 'quote'


@pytest.mark.parametrize('metadata', [
    {'source_ids': ['FAKE'], 'quotes': [{'source_id': 'FAKE', 'quote': '不存在的原文'}]},
    {'source_ids': None, 'quotes': 'bad shape'},
    {'source_ids': [], 'quotes': []},
])
def test_no_verifiable_source_keeps_answer_with_notice(short_record, metadata):
    result = resolve_answer(encoded(**metadata), [short_record])
    assert result.answer and not result.source_ids and not result.quotes
    assert result.notice


def test_insufficient_answer_drops_even_known_source_ids(short_record):
    result = resolve_answer(encoded(source_ids=['SHORT'], insufficient_evidence=True), [short_record])
    assert result.insufficient_evidence and not result.source_ids


@pytest.mark.parametrize('content', [
    '河洛新援属于初始天赋。',
    '{"answer":"河洛新援属于初始天赋。","quotes":[',
])
def test_plain_answer_or_damaged_citation_tail_is_recovered(short_record, content):
    result = resolve_answer(content, [short_record])
    assert result.answer == '河洛新援属于初始天赋。'
    assert not result.source_ids and result.notice


def settings():
    return Settings(retrieval_backend='lexical', base_url='https://model.test/v1', api_key='TEST_SECRET', model='test')


def completion(content, finish_reason='stop'):
    return httpx.Response(200, json={'choices': [{'message': {'content': content}, 'finish_reason': finish_reason}]})


async def test_unreadable_body_is_repaired_once(short_record):
    calls = []
    def handler(request):
        calls.append(request)
        return completion('{"answer":' if len(calls) == 1 else encoded(source_ids=['SHORT']))
    result = await LLM(settings(), httpx.MockTransport(handler)).generate('河洛相关天赋', [], [short_record], 'knowledge')
    assert result.answer and result.source_ids == ['SHORT'] and len(calls) == 2


async def test_completed_answer_survives_truncated_citations(short_record):
    calls = []
    def handler(request):
        calls.append(request)
        return completion('{"answer":"河洛新援属于初始天赋。","quotes":[', 'length')
    result = await LLM(settings(), httpx.MockTransport(handler)).generate('河洛相关天赋', [], [short_record], 'knowledge')
    assert result.answer and len(calls) == 1


async def test_null_message_is_repaired(short_record):
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, json={'choices': [{'message': None}]})
        return completion(encoded(source_ids=['SHORT']))
    result = await LLM(settings(), httpx.MockTransport(handler)).generate('河洛相关天赋', [], [short_record], 'knowledge')
    assert result.answer and len(calls) == 2


@pytest.mark.parametrize('behavior', ['short_quote', 'wrong_quote', 'unknown_source', 'broken_json', 'provider_down'])
def test_http_returns_content_instead_of_citation_error(short_record, monkeypatch, behavior):
    retriever = Retriever([short_record])
    monkeypatch.setattr(retriever, 'search_plan', lambda *args: [short_record])
    def handler(request):
        data = json.loads(json.loads(request.content)['messages'][1]['content'])
        if 'catalog' in data:
            return completion(json.dumps({'intent': 'knowledge', 'query': '和河洛相关的天赋有哪些？',
                'search': fallback_plan('河洛天赋').model_dump()}, ensure_ascii=False))
        if behavior == 'provider_down':
            return httpx.Response(503, text='private-provider-detail TEST_SECRET')
        if behavior == 'broken_json':
            return completion('{"answer":')
        return completion(encoded(source_ids=['FAKE' if behavior == 'unknown_source' else 'SHORT'],
            quotes=[{'source_id': 'SHORT' if behavior != 'unknown_source' else 'FAKE',
                     'quote': '初始天赋' if behavior == 'short_quote' else '改写的引用'}]))
    agent = Agent(settings(), llm=LLM(settings(), httpx.MockTransport(handler)), retriever=retriever)
    with TestClient(create_app(settings(), agent=agent)) as client:
        response = client.post('/api/chat', json={'message': '和河洛相关的天赋有哪些？'})
    assert response.status_code == 200
    result = response.json()
    assert result['answer'] and 'error' not in result
    assert 'TEST_SECRET' not in response.text and 'private-provider-detail' not in response.text
    if behavior in {'broken_json', 'provider_down'}:
        assert result['status'] == 'partial_answer' and result['generation_error']
        assert '初始天赋' in result['answer']
    elif behavior == 'unknown_source':
        assert result['sources'] == [] and result['notice']
    else:
        assert result['sources'][0]['excerpt'] == '初始天赋'

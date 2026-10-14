"""Keep usable answers while resolving citations only against retrieved records."""
import json
import re
from typing import Literal

from pydantic import BaseModel, Field


class Quote(BaseModel):
    source_id: str
    quote: str = Field(min_length=1, max_length=360)
    kind: Literal['quote', 'reference'] = 'quote'


class Generation(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    source_ids: list[str] = Field(default_factory=list, max_length=48)
    quotes: list[Quote] = Field(default_factory=list, max_length=48)
    insufficient_evidence: bool = False
    notice: str | None = None
    fallback_code: str | None = None


def read_answer(content):
    if not isinstance(content, str) or not content.strip():
        raise ValueError('No answer text')
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip()).strip()
    try:
        data = json.loads(text)
    except ValueError:
        # A complete answer may survive even when the later citation JSON is cut off.
        start = re.match(r'^\{\s*"answer"\s*:\s*', text)
        if start:
            answer, _ = json.JSONDecoder().raw_decode(text[start.end():])
            data = {'answer': answer}
        elif text.startswith(('{', '[')):
            raise ValueError('Incomplete structured answer')
        else:
            data = {'answer': text}
    if not isinstance(data, dict) or not isinstance(data.get('answer'), str):
        raise ValueError('Missing answer')
    # Source links come from our records. A generated URL never becomes provenance.
    answer = re.sub(r'\[([^\]]+)\]\(https?://[^)]+\)', r'\1', data['answer'])
    answer = re.sub(r'https?://\S+|www\.\S+', '', answer).strip()
    if not answer:
        raise ValueError('Empty answer')
    return {**data, 'answer': answer[:12000]}


def resolve_answer(content, evidence):
    data = read_answer(content)
    allowed = {row['id']: row for row in evidence}
    ids = data.get('source_ids', [])
    ids = [ids] if isinstance(ids, str) else ids if isinstance(ids, list) else []
    supplied = data.get('quotes', [])
    supplied = supplied if isinstance(supplied, list) else []
    supplied = [q for q in supplied if isinstance(q, dict) and isinstance(q.get('source_id'), str)]
    selected = []
    for key in [*ids, *(q['source_id'] for q in supplied)]:
        if isinstance(key, str) and key in allowed and key not in selected and allowed[key]['body'].strip():
            selected.append(key)
    insufficient = data.get('insufficient_evidence') is True
    quotes = []
    for key in ([] if insufficient else selected[:48]):
        body = allowed[key]['body']
        exact = next((q['quote'] for q in supplied if q['source_id'] == key
                      and isinstance(q.get('quote'), str) and q['quote'].strip() and q['quote'] in body), None)
        # Keep the answer; do not display a paraphrase as a verbatim source quote.
        quotes.append(Quote(source_id=key, quote=(exact or body)[:360],
                            kind='quote' if exact else 'reference'))
    notice = None
    if evidence and not insufficient and not quotes:
        notice = '这次回答未附上可核验的来源，供你参考。'
    return Generation(answer=data['answer'], source_ids=[q.source_id for q in quotes], quotes=quotes,
                      insufficient_evidence=insufficient, notice=notice)


def evidence_fallback(evidence, code):
    rows = [r for r in evidence if r['body'].strip()][:6]
    return Generation(
        answer=('我先把查到的相关资料列给你：\n\n' + '\n\n'.join(f"{r['title']}：\n{r['body'][:300]}" for r in rows))[:3000],
        source_ids=[r['id'] for r in rows],
        quotes=[Quote(source_id=r['id'], quote=r['body'][:360], kind='reference') for r in rows],
        notice='模型暂时没能完成整理，以上是资料原文摘录。', fallback_code=code)

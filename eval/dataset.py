"""Validate fixed evaluation inputs before starting any model calls."""
import json
import re
from collections import Counter

from app.schemas import ChatRequest


def evidence_groups(turn):
    return turn.get('expected_knowledge_groups') or [[key] for key in turn['expected_knowledge_ids']]


def validate_cases(cases, knowledge_ids):
    seen=set()
    for case in cases:
        if case['id'] in seen:raise ValueError('Duplicate case ID: '+case['id'])
        seen.add(case['id'])
        if not case['turns']:raise ValueError('Empty case: '+case['id'])
        for turn in case['turns']:
            ChatRequest(message=turn['message'],history=turn.get('history',[]))
            if turn['expected_intent'] not in {'knowledge','advice','chitchat','out_of_scope'}:
                raise ValueError('Invalid intent: '+case['id'])
            if not turn.get('expected_behavior') or not turn.get('answer_points'):
                raise ValueError('Missing behavior/answer points: '+case['id'])
            if not turn['required_groups'] or any(not group for group in turn['required_groups']):
                raise ValueError('Missing answer assertions: '+case['id'])
            for pattern in [p for group in turn['required_groups'] for p in group]+turn['forbidden_patterns']:
                re.compile(pattern)
            groups=evidence_groups(turn)
            if any(not group for group in groups):raise ValueError('Empty evidence group: '+case['id'])
            statuses=turn.get('accepted_statuses',[turn['expected_status']])
            if not statuses or set(statuses)-{'answered','partial_answer','needs_clarification','insufficient_evidence','unsupported'}:
                raise ValueError('Invalid accepted status: '+case['id'])
            ids=set(turn['expected_knowledge_ids']) | {key for group in groups for key in group} | set(turn.get('optional_source_ids',[]))
            if ids-knowledge_ids:raise ValueError('Unknown knowledge IDs: '+','.join(sorted(ids-knowledge_ids)))
    return {'case_count':len(cases),'turn_count':sum(len(c['turns']) for c in cases),
            'intents':dict(Counter(t['expected_intent'] for c in cases for t in c['turns'])),
            'multi_turn_cases':sum(len(c['turns'])>=2 for c in cases),
            'tags':dict(Counter(tag for c in cases for tag in c.get('tags',[])))}


def read_cases(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

"""Re-score saved visible Agent results with an audited dataset; never calls a model."""
import argparse
import hashlib
import json
import statistics
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from app.config import ROOT
from eval.dataset import read_cases, validate_cases
from eval.run import judge, rate, latency


def rescore(source, dataset, output):
    if source.resolve()==output.resolve():raise ValueError('Preserve the original report')
    raw=source.read_bytes()
    report=deepcopy(json.loads(raw))
    cases=read_cases(dataset)
    knowledge={r['id']:r for p in ('data/knowledge.json','data/wiki/records.json')
               for r in json.loads((ROOT/p).read_text(encoding='utf-8'))}
    for path,digest in report['knowledge_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:
            raise ValueError('Knowledge snapshot changed; preserve the original evidence for rescore')
    report['dataset_coverage']=validate_cases(cases,set(knowledge))
    turns={(c['id'],i+1):t for c in cases for i,t in enumerate(c['turns'])}
    for row in report['rows']:
        turn=turns[(row['case_id'],row['turn'])]
        if turn['message']!=row['message'] or turn.get('history',row.get('input_history',[]))!=row.get('input_history',[]):
            raise ValueError('Cannot rescore changed input: '+row['case_id'])
        row['expectation']=turn
        row['expected_knowledge_ids']=turn['expected_knowledge_ids']
        started=time.perf_counter()
        if row.get('result'):
            row['judgement']=judge(turn,row['result'],knowledge)
        row['rescore_judge_ms']=round((time.perf_counter()-started)*1000,3)
    rows=report['rows']
    supported=[r for r in rows if r['judgement']['retrieval_hit'] is not None]
    advice=[r for r in rows if r.get('advice_applicable')]
    case_ids={r['case_id'] for r in rows}
    report['summary'].update(
        rescore_judge_latency=latency([r['rescore_judge_ms'] for r in rows]),
        intent_accuracy=rate(sum(r['judgement']['intent_correct'] for r in rows),len(rows)),
        retrieval_hit_rate=rate(sum(r['judgement']['retrieval_hit'] for r in supported),len(supported)),
        mean_evidence_recall=statistics.mean(r['judgement']['retrieval_recall'] for r in supported) if supported else None,
        answer_pass_rate=rate(sum(r['judgement']['answer_pass'] for r in rows),len(rows)),
        case_answer_pass_rate=rate(sum(all(r['judgement']['answer_pass'] for r in rows if r['case_id']==key) for key in case_ids),len(case_ids)),
        advice_rule_pass_rate=rate(sum(bool((r['judgement'].get('advice_rubric') or {}).get('passed')) for r in advice),len(advice)))
    report.update(evaluation_kind='saved_responses_rescored',new_model_calls=0,
                  rescored_at=datetime.now(timezone.utc).isoformat(),source_report=str(source),
                  source_report_sha256=hashlib.sha256(raw).hexdigest(),
                  original_dataset_sha256=report['dataset_sha256'],dataset_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
                  original_scorer_sha256=report['scorer_sha256'],
                  scorer_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('eval/run.py','eval/advice.py','eval/text.py','eval/dataset.py','eval/rescore.py')})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 已保存回答重新评分','', '未重新调用Agent或模型；回答、历史、来源、调用次数和耗时原样保留。新规则仅用于评分，原报告保持不变。','',
           '| 指标 | 分子/分母 | 比例 |','| --- | --- | --- |']
    for key in ('intent_accuracy','retrieval_hit_rate','answer_pass_rate','case_answer_pass_rate','success_rate','advice_rule_pass_rate'):
        metric=report['summary'][key];lines.append(f"| {key} | {metric['numerator']}/{metric['denominator']} | {metric['rate']} |")
    lines+=['','| 案例/轮 | 回答规则通过 |','| --- | --- |']
    lines += [f"| {r['case_id']}/{r['turn']} | {r['judgement']['answer_pass']} |" for r in rows]
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--dataset',type=Path,default=ROOT/'eval/cases.jsonl')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.source.resolve()==args.output.resolve():parser.error('Use a new output path; preserve the original report')
    result=rescore(args.source,args.dataset,args.output)
    print(json.dumps(result['summary'],ensure_ascii=False,indent=2))

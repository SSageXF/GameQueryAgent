# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 4/4 | 1.0 |
| retrieval_hit_rate | 4/4 | 1.0 |
| answer_pass_rate | 0/4 | 0.0 |
| case_answer_pass_rate | 0/4 | 0.0 |
| advice_rule_pass_rate | 1/4 | 0.25 |
| success_rate | 3/4 | 0.75 |
| response_rate | 4/4 | 1.0 |

成功调用耗时：{'n': 3, 'median_ms': 15045.52, 'p95_ms': 18083.92}
失败调用耗时：{'n': 1, 'median_ms': 30568.85, 'p95_ms': 30568.85}
实际模型调用数：12

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| A02/1 | True | False | 18083.922 |
| A03/1 | True | False | 12493.389 |
| A05/1 | True | False | 15045.522 |
| A06/1 | False | False | 30568.848 |

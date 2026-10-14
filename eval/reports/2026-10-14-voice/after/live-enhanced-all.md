# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 6/6 | 1.0 |
| retrieval_hit_rate | 2/2 | 1.0 |
| answer_pass_rate | 5/6 | 0.8333 |
| case_answer_pass_rate | 3/4 | 0.75 |
| advice_rule_pass_rate | 0/0 | None |
| success_rate | 6/6 | 1.0 |
| response_rate | 6/6 | 1.0 |

成功调用耗时：{'n': 6, 'median_ms': 3407.96, 'p95_ms': 12720.32}
失败调用耗时：{'n': 0, 'median_ms': None, 'p95_ms': None}
实际模型调用数：9

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| VOICE01/1 | True | True | 2596.458 |
| VOICE01/2 | True | True | 4840.947 |
| VOICE01/3 | True | True | 3240.355 |
| VOICE02/1 | True | True | 3575.573 |
| VOICE03/1 | True | False | 12720.315 |
| VOICE04/1 | True | True | 2656.566 |

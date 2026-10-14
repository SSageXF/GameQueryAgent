# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 6/6 | 1.0 |
| retrieval_hit_rate | 2/2 | 1.0 |
| answer_pass_rate | 6/6 | 1.0 |
| case_answer_pass_rate | 4/4 | 1.0 |
| advice_rule_pass_rate | 0/0 | None |
| success_rate | 6/6 | 1.0 |
| response_rate | 6/6 | 1.0 |

成功调用耗时：{'n': 6, 'median_ms': 2738.45, 'p95_ms': 4292.73}
失败调用耗时：{'n': 0, 'median_ms': None, 'p95_ms': None}
实际模型调用数：8

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| VOICE01/1 | True | True | 2383.285 |
| VOICE01/2 | True | True | 4246.498 |
| VOICE01/3 | True | True | 2857.394 |
| VOICE02/1 | True | True | 4292.73 |
| VOICE03/1 | True | True | 2619.507 |
| VOICE04/1 | True | True | 2105.869 |

# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 5/5 | 1.0 |
| retrieval_hit_rate | 2/2 | 1.0 |
| answer_pass_rate | 5/5 | 1.0 |
| case_answer_pass_rate | 3/3 | 1.0 |
| advice_rule_pass_rate | 0/0 | None |
| success_rate | 4/5 | 0.8 |
| response_rate | 5/5 | 1.0 |

成功调用耗时：{'n': 4, 'median_ms': 2532.95, 'p95_ms': 4027.93}
失败调用耗时：{'n': 1, 'median_ms': 8487.93, 'p95_ms': 8487.93}
实际模型调用数：7

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| VOICE01/1 | True | True | 2663.706 |
| VOICE01/2 | False | True | 8487.927 |
| VOICE01/3 | True | True | 2402.203 |
| VOICE02/1 | True | True | 4027.931 |
| VOICE04/1 | True | True | 2122.947 |

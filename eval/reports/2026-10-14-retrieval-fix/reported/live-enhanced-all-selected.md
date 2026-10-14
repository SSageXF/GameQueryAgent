# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 4/4 | 1.0 |
| retrieval_hit_rate | 4/4 | 1.0 |
| answer_pass_rate | 4/4 | 1.0 |
| case_answer_pass_rate | 1/1 | 1.0 |
| advice_rule_pass_rate | 0/0 | None |
| success_rate | 3/4 | 0.75 |
| response_rate | 4/4 | 1.0 |

成功调用耗时：{'n': 3, 'median_ms': 8913.6, 'p95_ms': 9206.68}
失败调用耗时：{'n': 1, 'median_ms': 6839.72, 'p95_ms': 6839.72}
实际模型调用数：8

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| MT06/1 | True | True | 8913.598 |
| MT06/2 | True | True | 9206.679 |
| MT06/3 | True | True | 7252.599 |
| MT06/4 | False | True | 6839.721 |

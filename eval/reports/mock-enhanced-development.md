# MOCK / enhanced / development

Mock 仅验证链路，不代表模型质量。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 23/23 | 1.0 |
| retrieval_hit_rate | 13/13 | 1.0 |
| answer_pass_rate | 23/23 | 1.0 |
| case_answer_pass_rate | 21/21 | 1.0 |
| success_rate | 23/23 | 1.0 |

成功调用耗时：{'n': 23, 'median_ms': 0.65, 'p95_ms': 3.42}
失败调用耗时：{'n': 0, 'median_ms': None, 'p95_ms': None}
实际模型调用数：0

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| K01/1 | True | True | 7.643 |
| K02/1 | True | True | 1.567 |
| K03/1 | True | True | 0.662 |
| K04/1 | True | True | 0.617 |
| K05/1 | True | True | 0.789 |
| K06/1 | True | True | 0.611 |
| A01/1 | True | True | 3.422 |
| A02/1 | True | True | 1.844 |
| A03/1 | True | True | 0.96 |
| A04/1 | True | True | 0.804 |
| S01/1 | True | True | 0.442 |
| S02/1 | True | True | 0.105 |
| S03/1 | True | True | 0.06 |
| O01/1 | True | True | 0.052 |
| O02/1 | True | True | 0.172 |
| O03/1 | True | True | 0.055 |
| U01/1 | True | True | 0.062 |
| V01/1 | True | True | 0.051 |
| P01/1 | True | True | 0.602 |
| M01/1 | True | True | 1.064 |
| MT01/1 | True | True | 0.649 |
| MT01/2 | True | True | 1.147 |
| MT01/3 | True | True | 0.828 |

# MOCK / baseline / development

Mock 仅验证链路，不代表模型质量。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 23/23 | 1.0 |
| retrieval_hit_rate | 13/13 | 1.0 |
| answer_pass_rate | 22/23 | 0.9565 |
| case_answer_pass_rate | 20/21 | 0.9524 |
| success_rate | 23/23 | 1.0 |

成功调用耗时：{'n': 23, 'median_ms': 0.37, 'p95_ms': 1.09}
失败调用耗时：{'n': 0, 'median_ms': None, 'p95_ms': None}
实际模型调用数：0

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| K01/1 | True | True | 0.614 |
| K02/1 | True | True | 0.194 |
| K03/1 | True | True | 0.974 |
| K04/1 | True | True | 0.278 |
| K05/1 | True | True | 0.23 |
| K06/1 | True | True | 0.183 |
| A01/1 | True | True | 1.663 |
| A02/1 | True | False | 0.642 |
| A03/1 | True | True | 0.895 |
| A04/1 | True | True | 1.09 |
| S01/1 | True | True | 0.168 |
| S02/1 | True | True | 0.107 |
| S03/1 | True | True | 0.37 |
| O01/1 | True | True | 0.331 |
| O02/1 | True | True | 0.251 |
| O03/1 | True | True | 0.08 |
| U01/1 | True | True | 0.063 |
| V01/1 | True | True | 0.057 |
| P01/1 | True | True | 0.514 |
| M01/1 | True | True | 0.403 |
| MT01/1 | True | True | 0.698 |
| MT01/2 | True | True | 0.655 |
| MT01/3 | True | True | 0.62 |

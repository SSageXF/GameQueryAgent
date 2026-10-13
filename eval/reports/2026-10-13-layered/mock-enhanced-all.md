# MOCK / enhanced / all

Mock 仅验证链路，不代表模型质量。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 36/36 | 1.0 |
| retrieval_hit_rate | 24/24 | 1.0 |
| answer_pass_rate | 32/36 | 0.8889 |
| case_answer_pass_rate | 28/32 | 0.875 |
| advice_rule_pass_rate | 0/4 | 0.0 |
| success_rate | 36/36 | 1.0 |

成功调用耗时：{'n': 36, 'median_ms': 0.66, 'p95_ms': 1.38}
失败调用耗时：{'n': 0, 'median_ms': None, 'p95_ms': None}
实际模型调用数：0

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| K01/1 | True | True | 2.885 |
| K02/1 | True | True | 0.844 |
| K03/1 | True | True | 0.951 |
| K04/1 | True | True | 1.061 |
| K05/1 | True | True | 0.924 |
| K06/1 | True | True | 0.89 |
| A01/1 | True | True | 1.381 |
| A02/1 | True | False | 0.856 |
| A03/1 | True | False | 1.254 |
| A04/1 | True | True | 0.695 |
| S01/1 | True | True | 0.272 |
| S02/1 | True | True | 0.128 |
| S03/1 | True | True | 0.136 |
| O01/1 | True | True | 0.17 |
| O02/1 | True | True | 0.105 |
| O03/1 | True | True | 0.077 |
| U01/1 | True | True | 0.083 |
| V01/1 | True | True | 0.076 |
| P01/1 | True | True | 0.927 |
| M01/1 | True | True | 0.993 |
| H01/1 | True | True | 0.442 |
| H02/1 | True | True | 1.023 |
| H03/1 | True | True | 0.116 |
| MT01/1 | True | True | 0.445 |
| MT01/2 | True | True | 0.419 |
| MT01/3 | True | True | 0.476 |
| MT02/1 | True | True | 0.88 |
| MT02/2 | True | True | 0.97 |
| MT02/3 | True | True | 0.906 |
| WX01/1 | True | True | 0.396 |
| WX02/1 | True | True | 0.285 |
| WX03/1 | True | True | 0.686 |
| WX04/1 | True | True | 0.117 |
| WX05/1 | True | True | 0.431 |
| A05/1 | True | False | 1.011 |
| A06/1 | True | False | 0.635 |

# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 34/36 | 0.9444 |
| retrieval_hit_rate | 22/24 | 0.9167 |
| answer_pass_rate | 29/36 | 0.8056 |
| case_answer_pass_rate | 25/32 | 0.7812 |
| advice_rule_pass_rate | 0/4 | 0.0 |
| success_rate | 34/36 | 0.9444 |

成功调用耗时：{'n': 34, 'median_ms': 5339.99, 'p95_ms': 12305.55}
失败调用耗时：{'n': 2, 'median_ms': 293343.58, 'p95_ms': 573860.35}
实际模型调用数：24

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| K01/1 | True | True | 5278.355 |
| K02/1 | False | False | 573860.351 |
| K03/1 | True | False | 4430.604 |
| K04/1 | True | True | 6406.682 |
| K05/1 | True | True | 5026.725 |
| K06/1 | True | True | 4490.17 |
| A01/1 | True | True | 1.064 |
| A02/1 | True | False | 12305.554 |
| A03/1 | True | False | 6573.859 |
| A04/1 | True | True | 8.809 |
| S01/1 | True | True | 4161.747 |
| S02/1 | True | True | 5643.17 |
| S03/1 | True | False | 6638.953 |
| O01/1 | True | True | 0.187 |
| O02/1 | True | True | 0.14 |
| O03/1 | True | True | 0.124 |
| U01/1 | True | True | 0.121 |
| V01/1 | True | True | 0.613 |
| P01/1 | True | True | 5649.531 |
| M01/1 | True | True | 5401.616 |
| H01/1 | True | True | 6798.705 |
| H02/1 | True | True | 6797.215 |
| H03/1 | True | True | 0.209 |
| MT01/1 | True | True | 8019.415 |
| MT01/2 | True | True | 6542.473 |
| MT01/3 | True | True | 7323.426 |
| MT02/1 | True | True | 5162.467 |
| MT02/2 | True | True | 5749.416 |
| MT02/3 | True | True | 8975.82 |
| WX01/1 | True | True | 7011.733 |
| WX02/1 | True | True | 5021.997 |
| WX03/1 | True | True | 1.387 |
| WX04/1 | True | True | 0.161 |
| WX05/1 | True | True | 7245.994 |
| A05/1 | True | False | 14609.281 |
| A06/1 | False | False | 12826.81 |

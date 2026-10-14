# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 45/45 | 1.0 |
| retrieval_hit_rate | 23/30 | 0.7667 |
| answer_pass_rate | 28/45 | 0.6222 |
| case_answer_pass_rate | 21/36 | 0.5833 |
| advice_rule_pass_rate | 0/4 | 0.0 |
| success_rate | 45/45 | 1.0 |
| response_rate | 45/45 | 1.0 |

成功调用耗时：{'n': 45, 'median_ms': 5927.99, 'p95_ms': 11591.02}
失败调用耗时：{'n': 0, 'median_ms': None, 'p95_ms': None}
实际模型调用数：72

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| K01/1 | True | True | 9034.616 |
| K02/1 | True | True | 7148.866 |
| K03/1 | True | True | 7979.931 |
| K04/1 | True | True | 7927.049 |
| K05/1 | True | True | 8153.972 |
| K06/1 | True | True | 8698.677 |
| A01/1 | True | False | 3964.369 |
| A02/1 | True | False | 11645.742 |
| A03/1 | True | False | 17026.279 |
| A04/1 | True | False | 2598.883 |
| S01/1 | True | True | 2165.938 |
| S02/1 | True | True | 2173.876 |
| S03/1 | True | True | 2208.649 |
| O01/1 | True | True | 2279.772 |
| O02/1 | True | True | 2116.81 |
| O03/1 | True | True | 2322.393 |
| U01/1 | True | False | 8325.958 |
| V01/1 | True | False | 6022.505 |
| P01/1 | True | True | 8420.674 |
| M01/1 | True | True | 5284.306 |
| H01/1 | True | False | 6527.382 |
| H02/1 | True | True | 8375.199 |
| H03/1 | True | False | 2385.221 |
| MT01/1 | True | False | 2072.385 |
| MT01/2 | True | True | 7623.004 |
| MT01/3 | True | False | 2315.401 |
| MT02/1 | True | True | 7214.809 |
| MT02/2 | True | True | 7065.054 |
| MT02/3 | True | True | 7546.323 |
| WX01/1 | True | False | 1817.101 |
| WX02/1 | True | True | 3822.104 |
| WX03/1 | True | True | 2106.857 |
| WX04/1 | True | False | 2289.679 |
| WX05/1 | True | False | 4488.355 |
| A05/1 | True | False | 11591.025 |
| A06/1 | True | False | 11441.26 |
| K07/1 | True | True | 10775.053 |
| MT03/1 | True | True | 6608.523 |
| MT03/2 | True | True | 6067.939 |
| MT03/3 | True | True | 5927.986 |
| MT04/1 | True | False | 2142.88 |
| MT04/2 | True | False | 2259.824 |
| MT04/3 | True | True | 3282.556 |
| MT05/1 | True | True | 2337.985 |
| MT05/2 | True | True | 4818.003 |

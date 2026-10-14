# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 48/49 | 0.9796 |
| retrieval_hit_rate | 34/34 | 1.0 |
| answer_pass_rate | 41/49 | 0.8367 |
| case_answer_pass_rate | 29/37 | 0.7838 |
| advice_rule_pass_rate | 0/4 | 0.0 |
| success_rate | 47/49 | 0.9592 |
| response_rate | 49/49 | 1.0 |

成功调用耗时：{'n': 47, 'median_ms': 7367.59, 'p95_ms': 11753.73}
失败调用耗时：{'n': 2, 'median_ms': 19294.81, 'p95_ms': 19798.07}
实际模型调用数：85

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| K01/1 | True | True | 7399.144 |
| K02/1 | True | True | 7935.368 |
| K03/1 | True | True | 7028.664 |
| K04/1 | True | True | 9456.865 |
| K05/1 | True | True | 7680.878 |
| K06/1 | True | True | 6296.294 |
| A01/1 | True | True | 1928.001 |
| A02/1 | True | False | 11158.721 |
| A03/1 | True | False | 9838.677 |
| A04/1 | True | False | 7835.961 |
| S01/1 | True | True | 1848.212 |
| S02/1 | True | True | 1898.744 |
| S03/1 | True | True | 2181.429 |
| O01/1 | True | True | 2008.775 |
| O02/1 | True | True | 2170.494 |
| O03/1 | True | True | 1907.514 |
| U01/1 | True | False | 7967.036 |
| V01/1 | False | False | 18791.54 |
| P01/1 | True | True | 6144.583 |
| M01/1 | True | True | 9286.749 |
| H01/1 | False | True | 19798.07 |
| H02/1 | True | True | 8667.167 |
| H03/1 | True | False | 13271.377 |
| MT01/1 | True | True | 8711.464 |
| MT01/2 | True | True | 7838.445 |
| MT01/3 | True | True | 7413.501 |
| MT02/1 | True | True | 7220.465 |
| MT02/2 | True | True | 8244.62 |
| MT02/3 | True | True | 7735.996 |
| WX01/1 | True | True | 7367.588 |
| WX02/1 | True | True | 6130.135 |
| WX03/1 | True | True | 1967.411 |
| WX04/1 | True | True | 5283.497 |
| WX05/1 | True | True | 7147.691 |
| A05/1 | True | False | 9742.379 |
| A06/1 | True | False | 10758.319 |
| K07/1 | True | True | 15266.968 |
| MT03/1 | True | True | 7217.115 |
| MT03/2 | True | True | 5425.763 |
| MT03/3 | True | True | 4942.058 |
| MT04/1 | True | True | 2195.657 |
| MT04/2 | True | True | 2182.204 |
| MT04/3 | True | True | 2087.811 |
| MT05/1 | True | True | 2602.527 |
| MT05/2 | True | True | 8423.938 |
| MT06/1 | True | True | 8119.576 |
| MT06/2 | True | True | 11753.731 |
| MT06/3 | True | True | 7622.69 |
| MT06/4 | True | True | 6470.059 |

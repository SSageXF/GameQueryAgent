# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 49/49 | 1.0 |
| retrieval_hit_rate | 34/34 | 1.0 |
| answer_pass_rate | 42/49 | 0.8571 |
| case_answer_pass_rate | 30/37 | 0.8108 |
| advice_rule_pass_rate | 1/4 | 0.25 |
| success_rate | 48/49 | 0.9796 |
| response_rate | 49/49 | 1.0 |

成功调用耗时：{'n': 48, 'median_ms': 7082.01, 'p95_ms': 10753.58}
失败调用耗时：{'n': 1, 'median_ms': 4342.85, 'p95_ms': 4342.85}
实际模型调用数：86

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| K01/1 | True | True | 7123.944 |
| K02/1 | True | True | 6583.956 |
| K03/1 | True | True | 8401.769 |
| K04/1 | True | True | 8414.744 |
| K05/1 | True | True | 7291.374 |
| K06/1 | True | True | 7493.032 |
| A01/1 | True | True | 2382.122 |
| A02/1 | True | True | 10753.578 |
| A03/1 | True | False | 9971.907 |
| A04/1 | True | True | 7705.464 |
| S01/1 | True | True | 3076.367 |
| S02/1 | True | True | 2216.852 |
| S03/1 | True | False | 1717.586 |
| O01/1 | True | True | 1985.109 |
| O02/1 | True | True | 2182.248 |
| O03/1 | True | True | 2071.749 |
| U01/1 | False | True | 4342.845 |
| V01/1 | True | False | 8500.142 |
| P01/1 | True | True | 10075.536 |
| M01/1 | True | True | 7456.435 |
| H01/1 | True | True | 8315.901 |
| H02/1 | True | True | 8001.377 |
| H03/1 | True | False | 10972.661 |
| MT01/1 | True | True | 9782.457 |
| MT01/2 | True | True | 6452.201 |
| MT01/3 | True | True | 7181.326 |
| MT02/1 | True | True | 7613.71 |
| MT02/2 | True | True | 7397.93 |
| MT02/3 | True | True | 6873.702 |
| WX01/1 | True | True | 5980.899 |
| WX02/1 | True | True | 6921.44 |
| WX03/1 | True | True | 2086.608 |
| WX04/1 | True | True | 5385.957 |
| WX05/1 | True | True | 9025.413 |
| A05/1 | True | False | 9544.075 |
| A06/1 | True | False | 10673.242 |
| K07/1 | True | True | 15155.03 |
| MT03/1 | True | True | 6620.795 |
| MT03/2 | True | True | 6349.725 |
| MT03/3 | True | True | 4285.383 |
| MT04/1 | True | True | 1944.159 |
| MT04/2 | True | True | 1938.702 |
| MT04/3 | True | False | 2062.605 |
| MT05/1 | True | True | 2355.042 |
| MT05/2 | True | True | 6886.387 |
| MT06/1 | True | True | 6592.285 |
| MT06/2 | True | True | 9585.665 |
| MT06/3 | True | True | 7448.701 |
| MT06/4 | True | True | 7040.069 |

# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 49/49 | 1.0 |
| retrieval_hit_rate | 30/34 | 0.8824 |
| answer_pass_rate | 36/49 | 0.7347 |
| case_answer_pass_rate | 24/37 | 0.6486 |
| advice_rule_pass_rate | 0/4 | 0.0 |
| success_rate | 44/49 | 0.898 |
| response_rate | 49/49 | 1.0 |

成功调用耗时：{'n': 44, 'median_ms': 7687.41, 'p95_ms': 10429.0}
失败调用耗时：{'n': 5, 'median_ms': 7360.58, 'p95_ms': 19474.71}
实际模型调用数：85

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| K01/1 | True | True | 7481.978 |
| K02/1 | True | True | 10428.997 |
| K03/1 | True | True | 9624.07 |
| K04/1 | True | True | 9811.758 |
| K05/1 | True | True | 8358.509 |
| K06/1 | False | True | 19474.714 |
| A01/1 | True | True | 1888.9 |
| A02/1 | True | False | 9074.876 |
| A03/1 | True | False | 11335.359 |
| A04/1 | True | True | 1799.631 |
| S01/1 | True | True | 2292.713 |
| S02/1 | True | True | 2150.34 |
| S03/1 | True | True | 1962.555 |
| O01/1 | True | True | 2269.103 |
| O02/1 | True | False | 2121.145 |
| O03/1 | True | True | 3841.589 |
| U01/1 | True | False | 7521.144 |
| V01/1 | True | False | 10342.741 |
| P01/1 | True | True | 6958.158 |
| M01/1 | True | False | 9112.588 |
| H01/1 | True | False | 10099.247 |
| H02/1 | True | True | 8719.591 |
| H03/1 | True | False | 10310.066 |
| MT01/1 | True | True | 7661.708 |
| MT01/2 | True | True | 8366.787 |
| MT01/3 | True | True | 7796.139 |
| MT02/1 | True | True | 6672.475 |
| MT02/2 | True | False | 8156.775 |
| MT02/3 | True | True | 10092.409 |
| WX01/1 | False | True | 5207.209 |
| WX02/1 | True | True | 6551.106 |
| WX03/1 | True | True | 2217.222 |
| WX04/1 | True | True | 5895.75 |
| WX05/1 | False | True | 19190.792 |
| A05/1 | True | False | 9501.537 |
| A06/1 | True | False | 9545.952 |
| K07/1 | True | True | 11265.028 |
| MT03/1 | False | True | 7360.584 |
| MT03/2 | False | False | 6861.611 |
| MT03/3 | True | True | 7713.122 |
| MT04/1 | True | True | 2214.665 |
| MT04/2 | True | True | 2314.496 |
| MT04/3 | True | False | 2651.608 |
| MT05/1 | True | True | 3151.614 |
| MT05/2 | True | True | 7446.447 |
| MT06/1 | True | True | 8235.782 |
| MT06/2 | True | True | 8255.291 |
| MT06/3 | True | True | 8089.132 |
| MT06/4 | True | True | 7550.057 |

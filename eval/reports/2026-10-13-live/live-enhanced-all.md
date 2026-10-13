# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 32/36 | 0.8889 |
| retrieval_hit_rate | 20/24 | 0.8333 |
| answer_pass_rate | 29/36 | 0.8056 |
| case_answer_pass_rate | 25/32 | 0.7812 |
| advice_rule_pass_rate | 0/4 | 0.0 |
| success_rate | 32/36 | 0.8889 |

成功调用耗时：{'n': 32, 'median_ms': 4121.38, 'p95_ms': 7100.78}
失败调用耗时：{'n': 4, 'median_ms': 9642.81, 'p95_ms': 11057.27}
实际模型调用数：22

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| K01/1 | True | False | 4081.183 |
| K02/1 | True | True | 3819.14 |
| K03/1 | True | True | 3927.48 |
| K04/1 | True | True | 4483.526 |
| K05/1 | True | False | 4628.934 |
| K06/1 | True | True | 3789.877 |
| A01/1 | True | True | 1.819 |
| A02/1 | False | False | 9594.154 |
| A03/1 | True | False | 7100.783 |
| A04/1 | True | True | 0.592 |
| S01/1 | True | True | 4408.562 |
| S02/1 | True | True | 3820.065 |
| S03/1 | True | True | 5142.678 |
| O01/1 | True | True | 0.117 |
| O02/1 | True | True | 0.073 |
| O03/1 | True | True | 0.063 |
| U01/1 | True | True | 0.066 |
| V01/1 | True | True | 0.063 |
| P01/1 | True | True | 4554.739 |
| M01/1 | True | True | 4082.133 |
| H01/1 | True | True | 7065.644 |
| H02/1 | True | True | 6340.541 |
| H03/1 | True | True | 0.782 |
| MT01/1 | True | True | 6148.909 |
| MT01/2 | True | True | 4702.916 |
| MT01/3 | True | True | 4636.245 |
| MT02/1 | True | True | 4160.62 |
| MT02/2 | True | True | 6976.619 |
| MT02/3 | False | False | 11057.268 |
| WX01/1 | True | True | 6566.953 |
| WX02/1 | True | True | 5205.89 |
| WX03/1 | True | True | 1.33 |
| WX04/1 | True | True | 0.161 |
| WX05/1 | True | True | 7693.882 |
| A05/1 | False | False | 9502.847 |
| A06/1 | False | False | 9691.465 |

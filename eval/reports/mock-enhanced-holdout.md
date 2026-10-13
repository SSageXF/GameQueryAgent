# MOCK / enhanced / holdout

Mock 仅验证链路，不代表模型质量。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 6/6 | 1.0 |
| retrieval_hit_rate | 5/5 | 1.0 |
| answer_pass_rate | 6/6 | 1.0 |
| case_answer_pass_rate | 4/4 | 1.0 |
| success_rate | 6/6 | 1.0 |

成功调用耗时：{'n': 6, 'median_ms': 0.17, 'p95_ms': 0.87}
失败调用耗时：{'n': 0, 'median_ms': None, 'p95_ms': None}
实际模型调用数：0

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| H01/1 | True | True | 0.867 |
| H02/1 | True | True | 0.208 |
| H03/1 | True | True | 0.043 |
| MT02/1 | True | True | 0.172 |
| MT02/2 | True | True | 0.17 |
| MT02/3 | True | True | 0.166 |

# LIVE / enhanced / all

规则评分为代理指标，需人工检查事实依据和未覆盖的幻觉。

自动规则评分不等于语义正确率；模型质量评测与人工抽查状态见 JSON。

| 指标 | 分子 / 分母 | 比例 |
| --- | --- | --- |
| intent_accuracy | 13/13 | 1.0 |
| retrieval_hit_rate | 13/13 | 1.0 |
| answer_pass_rate | 13/13 | 1.0 |
| case_answer_pass_rate | 6/6 | 1.0 |
| advice_rule_pass_rate | 0/0 | None |
| success_rate | 12/13 | 0.9231 |
| response_rate | 13/13 | 1.0 |

成功调用耗时：{'n': 12, 'median_ms': 7289.1, 'p95_ms': 9071.21}
失败调用耗时：{'n': 1, 'median_ms': 5756.92, 'p95_ms': 5756.92}
实际模型调用数：26

| 案例 / 轮 | 成功 | 回答规则通过 | ms |
| --- | --- | --- | --- |
| MT01/1 | True | True | 7504.529 |
| MT01/2 | True | True | 6851.818 |
| MT01/3 | True | True | 7146.826 |
| WX01/1 | True | True | 9071.207 |
| WX04/1 | True | True | 4791.275 |
| WX05/1 | True | True | 8989.785 |
| MT03/1 | True | True | 5913.062 |
| MT03/2 | True | True | 6053.642 |
| MT03/3 | False | True | 5756.919 |
| MT06/1 | True | True | 8640.421 |
| MT06/2 | True | True | 8439.871 |
| MT06/3 | True | True | 7090.794 |
| MT06/4 | True | True | 7431.381 |

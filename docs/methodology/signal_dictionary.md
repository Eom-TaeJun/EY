# Signal Dictionary

| Signal | Economic meaning | Draft calculation | Leakage risk | Validation |
|---|---|---|---|---|
| recent_max_delinquency | recent repayment distress | max status in recent 3 months | low if only prior months | observed default rate by bucket |
| delinquent_months_6m | persistence of distress | count delinquent months | low | monotonicity and sample size |
| delinquency_deterioration | direction of recent behavior | recent status minus earlier status | low | compare deteriorating vs stable |
| latest_utilization_ratio | remaining liquidity buffer | latest bill / credit limit | medium if clipping is arbitrary | bucketed default rates |
| payment_coverage_ratio | ability to cover billed amount | payment / prior or current bill, explicitly defined | definition-sensitive | missing/zero handling tests |
| zero_payment_streak | repeated non-payment | maximum consecutive zero-payment months | low | default-rate comparison |
| recent_bill_growth | growing debt pressure | recent bill trend | low | segment review |

Thresholds remain configuration and decision items. Do not tune solely on the full outcome sample.

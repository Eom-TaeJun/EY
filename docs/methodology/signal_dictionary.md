# Signal Dictionary

| Signal | Economic meaning | Version 0.1.0 calculation | Timing / leakage | Validated run W1-20260727-001 |
|---|---|---|---|---|
| recent_max_delinquency | recent repayment distress | max of non-negative Jul–Sep repayment severity | pre-outcome; pass | 0: 21,560 / 12.52%; 2+: 6,661 / 52.27% |
| delinquent_months_6m | persistence of distress | count April–September statuses > 0 | pre-outcome; pass | 0: 19,931 / 11.71%; 2+: 5,643 / 52.84% |
| delinquency_deterioration | direction of recent behavior | recent 3m max severity minus earlier 3m max | pre-outcome; pass | <=0: 24,569 / 18.17%; 2+: 3,351 / 44.85% |
| latest_utilization_ratio | remaining liquidity buffer | September bill / credit limit; no clipping | pre-outcome; pass | <0.80: 22,020 / 20.45%; >=1: 2,123 / 30.05% |
| payment_coverage_ratio | ability to cover prior positive bill | September payment / August bill when August bill > 0 | pre-outcome; pass | <0.10: 14,912 / 25.97%; >=0.50: 7,581 / 14.06% |
| zero_payment_streak | repeated non-payment | longest consecutive zero-payment sequence over six months | pre-outcome; pass | 0: 15,458 / 13.92%; 1: 8,247 / 33.37%; 2+: 6,295 / 27.53% |
| recent_bill_growth | growing balance hypothesis | (September bill − June bill) / abs(June bill), when nonzero | pre-outcome; pass | <=0: 13,347 / 25.83%; >=0.25: 8,787 / 16.10% |

Values are `sample size / observed next-month default rate`. The first five
signals separate in the expected broad direction. `zero_payment_streak` is
non-monotonic, and `recent_bill_growth` contradicts the simple expected
direction; both remain reported rather than removed or retuned.

Risk-band points and thresholds are fixed in `config/risk_definitions.yml`.
They were recorded before outcome review and must be versioned, not edited to
improve this sample's separation.

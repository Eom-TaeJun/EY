# Approval Matrix

| Action | Agent may execute | Human approval required |
|---|---:|---:|
| Read files and inspect schemas | Yes | No |
| Create derived tables or draft documents | Yes | No |
| Run non-destructive SQL tests | Yes | No |
| Record an issue or failed test | Yes | No |
| Delete or replace source data | No | Yes |
| Change default/Stage definitions | No | Yes |
| Relax validation thresholds | No | Yes |
| Overwrite validated run output | No | Yes |
| Publish final portfolio numbers | No | Yes |
| Make final business interpretations | No | Yes |
| Accept or supersede a material definition decision | No | Yes |
| Make external writes or use credentials | No | Yes |
| Expand scope materially | No | Yes |

## Separation of duties

- A builder supplies evidence but cannot recommend approval of its own gate.
- Validation reproduces builder results and recommends Approve or Revise.
- The Orchestrator records internal Gate 0–3 status only after independent review.
- Human approval is still required for Gate 4 interpretation, Gate 5 publication,
  and every action marked above.

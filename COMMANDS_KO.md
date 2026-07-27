# Claude Code·Codex 실행 명령표

## 1. 압축 해제 후 공통 준비

```bash
cd credit-risk-signal-lab-scaffold
cp .env.example .env
python scripts/validate_scaffold.py
```

PostgreSQL을 Docker로 실행할 경우:

```bash
docker compose up -d postgres
```

## 2. Claude Code

### 대화형 실행

```bash
claude
```

세션에서:

```text
/context
/wave0
/status
```

Wave 0 검토가 끝난 뒤:

```text
/wave1
/review
```

### 프롬프트를 직접 지정해 한 번 실행

```bash
claude -p "Read AGENTS.md, HARNESS.md, PROJECT_STATE.md and execute prompts/01_wave0_governance.md. Do not perform Wave 1 work."
```

Wave 1:

```bash
claude -p "Read the repository instructions and execute prompts/02_wave1_data_sql.md. Respect all quality gates and stop on a material failed gate."
```

### 병렬 서브에이전트 지시 예시

Claude 대화창에서 다음처럼 지시한다.

```text
Wave 1을 Orchestrator 역할로 수행하라.
서로 파일이 겹치지 않는 경우에만 서브에이전트를 사용하라.
먼저 Hermes는 prompts/agent_packets/hermes_task.md,
Data Model은 agents/data_model.md,
SQL QA는 prompts/agent_packets/sql_qa_task.md를 따르게 하라.
각 결과를 병합하기 전 변경 파일, 테스트, 미해결 이슈를 요약하라.
```

## 3. Codex

### 대화형 실행

```bash
codex
```

처음에는 아래 파일 내용을 붙여 넣는다.

```text
prompts/01_wave0_governance.md
```

Wave 0 검토 이후:

```text
prompts/02_wave1_data_sql.md
```

### Codex용 시작 지시 예시

```text
Read AGENTS.md, HARNESS.md, PROJECT_STATE.md, and prompts/02_wave1_data_sql.md.
Act as the Orchestrator. Keep the full Wave 0–4 architecture, but implement only the Wave 1 critical path now.
Use separate workstreams only when file ownership does not overlap.
Do not alter raw data, invent results, relax tests, or publish unvalidated values.
At the end, update work_status.md and report exact commands and evidence.
```

## 4. 역할별로 병렬 실행할 때

### Hermes 작업

```text
Read agents/hermes.md and prompts/agent_packets/hermes_task.md.
Perform only the bounded Hermes task. Do not transform or interpret values.
```

### SQL QA 작업

```text
Read agents/sql_qa.md, docs/validation/test_catalog.md,
config/validation_thresholds.yml, and prompts/agent_packets/sql_qa_task.md.
Do not change upstream data or thresholds.
```

### Risk Signal 작업

```text
Read agents/risk_signal.md, docs/methodology/transmission_paths.md,
docs/methodology/signal_dictionary.md, and prompts/agent_packets/risk_signal_task.md.
Use only validated core tables and report contradictory evidence.
```

### 독립 리뷰

```text
Read agents/reviewer.md, agents/validation.md,
and prompts/agent_packets/reviewer_task.md.
Report issues by severity before editing anything.
```

## 5. 작업 완료 후 반드시 실행

```bash
python scripts/validate_scaffold.py
pytest -q
```

구현된 SQL 실행 명령과 대사 결과는 다음 파일에 남긴다.

- `docs/governance/work_status.md`
- `PROJECT_STATE.md`
- `docs/governance/decision_ledger.md`
- 이후 생성되는 `audit` 테이블과 issue log

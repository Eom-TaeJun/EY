# 저장소 구조 설명서

## 1. 파일을 세 층으로 나눈 이유

### 루트: 에이전트가 길을 잃지 않게 하는 지도

- `README.md`: 평가자와 사람에게 보여주는 프로젝트 설명
- `AGENTS.md`: Codex와 범용 코딩 에이전트가 가장 먼저 읽는 짧은 저장소 지도
- `CLAUDE.md`: Claude Code가 읽는 진입점. `@AGENTS.md`를 가져오고 Claude 전용 규칙만 추가
- `HARNESS.md`: 목적함수, 정본, 권한, 루프, 게이트, 종료조건을 담은 공통 운영 계약
- `PROJECT_STATE.md`: 지금 어느 Wave를 수행하는지와 현재 병목을 기록

루트 파일에 모든 내용을 넣지 않는다. 루트는 어디를 읽어야 하는지 알려주고, 세부 내용은 아래 문서로 분리한다.

### `docs/`: 사람이 합의하고 버전 관리하는 정본 문서

- `charter/`: 어떤 문제를 누구를 위해 해결하는가
- `governance/`: 목적, 작업 그래프, 결정, 승인, 상태
- `data/`: 데이터 출처, 테이블, 필드, lineage
- `methodology/`: 경제적 전파경로, 위험 신호, Risk Component 범위
- `validation/`: SQL 테스트, 대사, 모델 검증
- `wiki/`: 실행, 복구, 인수인계, 오류 대응
- `final/`: 평가자에게 보여줄 주장과 증거 연결

각 폴더의 `INDEX.md`가 해당 영역의 지도다. 에이전트가 모든 문서를 한꺼번에 읽지 않고 필요한 인덱스부터 따라가도록 한다.

### 실행층: 역할·프롬프트·코드 위치

- `agents/`: Orchestrator, Hermes, SQL QA 등 역할별 권한 계약
- `prompts/`: Wave별로 실행할 bounded prompt
- `.claude/rules/`: 파일 경로에 따라 자동 적용되는 Claude 규칙
- `.claude/skills/`: 반복 실행할 Wave, status, review 절차
- `sql/`, `src/`, `tests/`: 실제 구현
- `data/`, `logs/`, `outputs/`: 원천, 실행 증거, 산출물

## 2. 같은 내용을 여러 파일에 중복하지 않는 규칙

| 내용 | 정본 위치 |
|---|---|
| 프로젝트 메시지와 평가자용 설명 | `README.md` |
| 모든 에이전트의 공통 운영 원칙 | `HARNESS.md` |
| Codex가 읽을 저장소 지도 | `AGENTS.md` |
| Claude Code 전용 추가 규칙 | `CLAUDE.md`와 `.claude/rules/` |
| 반복 실행 절차 | `.claude/skills/`와 `prompts/` |
| 현재 진행 상태 | `PROJECT_STATE.md`와 `work_status.md` |
| 데이터 정의 | `docs/data/` |
| 위험 신호와 전파경로 | `docs/methodology/` |
| 실패·수정·검증 | `docs/validation/`, `work_status.md`, 이후 audit DB |

## 3. Claude Code에서 읽히는 구조

`CLAUDE.md`는 `@AGENTS.md`를 가져온다. 공통 규칙은 한 번만 작성하고, Claude에서만 필요한 내용만 `CLAUDE.md`에 둔다.

파일 유형별 세부 규칙은 `.claude/rules/`에 둔다.

- `data-safety.md`: data와 ingestion 작업에만 적용
- `sql-quality.md`: SQL과 테스트 작업에만 적용
- `documentation.md`: README와 문서 작업에만 적용
- `governance.md`: 상태·결정·설정 변경에 적용

긴 반복 절차는 `.claude/skills/<skill-name>/SKILL.md`에 둔다.

- `/wave0`
- `/wave1`
- `/status`
- `/review`

## 4. Codex에서 읽히는 구조

Codex는 루트 `AGENTS.md`를 저장소 지도와 공통 규칙으로 사용한다. 긴 실행 지시는 `prompts/`에서 하나씩 제공한다.

- 최초 구조 생성 또는 복구: `00_bootstrap_repository.md`
- 거버넌스 확인: `01_wave0_governance.md`
- DB·SQL·위험 신호: `02_wave1_data_sql.md`
- Risk Component: `03_wave2_risk_components.md`
- Graph·RAG·Wiki: `04_wave3_graph_rag_wiki.md`
- 보고·자동화: `05_wave4_reporting_automation.md`

`data/AGENTS.md`와 `sql/AGENTS.md`는 해당 영역을 작업할 때 적용할 더 구체적인 경계다.

## 5. Hermes Agent의 위치와 역할

- 역할 계약: `agents/hermes.md`
- 실행 패킷: `prompts/agent_packets/hermes_task.md`
- 소유 경로: `data/raw/`, `src/ingestion/`, `sql/ingestion/`, `logs/ingestion/`
- 관련 정본: `docs/data/source_registry.md`

Hermes는 원천 파일을 발견하고 해시·스키마·적재 건수를 기록한다. 결측치 처리, 코드 해석, 위험 신호 생성, 모델링은 수행하지 않는다.

## 6. 오늘 먼저 실행할 순서

1. `python scripts/validate_scaffold.py`
2. Claude의 `/wave0` 또는 Codex에 `prompts/01_wave0_governance.md` 투입
3. 거버넌스 검토 후 Hermes 패킷 실행
4. Wave 1 데이터와 SQL 프롬프트 실행
5. SQL QA와 Risk Signal 작업은 core 테이블이 준비된 뒤 병렬 실행
6. 검증된 숫자만 README와 자기소개서 근거에 사용

## 7. 나중에 확장하는 위치

| 기능 | 구현 위치 |
|---|---|
| PD·Stage proxy | `src/models/`, `sql/risk_components/`, Wave 2 문서 |
| LGD·EAD | 적합한 데이터 추가 후 같은 경로에 확장 |
| 그래프 lineage | `meta` DB 스키마, `docs/data/lineage_spec.md` |
| RAG·LLM Wiki | `src/`에 모듈 추가, 승인된 `docs/`만 색인 |
| Excel·PPT·Word | `outputs/`, `presentation/`, Documentation Agent |
| 반복 자동화 | Wave 4 프롬프트와 Agent 역할 계약 |

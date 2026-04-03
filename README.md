# Local AI 멀티-에이전트 개발자 (Open Interpreter + Ollama)

이 프로젝트는 **로컬 Ollama 모델들**을 역할별로 분담해,
지정한 디렉토리의 코드를 읽고 다음 작업을 자동화합니다.

- 코드베이스 분석 문서 생성
- 리팩토링 제안
- 사용자 요구사항 기반 코드 수정(옵션)

## 핵심 아이디어

- `open_interpreter`를 각 역할 에이전트의 실행 엔진으로 사용
- 모델별 강점을 반영한 역할 분리
- 분석 모드와 변경 모드를 분리해 안전성과 생산성 확보

## 권장 역할 매핑 (기본값)

- **Architect**: `qwen3.5:35b`
- **Refactorer**: `qwen2.5-coder:32b`
- **QA Reviewer**: `deepseek-r1:32b`
- **Doc Writer**: `llama3.1:latest`
- **Change Implementer**: `qwen2.5-coder:32b`

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 1) 분석 모드 (기본)

```bash
python ai_dev_orchestrator.py \
  --target-dir /path/to/your/project \
  --output-dir ./analysis_output \
  --mode analysis
```

생성 결과:

- `analysis_output/architect_report.md`
- `analysis_output/refactorer_report.md`
- `analysis_output/qa_reviewer_report.md`
- `analysis_output/doc_writer_report.md`
- `analysis_output/final_merged_report.md`

## 2) 변경 모드 (요구사항 분석 + 코드 변경)

### 2-1. 제안만 생성 (안전 모드)

```bash
python ai_dev_orchestrator.py \
  --target-dir /path/to/your/project \
  --output-dir ./analysis_output \
  --mode change \
  --change-request "로그인 API에 rate limit 기능 추가하고 테스트도 보강해줘"
```

이 경우 실제 코드는 수정하지 않고, 요구사항 분석/영향파일/수정 제안/테스트 전략을 문서로 생성합니다.

### 2-2. 실제 코드 수정 실행

```bash
python ai_dev_orchestrator.py \
  --target-dir /path/to/your/project \
  --output-dir ./analysis_output \
  --mode change \
  --change-request "로그인 API에 rate limit 기능 추가하고 테스트도 보강해줘" \
  --execute-change
```

이 경우 Open Interpreter가 대상 디렉토리에서 실제 코드 변경을 시도합니다.

## 모델 매핑 커스터마이즈

```bash
python ai_dev_orchestrator.py \
  --target-dir /path/to/your/project \
  --model-map 'Architect=qwen3:latest,Refactorer=qwen2.5-coder:latest,QA Reviewer=deepseek-r1:32b,Doc Writer=llama3.1:8b,Change Implementer=qwen3-coder:30b'
```

## 기존 patch-plan 옵션

```bash
python ai_dev_orchestrator.py \
  --target-dir /path/to/your/project \
  --mode analysis \
  --apply-patch-plan
```

## 주의사항

- 실제 코드 변경은 `--execute-change`를 켰을 때만 허용됩니다.
- 반드시 Git 브랜치에서 실행하고 diff를 검토하세요.
- 대규모 코드베이스는 `--max-files`, `--max-chars-per-file`를 줄여 시작하는 것을 권장합니다.

# Local AI 멀티-에이전트 개발자 (Open Interpreter + Ollama)

이 프로젝트는 **로컬 Ollama 모델들**을 역할별로 분담해,
지정한 디렉토리의 코드를 읽고 다음 작업을 자동화하는 예시입니다.

- 코드베이스 분석 문서 생성
- 리팩토링 제안
- 선택적으로 코드 수정 패치 생성

## 핵심 아이디어

- `open_interpreter`를 각 역할 에이전트의 실행 엔진으로 사용
- 모델별 강점을 반영한 역할 분리
- 동일 코드베이스를 공유하되, 결과물을 역할별 마크다운으로 저장
- 마지막에 통합 요약 보고서 생성

## 권장 역할 매핑 (기본값)

- **Architect**: `qwen3.5:35b`  
  아키텍처/설계 리뷰, 우선순위 도출
- **Refactorer**: `qwen2.5-coder:32b`  
  리팩토링/코드 개선안 및 패치 제안
- **QA Reviewer**: `deepseek-r1:32b`  
  잠재 버그/테스트 전략/리스크 분석
- **Doc Writer**: `llama3.1:latest`  
  최종 분석 문서 정리

모델이 없다면 `--model-map`으로 원하는 모델로 교체하세요.

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 실행

```bash
python ai_dev_orchestrator.py \
  --target-dir /path/to/your/project \
  --output-dir ./analysis_output
```

실행 후 생성물 예시:

- `analysis_output/architect_report.md`
- `analysis_output/refactorer_report.md`
- `analysis_output/qa_reviewer_report.md`
- `analysis_output/doc_writer_report.md`
- `analysis_output/final_merged_report.md`

## 모델 매핑 커스터마이즈

```bash
python ai_dev_orchestrator.py \
  --target-dir /path/to/your/project \
  --model-map 'Architect=qwen3:latest,Refactorer=qwen2.5-coder:latest,QA Reviewer=deepseek-r1:32b,Doc Writer=llama3.1:8b'
```

## 코드 자동 수정 옵션

기본값은 분석/제안 중심입니다. 실제 수정 파일 생성을 원하면:

```bash
python ai_dev_orchestrator.py \
  --target-dir /path/to/your/project \
  --apply-patch-plan
```

이 옵션은 `patch_plan.md`를 생성하도록 지시하며, 직접 검토 후 적용하는 방식(안전한 human-in-the-loop)을 권장합니다.

## 주의사항

- Open Interpreter가 실행 가능한 환경(파이썬, 쉘 권한, 로컬 파일 접근)이 필요합니다.
- 실제 코드 변경은 반드시 Git 브랜치에서 검토 후 반영하세요.
- 대규모 코드베이스는 `--max-files`, `--max-chars-per-file`를 줄여 시작하는 것을 권장합니다.

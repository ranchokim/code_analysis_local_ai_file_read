#!/usr/bin/env python3
"""Local AI multi-agent developer using Open Interpreter + Ollama."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_MODEL_MAP = {
    "Architect": "qwen3.5:35b",
    "Refactorer": "qwen2.5-coder:32b",
    "QA Reviewer": "deepseek-r1:32b",
    "Doc Writer": "llama3.1:latest",
    "Change Implementer": "qwen2.5-coder:32b",
}

ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".sh",
}


@dataclass
class AgentRole:
    name: str
    objective: str
    output_file: str


ANALYSIS_ROLES: List[AgentRole] = [
    AgentRole(
        name="Architect",
        objective=(
            "코드 구조를 리뷰하고 모듈 경계, 의존성, 기술부채 우선순위를 제시하세요. "
            "가장 효과가 큰 개선 5개를 근거와 함께 작성하세요."
        ),
        output_file="architect_report.md",
    ),
    AgentRole(
        name="Refactorer",
        objective=(
            "리팩토링 계획과 파일 단위 수정안을 작성하세요. "
            "가능하면 diff 형태 예시를 포함하고, 안전한 단계적 적용 순서를 제시하세요."
        ),
        output_file="refactorer_report.md",
    ),
    AgentRole(
        name="QA Reviewer",
        objective=(
            "잠재 버그, 보안 리스크, 엣지 케이스를 찾고 테스트 전략(단위/통합/E2E)을 제안하세요."
        ),
        output_file="qa_reviewer_report.md",
    ),
    AgentRole(
        name="Doc Writer",
        objective=(
            "앞선 역할들의 결과를 종합해 실행 가능한 최종 개선 로드맵 문서를 작성하세요."
        ),
        output_file="doc_writer_report.md",
    ),
]

CHANGE_IMPLEMENTER_ROLE = AgentRole(
    name="Change Implementer",
    objective=(
        "사용자 요구사항을 분석하고 영향 파일을 식별한 뒤 코드 수정안을 만들고 검증 계획을 작성하세요."
    ),
    output_file="change_implementer_report.md",
)


def parse_model_map(raw: str | None) -> Dict[str, str]:
    if not raw:
        return DEFAULT_MODEL_MAP.copy()

    parsed = DEFAULT_MODEL_MAP.copy()
    pairs = [chunk.strip() for chunk in raw.split(",") if chunk.strip()]
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid model map entry: {pair}")
        role, model = pair.split("=", 1)
        parsed[role.strip()] = model.strip()
    return parsed


def collect_project_snapshot(
    target_dir: Path,
    max_files: int,
    max_chars_per_file: int,
) -> Tuple[str, List[Path]]:
    files: List[Path] = []
    for root, _, filenames in os.walk(target_dir):
        for filename in filenames:
            path = Path(root) / filename
            if path.suffix.lower() in ALLOWED_EXTENSIONS:
                files.append(path)

    files = sorted(files)[:max_files]

    snippets: List[str] = [f"# Project: {target_dir}"]
    for path in files:
        rel = path.relative_to(target_dir)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            snippets.append(f"\n## File: {rel}\n<read-error: {exc}>")
            continue

        trimmed = text[:max_chars_per_file]
        snippets.append(f"\n## File: {rel}\n```\n{trimmed}\n```")

    return "\n".join(snippets), files


def run_open_interpreter_agent(model_name: str, prompt: str) -> str:
    """Run one agent role through Open Interpreter configured for local Ollama."""
    from interpreter import interpreter

    interpreter.auto_run = True
    interpreter.offline = True
    interpreter.llm.model = f"openai/{model_name}"
    interpreter.llm.api_base = "http://localhost:11434/v1"
    interpreter.llm.api_key = "ollama"

    response = interpreter.chat(prompt)

    if isinstance(response, str):
        return response

    if isinstance(response, list):
        chunks = []
        for item in response:
            if isinstance(item, dict):
                maybe = item.get("content") or item.get("message")
                if maybe:
                    chunks.append(str(maybe))
            else:
                chunks.append(str(item))
        return "\n".join(chunks)

    return str(response)


def build_analysis_prompt(
    role: AgentRole,
    model: str,
    target_dir: Path,
    project_snapshot: str,
    apply_patch_plan: bool,
) -> str:
    patch_instruction = (
        "추가로 patch_plan.md 형식(수정 이유, 대상 파일, 예상 diff 요약)을 반드시 포함하세요."
        if apply_patch_plan
        else "실제 파일 변경 대신 검토 가능한 제안 중심으로 작성하세요."
    )

    return f"""
당신은 로컬 AI 개발팀의 {role.name} 역할입니다.
모델: {model}

대상 디렉토리: {target_dir}
목표: {role.objective}

요구사항:
1) 핵심 문제 요약
2) 개선안 우선순위
3) 실행 단계 (작업 순서)
4) 리스크 및 롤백 전략
5) {patch_instruction}

아래는 코드 스냅샷입니다:
{project_snapshot}
""".strip()


def build_change_request_prompt(
    model: str,
    target_dir: Path,
    project_snapshot: str,
    change_request: str,
    execute_change: bool,
) -> str:
    execution_mode = (
        "실제 코드를 수정하세요. 수정 후 변경 파일 목록과 검증 명령을 마지막에 작성하세요."
        if execute_change
        else "코드를 직접 수정하지 말고 diff 제안 및 적용 순서만 제시하세요."
    )

    return f"""
당신은 로컬 AI 개발팀의 Change Implementer 역할입니다.
모델: {model}

대상 디렉토리: {target_dir}
사용자 요청:
{change_request}

작업 절차:
1) 요구사항 분석 (기능 요구/비기능 요구/제약)
2) 영향 받는 파일 식별
3) 구현 전략 및 예외 처리
4) 테스트 전략 (단위/통합/회귀)
5) {execution_mode}

아래는 코드 스냅샷입니다:
{project_snapshot}
""".strip()


def merge_reports(output_dir: Path, roles: List[AgentRole]) -> str:
    parts = ["# Final Merged Report\n"]
    for role in roles:
        file_path = output_dir / role.output_file
        if file_path.exists():
            parts.append(f"\n## {role.name}\n")
            parts.append(file_path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def run_analysis_mode(
    target_dir: Path,
    output_dir: Path,
    model_map: Dict[str, str],
    project_snapshot: str,
    apply_patch_plan: bool,
) -> None:
    for role in ANALYSIS_ROLES:
        model = model_map.get(role.name, DEFAULT_MODEL_MAP.get(role.name, "llama3.1:latest"))
        prompt = build_analysis_prompt(
            role=role,
            model=model,
            target_dir=target_dir,
            project_snapshot=project_snapshot,
            apply_patch_plan=apply_patch_plan,
        )

        try:
            result = run_open_interpreter_agent(model_name=model, prompt=prompt)
        except Exception as exc:  # noqa: BLE001
            result = f"# {role.name} execution failed\n\nError: {exc}"

        (output_dir / role.output_file).write_text(result, encoding="utf-8")
        print(f"[{role.name}] report written: {output_dir / role.output_file}")

    merged = merge_reports(output_dir, ANALYSIS_ROLES)
    (output_dir / "final_merged_report.md").write_text(merged, encoding="utf-8")
    print(f"Merged report written: {output_dir / 'final_merged_report.md'}")


def run_change_mode(
    target_dir: Path,
    output_dir: Path,
    model_map: Dict[str, str],
    project_snapshot: str,
    change_request: str,
    execute_change: bool,
) -> None:
    model = model_map.get(
        CHANGE_IMPLEMENTER_ROLE.name,
        DEFAULT_MODEL_MAP[CHANGE_IMPLEMENTER_ROLE.name],
    )
    prompt = build_change_request_prompt(
        model=model,
        target_dir=target_dir,
        project_snapshot=project_snapshot,
        change_request=change_request,
        execute_change=execute_change,
    )

    if execute_change:
        os.chdir(target_dir)

    try:
        result = run_open_interpreter_agent(model_name=model, prompt=prompt)
    except Exception as exc:  # noqa: BLE001
        result = f"# {CHANGE_IMPLEMENTER_ROLE.name} execution failed\n\nError: {exc}"

    (output_dir / CHANGE_IMPLEMENTER_ROLE.output_file).write_text(result, encoding="utf-8")
    print(f"[{CHANGE_IMPLEMENTER_ROLE.name}] report written: {output_dir / CHANGE_IMPLEMENTER_ROLE.output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-dir", required=True, type=Path)
    parser.add_argument("--output-dir", default=Path("analysis_output"), type=Path)
    parser.add_argument("--max-files", type=int, default=25)
    parser.add_argument("--max-chars-per-file", type=int, default=5000)
    parser.add_argument("--model-map", type=str, default=None)
    parser.add_argument("--apply-patch-plan", action="store_true")

    parser.add_argument(
        "--mode",
        choices=["analysis", "change"],
        default="analysis",
        help="analysis: 역할 분담 코드 분석 / change: 사용자 요구사항 기반 코드 수정",
    )
    parser.add_argument(
        "--change-request",
        type=str,
        default="",
        help="--mode change 에서 사용할 사용자 기능/수정 요구사항",
    )
    parser.add_argument(
        "--execute-change",
        action="store_true",
        help="--mode change 에서 실제 코드 수정을 허용합니다.",
    )

    args = parser.parse_args()

    target_dir = args.target_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "change" and not args.change_request.strip():
        raise ValueError("--mode change 사용 시 --change-request를 반드시 입력해야 합니다.")

    model_map = parse_model_map(args.model_map)

    project_snapshot, files = collect_project_snapshot(
        target_dir=target_dir,
        max_files=args.max_files,
        max_chars_per_file=args.max_chars_per_file,
    )

    metadata = {
        "mode": args.mode,
        "target_dir": str(target_dir),
        "files_scanned": [str(p.relative_to(target_dir)) for p in files],
        "model_map": model_map,
        "change_request": args.change_request,
        "execute_change": args.execute_change,
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if args.mode == "analysis":
        run_analysis_mode(
            target_dir=target_dir,
            output_dir=output_dir,
            model_map=model_map,
            project_snapshot=project_snapshot,
            apply_patch_plan=args.apply_patch_plan,
        )
    else:
        run_change_mode(
            target_dir=target_dir,
            output_dir=output_dir,
            model_map=model_map,
            project_snapshot=project_snapshot,
            change_request=args.change_request,
            execute_change=args.execute_change,
        )


if __name__ == "__main__":
    main()

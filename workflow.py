"""LangGraph workflow that turns legacy code analysis into a modernization report."""
import json
import re
from pathlib import Path
from typing import TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from analyzer import SEVERITY_RANK, FileSummary, Finding, find_dependencies, parse_file, scan_for_findings


class MigrationPhase(BaseModel):
    name: str
    actions: list[str]


class MigrationPlan(BaseModel):
    summary: str
    phases: list[MigrationPhase]


class ModernizationState(TypedDict, total=False):
    sources: dict[str, str]
    files: list[FileSummary]
    dependencies: list[tuple[str, str]]
    findings: list[Finding]
    risk_level: str
    security_actions: list[str]
    plan: MigrationPlan
    report: str


PLAN_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior .NET modernization architect. Build a phased migration plan using only the "
            "findings provided. Put security fixes first and name the affected files in each action.",
        ),
        ("human", "Overall risk: {risk_level}\nFile dependencies: {dependencies}\nFindings:\n{findings}"),
    ]
)


def load_sources(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(directory.rglob("*.cs"))
    }


def build_local_plan(findings: list[Finding], risk_level: str) -> MigrationPlan:
    """Group findings into ordered phases without calling an LLM."""
    phases: dict[str, dict[str, list[str]]] = {
        "Security remediation": {},
        "Platform migration": {},
        "Modernization cleanup": {},
    }
    for finding in sorted(findings, key=lambda item: SEVERITY_RANK[item.severity]):
        if finding.rule_id.startswith("SEC"):
            phase = "Security remediation"
        elif finding.severity == "low":
            phase = "Modernization cleanup"
        else:
            phase = "Platform migration"
        files = phases[phase].setdefault(finding.recommendation, [])
        if finding.file not in files:
            files.append(finding.file)

    file_count = len({finding.file for finding in findings})
    return MigrationPlan(
        summary=f"{len(findings)} findings across {file_count} files with {risk_level} overall risk.",
        phases=[
            MigrationPhase(
                name=name,
                actions=[f"{recommendation} [{', '.join(files)}]" for recommendation, files in actions.items()],
            )
            for name, actions in phases.items()
            if actions
        ],
    )


def render_report(state: ModernizationState) -> str:
    files = state["files"]
    findings = sorted(
        state["findings"], key=lambda item: (SEVERITY_RANK[item.severity], item.file, item.line)
    )
    lines = [
        "# Legacy Modernization Report",
        "",
        f"**Overall risk:** {state['risk_level'].upper()}",
        "",
        "| Files | Lines | Types | Methods | Findings |",
        "|---|---|---|---|---|",
        f"| {len(files)} | {sum(f.line_count for f in files)} | {sum(len(f.types) for f in files)} "
        f"| {sum(len(f.methods) for f in files)} | {len(findings)} |",
    ]

    if state["dependencies"]:
        lines += ["", "## Dependency Diagram", "", "```mermaid", "graph TD"]
        for source, target in state["dependencies"]:
            source_id, target_id = re.sub(r"\W", "_", source), re.sub(r"\W", "_", target)
            lines.append(f'    {source_id}["{source}"] --> {target_id}["{target}"]')
        lines.append("```")

    if not findings:
        lines += ["", "No legacy patterns or security risks were detected."]
        return "\n".join(lines) + "\n"

    lines += ["", "## Findings", "", "| Severity | Rule | Location | Issue | Recommendation |", "|---|---|---|---|---|"]
    lines += [
        f"| {f.severity.upper()} | {f.rule_id} | {f.file}:{f.line} | {f.issue} | {f.recommendation} |"
        for f in findings
    ]

    if state.get("security_actions"):
        lines += ["", "## Security Review", "", "Resolve these issues before starting the migration:", ""]
        lines += [f"- {action}" for action in state["security_actions"]]

    plan = state.get("plan")
    if plan:
        lines += ["", "## Migration Plan", "", plan.summary]
        for number, phase in enumerate(plan.phases, start=1):
            lines += ["", f"### Phase {number}: {phase.name}", ""]
            lines += [f"- {action}" for action in phase.actions]
    return "\n".join(lines) + "\n"


def build_workflow(llm: BaseChatModel | None = None):
    def parse_files(state: ModernizationState) -> dict:
        return {"files": [parse_file(name, source) for name, source in state["sources"].items()]}

    def map_dependencies(state: ModernizationState) -> dict:
        return {"dependencies": find_dependencies(state["files"], state["sources"])}

    def detect_patterns(state: ModernizationState) -> dict:
        findings = [
            finding for name, source in state["sources"].items() for finding in scan_for_findings(name, source)
        ]
        return {"findings": findings}

    def assess_risk(state: ModernizationState) -> dict:
        severities = {finding.severity for finding in state["findings"]}
        risk_level = next((level for level in ("high", "medium", "low") if level in severities), "none")
        return {"risk_level": risk_level}

    def route_by_risk(state: ModernizationState) -> str:
        if state["risk_level"] == "high":
            return "security_review"
        if state["risk_level"] == "none":
            return "write_report"
        return "plan_migration"

    def security_review(state: ModernizationState) -> dict:
        high_risk = [f for f in state["findings"] if f.severity == "high"]
        return {"security_actions": [f"{f.file}:{f.line} - {f.issue}. {f.recommendation}" for f in high_risk]}

    def plan_migration(state: ModernizationState) -> dict:
        if llm is None:
            return {"plan": build_local_plan(state["findings"], state["risk_level"])}
        chain = PLAN_PROMPT | llm.with_structured_output(MigrationPlan)
        plan = chain.invoke(
            {
                "risk_level": state["risk_level"],
                "dependencies": json.dumps(state["dependencies"]),
                "findings": json.dumps([finding.model_dump() for finding in state["findings"]], indent=2),
            }
        )
        return {"plan": plan}

    def write_report(state: ModernizationState) -> dict:
        return {"report": render_report(state)}

    graph = StateGraph(ModernizationState)
    graph.add_node("parse_files", parse_files)
    graph.add_node("map_dependencies", map_dependencies)
    graph.add_node("detect_patterns", detect_patterns)
    graph.add_node("assess_risk", assess_risk)
    graph.add_node("security_review", security_review)
    graph.add_node("plan_migration", plan_migration)
    graph.add_node("write_report", write_report)
    graph.add_edge(START, "parse_files")
    graph.add_edge("parse_files", "map_dependencies")
    graph.add_edge("map_dependencies", "detect_patterns")
    graph.add_edge("detect_patterns", "assess_risk")
    graph.add_conditional_edges("assess_risk", route_by_risk, ["security_review", "plan_migration", "write_report"])
    graph.add_edge("security_review", "plan_migration")
    graph.add_edge("plan_migration", "write_report")
    graph.add_edge("write_report", END)
    return graph.compile()


def analyze_sources(sources: dict[str, str], llm: BaseChatModel | None = None) -> ModernizationState:
    return build_workflow(llm).invoke({"sources": sources})

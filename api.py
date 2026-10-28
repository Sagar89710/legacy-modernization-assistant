"""REST API for the legacy code modernization assistant."""
import re

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

from analyzer import Finding
from workflow import MigrationPlan, analyze_sources

MAX_FILE_CHARS = 200_000
FILE_NAME_PATTERN = re.compile(r"^[\w./-]{1,200}\.cs$")

app = FastAPI(title="Legacy Code Modernization Assistant", version="1.0.0")


class AnalyzeRequest(BaseModel):
    files: dict[str, str] = Field(min_length=1, max_length=50, description="C# file name mapped to its content")

    @field_validator("files")
    @classmethod
    def validate_files(cls, files: dict[str, str]) -> dict[str, str]:
        for name, content in files.items():
            if not FILE_NAME_PATTERN.match(name):
                raise ValueError(f"Invalid C# file name: {name}")
            if len(content) > MAX_FILE_CHARS:
                raise ValueError(f"{name} exceeds {MAX_FILE_CHARS} characters")
        return files


class AnalyzeResponse(BaseModel):
    risk_level: str
    findings: list[Finding]
    dependencies: list[tuple[str, str]]
    plan: MigrationPlan | None
    report: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    result = analyze_sources(request.files)
    return AnalyzeResponse(
        risk_level=result["risk_level"],
        findings=result["findings"],
        dependencies=result["dependencies"],
        plan=result.get("plan"),
        report=result["report"],
    )

"""Static analysis for legacy C# (.NET Framework) source files."""
import re
from typing import Literal, NamedTuple

from pydantic import BaseModel

Severity = Literal["high", "medium", "low"]
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}

USING_PATTERN = re.compile(r"^[ \t]*using[ \t]+([\w.]+)[ \t]*;", re.MULTILINE)
NAMESPACE_PATTERN = re.compile(r"^[ \t]*namespace[ \t]+([\w.]+)", re.MULTILINE)
TYPE_PATTERN = re.compile(r"\b(?:class|interface|struct)[ \t]+(\w+)")
METHOD_PATTERN = re.compile(
    r"^[ \t]*(?:public|private|protected|internal)[ \t]+"
    r"(?:(?:static|virtual|override|async|abstract|sealed)[ \t]+)*"
    r"[\w<>\[\],.?]+[ \t]+(\w+)[ \t]*\(",
    re.MULTILINE,
)


class Rule(NamedTuple):
    rule_id: str
    pattern: str
    severity: Severity
    issue: str
    recommendation: str


RULES = [
    Rule(
        "SEC001",
        r'"(?:SELECT\b[^"]*\bFROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b[^"]*"\s*\+',
        "high",
        "SQL query built with string concatenation (SQL injection risk)",
        "Use parameterized queries or Entity Framework Core.",
    ),
    Rule(
        "SEC002",
        r'"[^"]*\b(?:Password|Pwd)=[^;"]+',
        "high",
        "Hard-coded credentials in a connection string",
        "Move secrets to environment variables or Azure Key Vault.",
    ),
    Rule(
        "SEC003",
        r'"http://',
        "medium",
        "Service call over unencrypted HTTP",
        "Use HTTPS and read the endpoint from configuration.",
    ),
    Rule(
        "LEG001",
        r"^\s*using\s+System\.Data\.SqlClient\s*;",
        "medium",
        "Legacy System.Data.SqlClient data provider",
        "Migrate to Microsoft.Data.SqlClient or Entity Framework Core.",
    ),
    Rule(
        "LEG002",
        r"^\s*using\s+System\.Windows\.Forms\s*;",
        "medium",
        "Windows Forms UI on .NET Framework",
        "Port to Windows Forms on modern .NET or re-platform the UI to Blazor.",
    ),
    Rule(
        "LEG003",
        r"\bHttpContext\.Current\b",
        "medium",
        "HttpContext.Current is not available in ASP.NET Core",
        "Inject IHttpContextAccessor or pass the user identity explicitly.",
    ),
    Rule(
        "LEG004",
        r"\[ServiceContract\b",
        "medium",
        "WCF service contract",
        "Expose the operation as an ASP.NET Core Web API or gRPC service, or use CoreWCF.",
    ),
    Rule(
        "LEG005",
        r"\bConfigurationManager\.",
        "low",
        "Configuration read through ConfigurationManager",
        "Use IConfiguration with appsettings.json and environment variables.",
    ),
    Rule(
        "LEG006",
        r"\bnew\s+WebClient\s*\(",
        "low",
        "Obsolete WebClient API",
        "Use HttpClient through IHttpClientFactory.",
    ),
]


class Finding(BaseModel):
    rule_id: str
    file: str
    line: int
    severity: Severity
    issue: str
    recommendation: str


class FileSummary(BaseModel):
    file: str
    namespace: str | None
    types: list[str]
    methods: list[str]
    usings: list[str]
    line_count: int


def parse_file(name: str, source: str) -> FileSummary:
    namespace = NAMESPACE_PATTERN.search(source)
    return FileSummary(
        file=name,
        namespace=namespace.group(1) if namespace else None,
        types=TYPE_PATTERN.findall(source),
        methods=METHOD_PATTERN.findall(source),
        usings=USING_PATTERN.findall(source),
        line_count=len(source.splitlines()),
    )


def scan_for_findings(name: str, source: str) -> list[Finding]:
    findings = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        if line.lstrip().startswith("//"):
            continue
        for rule in RULES:
            if re.search(rule.pattern, line, re.IGNORECASE):
                findings.append(
                    Finding(
                        rule_id=rule.rule_id,
                        file=name,
                        line=line_number,
                        severity=rule.severity,
                        issue=rule.issue,
                        recommendation=rule.recommendation,
                    )
                )
    return findings


def find_dependencies(summaries: list[FileSummary], sources: dict[str, str]) -> list[tuple[str, str]]:
    """Return (file, dependency) pairs where a file references a type defined in another file."""
    edges = []
    for summary in summaries:
        for other in summaries:
            if other.file != summary.file and any(
                re.search(rf"\b{re.escape(type_name)}\b", sources[summary.file]) for type_name in other.types
            ):
                edges.append((summary.file, other.file))
    return edges

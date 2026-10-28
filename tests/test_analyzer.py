from pathlib import Path

from analyzer import find_dependencies, parse_file, scan_for_findings

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_legacy_app"


def read_sample(name: str) -> str:
    return (SAMPLE_DIR / name).read_text(encoding="utf-8")


def test_parse_file_extracts_structure() -> None:
    summary = parse_file("CustomerRepository.cs", read_sample("CustomerRepository.cs"))
    assert summary.namespace == "Contoso.Billing.Data"
    assert summary.types == ["CustomerRepository", "Customer"]
    assert summary.methods == ["GetCustomersByCity", "DeleteCustomer"]
    assert "System.Data.SqlClient" in summary.usings


def test_sql_concatenation_is_flagged_but_parameterized_sql_is_not() -> None:
    repository = read_sample("CustomerRepository.cs")
    delete_line = next(
        number for number, line in enumerate(repository.splitlines(), start=1) if '"DELETE FROM' in line
    )
    repository_findings = scan_for_findings("CustomerRepository.cs", repository)
    assert any(f.rule_id == "SEC001" and f.line == delete_line for f in repository_findings)

    order_findings = scan_for_findings("OrderService.cs", read_sample("OrderService.cs"))
    assert not any(f.rule_id == "SEC001" for f in order_findings)
    assert any(f.rule_id == "SEC002" for f in order_findings)


def test_non_sql_string_concatenation_is_not_flagged() -> None:
    assert scan_for_findings("Status.cs", 'var message = "Update completed for " + name;') == []


def test_commented_code_is_ignored() -> None:
    assert scan_for_findings("Old.cs", "// using System.Data.SqlClient;\n") == []


def test_dependencies_between_files() -> None:
    sources = {path.name: path.read_text(encoding="utf-8") for path in sorted(SAMPLE_DIR.glob("*.cs"))}
    summaries = [parse_file(name, source) for name, source in sources.items()]
    assert find_dependencies(summaries, sources) == [
        ("CustomerForm.cs", "CustomerRepository.cs"),
        ("OrderService.cs", "CustomerRepository.cs"),
    ]

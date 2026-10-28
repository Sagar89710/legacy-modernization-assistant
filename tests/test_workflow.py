from pathlib import Path

from langchain_core.runnables import RunnableLambda

from workflow import MigrationPhase, MigrationPlan, analyze_sources, load_sources

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_legacy_app"

MODERN_SOURCE = """using Microsoft.Extensions.Configuration;

namespace Contoso.Modern
{
    public class GreetingService
    {
        public string Greet(string name)
        {
            return $"Hello, {name}";
        }
    }
}
"""


def test_high_risk_code_goes_through_security_review() -> None:
    result = analyze_sources(load_sources(SAMPLE_DIR))
    assert result["risk_level"] == "high"
    assert any(action.startswith("OrderService.cs:") for action in result["security_actions"])
    assert result["plan"].phases[0].name == "Security remediation"
    assert "```mermaid" in result["report"]


def test_medium_risk_code_skips_security_review() -> None:
    result = analyze_sources({"MainForm.cs": "using System.Windows.Forms;\n\npublic class MainForm : Form { }\n"})
    assert result["risk_level"] == "medium"
    assert "security_actions" not in result
    assert result["plan"].phases[0].name == "Platform migration"


def test_clean_code_skips_migration_planning() -> None:
    result = analyze_sources({"GreetingService.cs": MODERN_SOURCE})
    assert result["risk_level"] == "none"
    assert "plan" not in result
    assert "No legacy patterns" in result["report"]


def test_llm_plan_is_used_when_model_is_provided() -> None:
    expected = MigrationPlan(
        summary="LLM plan", phases=[MigrationPhase(name="Fix security issues", actions=["Parameterize SQL"])]
    )

    class StubChatModel:
        def with_structured_output(self, schema):
            assert schema is MigrationPlan
            return RunnableLambda(lambda _prompt: expected)

    result = analyze_sources(load_sources(SAMPLE_DIR), llm=StubChatModel())
    assert result["plan"] == expected
    assert "### Phase 1: Fix security issues" in result["report"]

"""Analyze a folder of C# files and write a Markdown modernization report."""
import argparse
import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from workflow import analyze_sources, load_sources

BASE_DIR = Path(__file__).parent


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    parser = argparse.ArgumentParser(description="Analyze legacy C# code and generate a modernization report.")
    parser.add_argument(
        "source_dir",
        nargs="?",
        type=Path,
        default=BASE_DIR / "sample_legacy_app",
        help="Folder containing .cs files (defaults to the bundled sample)",
    )
    parser.add_argument("--output", type=Path, default=Path("modernization_report.md"), help="Markdown report path")
    parser.add_argument("--openai", action="store_true", help="Use OpenAI to write the migration plan")
    args = parser.parse_args()

    sources = load_sources(args.source_dir)
    if not sources:
        raise SystemExit(f"No .cs files found in {args.source_dir}")

    llm = None
    if args.openai:
        if not os.getenv("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is required when using --openai.")
        llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)

    result = analyze_sources(sources, llm=llm)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result["report"], encoding="utf-8")

    severities = Counter(finding.severity for finding in result["findings"])
    print(f"Files analyzed: {len(result['files'])}")
    print(f"Overall risk: {result['risk_level'].upper()}")
    print(f"Findings: {severities['high']} high, {severities['medium']} medium, {severities['low']} low")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()

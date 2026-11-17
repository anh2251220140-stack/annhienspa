"""Gemini staging and explicitly attested synthetic-only live probes."""
import argparse
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import openai_test as staging


def main(argv=None):
    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            raise staging.StagingError("Invalid arguments; never pass credentials as arguments.")
    parser = SafeParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "fallback", "live", "generate-only"))
    parser.add_argument("--feature", choices=(*staging.FEATURES, "all"), default="fr21")
    args = parser.parse_args(argv)
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise staging.StagingError("Use the project .venv")
    values = staging.locked_environment(os.environ.get("COMPUTERNAME", ""), os.environ.get("SystemRoot", r"C:\Windows"))
    values.update(AI_PROVIDER="gemini", AI_GEMINI_MODEL="gemini-3.5-flash-lite",
                  AI_GEMINI_EMBEDDING_MODEL="gemini-embedding-001", AI_GEMINI_EMBEDDING_DIMENSIONS="768",
                  AI_GEMINI_REQUESTS_APPROVED="false", AI_GEMINI_FREE_TIER_CONFIRMED="false",
                  AI_GEMINI_FREE_TIER_ONLY="true", AI_RAG_INDEX_UPDATE_APPROVED="false")
    os.environ.clear()
    os.environ.update(values)
    if args.mode == "live":
        if args.feature == "all":
            raise staging.StagingError("Live requires one explicit feature.")
        from tools.gemini_live import live
        report = live(args.feature)
    elif args.mode == "generate-only":
        if args.feature != "fr21":
            raise staging.StagingError("Generate-only requires FR-21.")
        from tools.gemini_live import generate_only
        report = generate_only(args.feature)
    elif args.mode == "plan":
        report = {"configuration": staging.public_configuration("gemini"), "google_requests_approved": False,
                  "free_project_confirmed": False, "index_update_approved": False,
                  "database_connected": False, "key_loaded": False, "provider_called": False}
    else:
        with patch.object(staging, "WORK_ROOT", ROOT / ".gemini-test"):
            report = staging.fallback(args.feature, provider="gemini")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if report.get("status") == "FALLBACK" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(f"Stopped ({type(error).__name__}); no retry or alternate provider will be used.")
        raise SystemExit(1)

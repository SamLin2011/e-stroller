from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collect import collect_all
from emailer import send_report
from storage import load_seen_urls, merge_seen_urls
from summarize import generate_chinese_report

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is included in requirements
    load_dotenv = None


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect electric stroller intelligence and email a Chinese daily report."
    )
    parser.add_argument("--skip-email", action="store_true", help="Generate the report without sending email.")
    parser.add_argument(
        "--allow-fallback-summary",
        action="store_true",
        help="Use a deterministic local report if OpenAI is unavailable.",
    )
    parser.add_argument("--max-items", type=int, default=50, help="Maximum new items to include in the report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if load_dotenv:
        load_dotenv(PROJECT_ROOT / ".env")

    report_date = datetime.now(BEIJING_TZ).date()
    reports_dir = PROJECT_ROOT / "reports"
    report_path = reports_dir / f"{report_date.isoformat()}.md"

    LOGGER.info("Collecting sources")
    collected_items, errors = collect_all(PROJECT_ROOT / "config")
    seen_urls = load_seen_urls(PROJECT_ROOT / "data" / "seen_urls.json")

    new_items = [item for item in collected_items if item.url not in seen_urls]
    if args.max_items > 0:
        new_items = new_items[: args.max_items]

    LOGGER.info("Collected %s URLs, %s new URLs", len(collected_items), len(new_items))
    report = generate_chinese_report(
        [item.to_dict() for item in new_items],
        errors,
        report_date,
        allow_fallback=args.allow_fallback_summary,
    )

    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    LOGGER.info("Report saved to %s", report_path)

    subject = f"婴童电助力推车 / 智能婴儿车日报 - {report_date.isoformat()}"
    if args.skip_email:
        LOGGER.info("Email skipped by --skip-email")
    else:
        send_report(subject=subject, body=report, attachment_path=str(report_path))
        LOGGER.info("Email sent")

    merge_seen_urls((item.url for item in collected_items), PROJECT_ROOT / "data" / "seen_urls.json")
    LOGGER.info("Seen URL storage updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

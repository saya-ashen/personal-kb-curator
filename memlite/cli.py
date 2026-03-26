import argparse
import json
from pathlib import Path

from workflows import (
    ask_question,
    capture,
    generate_weekly_review,
    process_meeting,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mem-lite local CLI")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_capture = sub.add_parser("capture", help="Capture a new note")
    p_capture.add_argument("text", help="Raw note text, file path, or URL")

    p_ask = sub.add_parser("ask", help="Ask from local knowledge")
    p_ask.add_argument("question", help="Question")

    p_meeting = sub.add_parser("meeting", help="Convert meeting text to knowledge")
    p_meeting.add_argument("text", help="Meeting transcript or notes")
    p_meeting.add_argument(
        "--meeting-date", required=True, help="Meeting date (YYYY-MM-DD)"
    )

    p_weekly = sub.add_parser("weekly", help="Generate weekly review")
    p_weekly.add_argument("--period-start", required=True, help="Start date YYYY-MM-DD")
    p_weekly.add_argument("--period-end", required=True, help="End date YYYY-MM-DD")

    args = parser.parse_args()
    root = Path(args.workspace_root).resolve()

    if args.cmd == "capture":
        result = capture(workspace_root=root, input_value=args.text)
    elif args.cmd == "ask":
        result = ask_question(workspace_root=root, question=args.question)
    elif args.cmd == "meeting":
        result = process_meeting(
            workspace_root=root,
            text=args.text,
            meeting_date=args.meeting_date,
        )
    elif args.cmd == "weekly":
        result = generate_weekly_review(
            workspace_root=root,
            period_start=args.period_start,
            period_end=args.period_end,
        )
    else:
        raise ValueError(f"Unsupported command: {args.cmd}")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

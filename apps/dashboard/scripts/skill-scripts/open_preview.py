import json
import sys
import argparse


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def open_preview(payload: dict):
    """
    Triggers the opening of a dynamic preview modal on the dashboard.
    In the agentic context, this typically involves emitting a signal
    that the dashboard's event listener (DynamicPreviewModal) will catch.

    Since this script runs on the factory side, it communicates the intent.
    The actual 'WOW' effect happens when the dashboard receives this payload.
    """
    _out(f"🎨 [FRONTEND-DESIGN] Triggering Dynamic Preview: {payload.get('title')}")
    _out(f"📦 Payload: {json.dumps(payload, indent=2)}")

    # In a full integration, this might write to a websocket or a src/lib status file
    # that the dashboard polls, or use a custom tool to interact with the browser.

    # For now, we simulate the 'success' of the trigger.
    return {"status": "success", "event": "augur:open-dynamic-ui", "payload": payload}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", help="Unique ID for the payload")
    parser.add_argument("--title", help="Title of the preview")
    parser.add_argument("--type", choices=['strategy', 'checklist', 'data-viz'], help="Content type")
    parser.add_argument("--content", help="Content data (Markdown or JSON)")
    parser.add_argument("--agentName", help="Agent who generated this")

    args = parser.parse_args()

    try:
        # Try to parse content as JSON if it looks like it, otherwise keep as string (markdown)
        content = args.content
        try:
            content = json.loads(args.content)
        except (TypeError, json.JSONDecodeError):
            content = args.content

        payload = {
            "id": args.id or "preview-123",
            "title": args.title,
            "type": args.type,
            "content": content,
            "agentName": args.agentName,
        }

        open_preview(payload)
    except Exception as e:
        _out(f"❌ Error triggering preview: {e}")
        sys.exit(1)

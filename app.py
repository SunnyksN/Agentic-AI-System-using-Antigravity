"""
app.py — Flask web server for the Agentic AI project.

Routes:
  GET  /           → Main chat UI
  POST /run        → SSE stream of agent steps
  GET  /health     → Health check
"""

import json
import os

from dotenv import load_dotenv
from flask import Flask, Response, render_template, request, stream_with_context

from agent import run_agent

load_dotenv()

app = Flask(__name__)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def sse_event(data: dict) -> str:
    """Format a dict as a Server-Sent Event string."""
    return f"data: {json.dumps(data)}\n\n"


@app.route("/")
def index():
    return render_template("index.html", api_key_set=bool(GEMINI_API_KEY))


@app.route("/run", methods=["POST"])
def run():
    """Stream the agent's execution steps as Server-Sent Events."""
    data = request.get_json(force=True) or {}
    task = (data.get("task") or "").strip()
    api_key = (data.get("api_key") or GEMINI_API_KEY or "").strip()

    if not task:
        def err():
            yield sse_event({"type": "error", "content": "Please enter a task."})
        return Response(stream_with_context(err()), mimetype="text/event-stream")

    if not api_key:
        def err():
            yield sse_event({
                "type": "error",
                "content": "No Gemini API key found. Add it to your .env file or enter it in the UI.",
            })
        return Response(stream_with_context(err()), mimetype="text/event-stream")

    def generate():
        for event in run_agent(task, api_key):
            yield sse_event(event)
        yield sse_event({"type": "done"})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/health")
def health():
    return {"status": "ok", "gemini_key_set": bool(GEMINI_API_KEY)}


if __name__ == "__main__":
    app.run(debug=True, port=5000)

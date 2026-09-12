import time

import gradio as gr

from .jobs import create_job, get_job

_POLL_SECONDS = 2
_MAX_POLLS = 150


def _run(company: str, history: list):
    company = (company or "").strip()
    history = history or []
    if not company:
        yield history, ""
        return

    history = history + [{"role": "user", "content": company}]
    job_id = create_job(company)
    history = history + [{"role": "assistant", "content": "Queued, the analyst is starting..."}]
    yield history, ""

    shown = 0
    for _ in range(_MAX_POLLS):
        time.sleep(_POLL_SECONDS)
        job = get_job(job_id) or {}

        steps = job.get("steps", [])
        for s in steps[shown:]:
            history = history + [{"role": "assistant", "content": s.get("text", "")}]
        shown = len(steps)

        status = job.get("status")
        if status == "DONE":
            history = history + [{"role": "assistant", "content": job.get("result", "(empty brief)")}]
            yield history, ""
            return
        if status == "FAILED":
            history = history + [{"role": "assistant", "content": f"Failed: {job.get('error', 'unknown error')}"}]
            yield history, ""
            return
        yield history, ""

    history = history + [{"role": "assistant", "content": "Still working. Submit again to keep watching."}]
    yield history, ""


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Financial Research Analyst") as demo:
        gr.Markdown("## Financial Research Analyst Agent\nSubmit a company and watch the agent decide, then read the cited brief.")
        chat = gr.Chatbot(type="messages", height=460, label="Agent")
        company = gr.Textbox(label="Company or ticker", placeholder="e.g. Apple / AAPL", submit_btn=True)

        company.submit(_run, inputs=[company, chat], outputs=[chat, company])
    return demo

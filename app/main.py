import gradio as gr
from fastapi import FastAPI
from pydantic import BaseModel

from .jobs import create_job, get_job
from .ui import build_ui

app = FastAPI(title="Financial Research Analyst API")


@app.get("/api/health")
def health():
    return {"status": "ok"}


class JobRequest(BaseModel):
    company: str


@app.post("/api/jobs")
def submit_job(req: JobRequest):
    job_id = create_job(req.company)
    return {"job_id": job_id, "status": "PENDING"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        return {"job_id": job_id, "status": "NOT_FOUND"}
    return job


app = gr.mount_gradio_app(app, build_ui(), path="/ui")

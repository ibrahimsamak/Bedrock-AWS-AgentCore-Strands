# AgentCore Runtime requires linux/arm64. Build with buildx (see deploy section).
FROM --platform=linux/arm64 python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

# BedrockAgentCoreApp.run() serves /invocations + /ping on 8080.
EXPOSE 8080
CMD ["python", "agent_runtime.py"]

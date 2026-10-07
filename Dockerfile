FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    DENSO_DEMO_DB=/data/pose_demo.sqlite3 \
    DENSO_RESEARCH_DIR=/data/research

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 denso \
    && useradd --uid 10001 --gid denso --create-home denso \
    && mkdir -p /data/research \
    && chown -R denso:denso /data

COPY requirements-docker.txt ./
RUN python -m pip install --no-cache-dir -r requirements-docker.txt

COPY --chown=denso:denso pose_focus_demo/ ./pose_focus_demo/
COPY --chown=denso:denso research_pipeline/ ./research_pipeline/
COPY --chown=denso:denso scripts/ ./scripts/
COPY --chown=denso:denso research_artifacts/benchmark.json research_artifacts/comparison.csv /data/research/

USER denso
EXPOSE 8767
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8767/api/health', timeout=4).close()"]

CMD ["python", "-m", "uvicorn", "app:app", "--app-dir", "pose_focus_demo", "--host", "0.0.0.0", "--port", "8767"]

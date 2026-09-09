FROM python:3.12.11-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    WORKSPACE=/workspace \
    TASK_ROOT=/opt/task \
    PYTHONPATH=/workspace \
    PORT=8000 \
    HOST=0.0.0.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY environment/requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY starter/ ${WORKSPACE}/
COPY tests/ ${TASK_ROOT}/tests/
COPY instruction.md task.toml ${TASK_ROOT}/
COPY environment/start.sh environment/healthcheck.sh /usr/local/bin/

RUN chmod +x /usr/local/bin/start.sh /usr/local/bin/healthcheck.sh \
    && mkdir -p /var/trial \
    && useradd --create-home --uid 1000 --shell /bin/bash sandbox \
    && chown -R sandbox:sandbox ${WORKSPACE} ${TASK_ROOT} /var/trial

USER sandbox
WORKDIR /workspace
EXPOSE 8000

LABEL task_id="health-api" \
      python.version="3.12"

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
    CMD ["/usr/local/bin/healthcheck.sh"]

ENTRYPOINT ["/usr/local/bin/start.sh"]

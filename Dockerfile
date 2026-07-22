# Multi-stage build, non-root final image, no floating tags (conception §13.1, §13.2).

FROM python:3.13.5-slim-trixie AS builder

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.13.5-slim-trixie AS final

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY src/ ./src/
COPY pyproject.toml .

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-m", "ebios_rm.main"]

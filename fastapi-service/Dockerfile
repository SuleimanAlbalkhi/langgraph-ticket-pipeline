FROM python:3.13-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1  

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Non-root: ein unprivilegierter User führt den Prozess aus. Falls der Service je
# kompromittiert wird (z.B. über eine Dependency-Lücke), ist der Angreifer NICHT
# root im Container — begrenzt den möglichen Schaden (Defense in Depth).
RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser app/ ./app/
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
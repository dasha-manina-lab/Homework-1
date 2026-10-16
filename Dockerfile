FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN mkdir -p /data
ENV STATE_FILE=/data/state.json
EXPOSE 5000
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1
# Один воркер: состояние игры хранится в памяти процесса.
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:5000", "app:app"]

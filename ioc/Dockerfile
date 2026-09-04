FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
# EPICS Channel Access needs its UDP/TCP ports; run with network_mode: host (see compose).
CMD ["python", "puck_ioc.py"]

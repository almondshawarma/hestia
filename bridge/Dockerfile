FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
# Channel Access needs its UDP/TCP ports; run with network_mode: host (see deploy/).
CMD ["python", "ca2influx.py"]

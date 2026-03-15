FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY stove_monitor.py .

CMD ["python", "-u", "stove_monitor.py"]

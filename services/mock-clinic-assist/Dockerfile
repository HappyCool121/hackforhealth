FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py clinic-assist-v2.schema.json ./
EXPOSE 8090
CMD ["python", "server.py"]

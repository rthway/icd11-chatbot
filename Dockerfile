FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# Fetches the official WHO ICD-11 MMS export and builds data/icd11_codes.json
# at image build time (requires network access during `docker build`).
RUN python build_db.py

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]

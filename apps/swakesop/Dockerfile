## version 2
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# No compiler: every Python dependency ships a wheel. iputils-ping stays because the
# app shells out to ping for its live status checks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8085

CMD ["gunicorn", "-b", "0.0.0.0:8085", "--workers", "2", "--threads", "4", "app:app"]

FROM python:3.11-slim-bookworm
WORKDIR /app
COPY auditforge /app/auditforge
COPY tests /app/tests
COPY scripts /app/scripts
COPY configs /app/configs
RUN mkdir -p /app/web/public
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "auditforge.verify"]

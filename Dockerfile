FROM python:3.11-slim-bookworm@sha256:a83ba18aef0f865b1a4a611c2cf460fe446f2795673bbb9fe43be570439e3b39
WORKDIR /app
COPY auditforge /app/auditforge
COPY tests /app/tests
COPY scripts /app/scripts
COPY configs /app/configs
COPY docs /app/docs
COPY README.md LICENSE requirements.txt pyproject.toml Dockerfile Dockerfile.policy HACKATHON_COMPLIANCE.md SUBMISSION_MANIFEST.md JURY_LIVE_DEMO_SCRIPT.md FINAL_AUDIT_REPORT.md THIRD_PARTY_NOTICES.md /app/
RUN mkdir -p /app/web/public
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "auditforge.verify"]

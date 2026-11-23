FROM python:3.11-slim-bookworm@sha256:a83ba18aef0f865b1a4a611c2cf460fe446f2795673bbb9fe43be570439e3b39
WORKDIR /app
COPY auditforge /app/auditforge
COPY tests /app/tests
COPY scripts /app/scripts
COPY configs /app/configs
COPY docs /app/docs
COPY web/public/python-bridge.py /app/web/public/python-bridge.py
COPY README.md LICENSE requirements.txt pyproject.toml Dockerfile Dockerfile.policy HACKATHON_COMPLIANCE.md SUBMISSION_MANIFEST.md JURY_LIVE_DEMO_SCRIPT.md FINAL_AUDIT_REPORT.md THIRD_PARTY_NOTICES.md /app/
COPY Dockerfile.sequential-policy AUDITFORGE_FINAL_INDEPENDENT_AUDIT.md AUDITFORGE_RL_BENCHMARK.md AUDITFORGE_ADVERSARIAL_REPORT.md AUDITFORGE_GENESIS_COMPLIANCE.md AUDITFORGE_JURY_DEMO.md AUDITFORGE_LIMITATIONS.md /app/
COPY Dockerfile.document-policy AUDITFORGE_2_2_*.md /app/
RUN mkdir -p /app/web/public
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "auditforge.verify"]

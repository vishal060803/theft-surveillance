#!/usr/bin/env bash
set -e

export THREAT_SURVEILLANCE_ENV="production"
export THREAT_SURVEILLANCE_ENABLE_AUTH="true"
export THREAT_SURVEILLANCE_DASHBOARD_USERNAME="admin"
export THREAT_SURVEILLANCE_DASHBOARD_PASSWORD="change-me-in-production"
export THREAT_SURVEILLANCE_SECRET_KEY="replace-with-a-long-random-secret"
export THREAT_SURVEILLANCE_API_KEY="replace-with-a-strong-api-key"
export THREAT_SURVEILLANCE_RETENTION_DAYS="30"

python3 app.py

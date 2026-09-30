$env:THREAT_SURVEILLANCE_ENV = "production"
$env:THREAT_SURVEILLANCE_ENABLE_AUTH = "true"
$env:THREAT_SURVEILLANCE_DASHBOARD_USERNAME = "admin"
$env:THREAT_SURVEILLANCE_DASHBOARD_PASSWORD = "change-me-in-production"
$env:THREAT_SURVEILLANCE_SECRET_KEY = "replace-with-a-long-random-secret"
$env:THREAT_SURVEILLANCE_API_KEY = "replace-with-a-strong-api-key"
$env:THREAT_SURVEILLANCE_RETENTION_DAYS = "30"
python app.py

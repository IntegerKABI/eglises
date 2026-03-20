# Testing Guide

## Use the project virtual environment

Activate the project environment before running any Django or Playwright command.

```powershell
.\env\Scripts\Activate.ps1
```

If you do not activate it, `py manage.py ...` may use the global Python interpreter instead of `env\Scripts\python.exe`.

## Local SQLite suite

```bash
py manage.py test --noinput
```

## Local PostgreSQL suite with Docker

1. Start the database service.

```bash
docker compose up -d postgres
```

2. Ensure `.env` points Django to PostgreSQL.

```env
POSTGRES_DB=eglise_saas
POSTGRES_USER=eglise_user
POSTGRES_PASSWORD=eglise-password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
DATABASE_CONN_MAX_AGE=600
DATABASE_SSL_REQUIRE=False
```

3. Run migrations and the test suite.

```bash
py manage.py migrate
py manage.py test --noinput
```

4. Run the PostgreSQL locking regression on its own when validating concurrency work.

```bash
py manage.py test tests.church.integration.test_postgres_transactions --noinput
```

## Browser E2E suite

Install the Python dependency and Chromium once in your environment.

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Then run the browser journeys.

```bash
py manage.py test tests.church.e2e --noinput
```

If Playwright is installed but the browser process cannot start on your current machine or policy context, the suite now skips cleanly instead of failing the whole test run.

## CI coverage

The GitHub Actions workflow runs three jobs:
- SQLite regression suite
- PostgreSQL regression suite, including the lock-sensitive invitation test
- Browser journeys against PostgreSQL with Playwright Chromium

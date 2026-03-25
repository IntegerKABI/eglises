# Testing Guide

## Required Python interpreter

Always run Django, pytest-style test commands, and Playwright commands from the project virtual environment.

Do not use `py manage.py ...` for this repository. On Windows, `py` can resolve to the global interpreter instead of the project environment, which leads to missing dependencies and inconsistent test results.

Preferred options:
- Activate the environment and use `python`
- Or call `env\Scripts\python.exe` directly for one-off commands

### PowerShell activation

```powershell
.\env\Scripts\Activate.ps1
```

After activation, every command in this guide should use `python`.

### Direct interpreter usage without activation

```powershell
env\Scripts\python.exe manage.py test --noinput
```

## Local PostgreSQL suite

```powershell
python manage.py migrate
python manage.py test --noinput
```

## Local PostgreSQL suite with Docker

1. Start the database service.

```powershell
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

```powershell
python manage.py migrate
python manage.py test --noinput
```

4. Run the PostgreSQL locking regression on its own when validating concurrency work.

```powershell
python manage.py test tests.church.integration.test_postgres_transactions --noinput
```

## Browser E2E suite

Install the Python dependency and Chromium once in your environment.

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

Then run the browser journeys.

```powershell
python manage.py test tests.church.e2e --noinput
```

The browser suite runs whenever Playwright is installed and Chromium can start in the current environment. On Windows, it is skipped by default unless `ENABLE_WINDOWS_PLAYWRIGHT_E2E=1` is set and the machine can launch Chromium.

## CI coverage

The GitHub Actions workflow runs one PostgreSQL regression job that includes the lock-sensitive invitation test and the browser journeys with Playwright Chromium installed in the same runner.

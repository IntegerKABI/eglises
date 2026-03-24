import os
from importlib import import_module
from unittest.mock import patch

from django.test import SimpleTestCase

from eglise_saas_project.settings import base as project_settings


class SettingsHelpersTests(SimpleTestCase):
    def test_env_bool_and_int_helpers_parse_values(self):
        with patch.dict(os.environ, {"FEATURE_FLAG": "true", "COUNT_LIMIT": "15"}, clear=False):
            self.assertTrue(project_settings._env_bool("FEATURE_FLAG"))
            self.assertEqual(project_settings._env_int("COUNT_LIMIT", 0), 15)

    def test_env_log_level_normalizes_known_levels(self):
        with patch.dict(os.environ, {"APP_LOG_LEVEL": "warning"}, clear=False):
            self.assertEqual(project_settings._env_log_level("APP_LOG_LEVEL"), "WARNING")

    def test_env_log_level_falls_back_for_invalid_values(self):
        with patch.dict(os.environ, {"APP_LOG_LEVEL": "verbose"}, clear=False):
            self.assertEqual(project_settings._env_log_level("APP_LOG_LEVEL", default="INFO"), "INFO")

    def test_build_database_config_prefers_database_url(self):
        env = {
            "DATABASE_URL": "postgresql://eglise_user:secret@127.0.0.1:5432/eglise_saas",
            "POSTGRES_DB": "",
            "POSTGRES_USER": "",
            "POSTGRES_PASSWORD": "",
            "POSTGRES_HOST": "",
            "POSTGRES_PORT": "",
            "DATABASE_CONN_MAX_AGE": "120",
            "DATABASE_SSL_REQUIRE": "false",
            "DEBUG": "true",
        }

        with patch.dict(os.environ, env, clear=False):
            config = project_settings._build_database_config()

        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "eglise_saas")
        self.assertEqual(config["CONN_MAX_AGE"], 120)
        self.assertTrue(config["CONN_HEALTH_CHECKS"])

    def test_build_database_config_uses_explicit_postgres_settings(self):
        env = {
            "DATABASE_URL": "",
            "POSTGRES_DB": "eglise_saas",
            "POSTGRES_USER": "eglise_user",
            "POSTGRES_PASSWORD": "secret",
            "POSTGRES_HOST": "db",
            "POSTGRES_PORT": "5433",
            "DATABASE_CONN_MAX_AGE": "300",
        }

        with patch.dict(os.environ, env, clear=False):
            config = project_settings._build_database_config()

        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["HOST"], "db")
        self.assertEqual(config["PORT"], "5433")
        self.assertEqual(config["CONN_MAX_AGE"], 300)
        self.assertTrue(config["CONN_HEALTH_CHECKS"])

    def test_build_database_config_falls_back_to_sqlite(self):
        env = {
            "DATABASE_URL": "",
            "POSTGRES_DB": "",
            "POSTGRES_USER": "",
            "POSTGRES_PASSWORD": "",
            "POSTGRES_HOST": "",
            "POSTGRES_PORT": "",
        }

        with patch.dict(os.environ, env, clear=False):
            config = project_settings._build_database_config()

        self.assertEqual(config["ENGINE"], "django.db.backends.sqlite3")
        self.assertTrue(str(config["NAME"]).endswith("db.sqlite3"))

    def test_settings_profiles_are_importable(self):
        self.assertIsNotNone(import_module("eglise_saas_project.settings.development"))
        self.assertIsNotNone(import_module("eglise_saas_project.settings.production"))
        self.assertIsNotNone(import_module("eglise_saas_project.settings.test"))

    def test_logging_configuration_uses_structured_console_output(self):
        console_handler = project_settings.LOGGING["handlers"]["console"]
        structured_formatter = project_settings.LOGGING["formatters"]["structured"]

        self.assertEqual(console_handler["formatter"], "structured")
        self.assertEqual(console_handler["stream"], project_settings.sys.stdout)
        self.assertIn("timestamp=%(asctime)s", structured_formatter["format"])

    def test_test_profile_silences_django_request_noise(self):
        test_settings = import_module("eglise_saas_project.settings.test")
        django_request_logger = test_settings.LOGGING["loggers"]["django.request"]

        self.assertEqual(django_request_logger["level"], "CRITICAL")
        self.assertFalse(django_request_logger["propagate"])

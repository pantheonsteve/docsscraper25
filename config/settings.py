"""
Django settings for docanalyzer project.
"""

import os
import multiprocessing
from pathlib import Path
from decouple import config, Csv

# Fix for macOS fork crashes with PostgreSQL/Kerberos
# Disable GSSAPI at the libpq level using environment variables
os.environ['PGGSSENCMODE'] = 'disable'
os.environ['PGGSSDELEGATION'] = '0'

# Must be set before any multiprocessing occurs
try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    # Already set, ignore
    pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'django_extensions',

    # Local apps
    'core.apps.CoreConfig',
    'crawler.apps.CrawlerConfig',
    'analyzer.apps.AnalyzerConfig',
    'reports.apps.ReportsConfig',
    'dashboard.apps.DashboardConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='docanalyzer'),
        'USER': config('DB_USER', default='docanalyzer'),
        'PASSWORD': config('DB_PASSWORD', default='docanalyzer_dev_password'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redis Configuration
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 24 * 60 * 60  # 24 hours for long crawls

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {}

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'docanalyzer.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'crawler_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'crawler.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file', 'json_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'crawler': {
            'handlers': ['console', 'crawler_file', 'json_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'dashboard': {
            'handlers': ['console', 'file', 'json_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'file', 'json_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# JSON logging configuration (for Datadog and structured logging)
LOGGING['formatters']['json'] = {
    '()': 'json_log_formatter.JSONFormatter',
}
LOGGING['handlers']['json_file'] = {
    'level': 'INFO',
    'class': 'logging.FileHandler',
    'filename': BASE_DIR / 'logs' / 'my-log.json',
    'formatter': 'json',
}

# Ensure logs directory exists
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# Crawler Settings
CRAWLER_USER_AGENT = config(
    'CRAWLER_USER_AGENT',
    default='DocAnalyzer Bot (+https://yourcompany.com/bot)'
)
CRAWLER_POLITENESS_DELAY = config('CRAWLER_POLITENESS_DELAY', default=0.5, cast=float)
CRAWLER_CONCURRENT_REQUESTS = config('CRAWLER_CONCURRENT_REQUESTS', default=16, cast=int)
CRAWLER_DEFAULT_DEPTH_LIMIT = config('CRAWLER_DEFAULT_DEPTH_LIMIT', default=5, cast=int)

# Security
ENCRYPTION_KEY = config('ENCRYPTION_KEY', default='dev-encryption-key-change-in-production')

# Webhook Configuration
WEBHOOK_TIMEOUT = config('WEBHOOK_TIMEOUT', default=30, cast=int)

# Screenshot Storage Configuration
# Options: 'local' or 's3'
SCREENSHOT_STORAGE_BACKEND = config('SCREENSHOT_STORAGE_BACKEND', default='local')
SCREENSHOT_S3_BUCKET = config('SCREENSHOT_S3_BUCKET', default=None)
SCREENSHOT_S3_PREFIX = config('SCREENSHOT_S3_PREFIX', default='screenshots/')
# AWS credentials (if using S3)
# AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default=None)
# AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default=None)
# AWS_REGION = config('AWS_REGION', default='us-east-1')

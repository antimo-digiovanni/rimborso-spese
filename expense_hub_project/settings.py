import os
from pathlib import Path

import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = os.environ.get('SECRET_KEY', 'expense-hub-dev-secret-key')
DEBUG = os.environ.get('DEBUG', '1').strip().lower() in {'1', 'true', 'yes', 'on'}

BASE_ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
extra_allowed_hosts = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', '').split(',') if host.strip()]
ALLOWED_HOSTS = BASE_ALLOWED_HOSTS + extra_allowed_hosts


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'claims',
]

USE_S3_MEDIA = os.environ.get('USE_S3_MEDIA', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
SQLITE_PATH = os.environ.get('SQLITE_PATH', '').strip()
MEDIA_ROOT_PATH = os.environ.get('MEDIA_ROOT_PATH', '').strip()

if USE_S3_MEDIA:
    INSTALLED_APPS.append('storages')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'expense_hub_project.urls'

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

WSGI_APPLICATION = 'expense_hub_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.parse(os.environ['DATABASE_URL'], conn_max_age=600),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': SQLITE_PATH or (BASE_DIR / 'db.sqlite3'),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'it-it'

TIME_ZONE = 'Europe/Rome'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = MEDIA_ROOT_PATH or (BASE_DIR / 'media')

if USE_S3_MEDIA:
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', '')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', '') or None
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL', '') or None
    AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN', '') or None
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False

    DEFAULT_FILE_STORAGE = 'storages.backends.s3.S3Storage'

    media_base_url = AWS_S3_CUSTOM_DOMAIN
    if media_base_url:
        MEDIA_URL = f"https://{media_base_url}/"
    elif AWS_S3_ENDPOINT_URL and AWS_STORAGE_BUCKET_NAME:
        MEDIA_URL = f"{AWS_S3_ENDPOINT_URL.rstrip('/')}/{AWS_STORAGE_BUCKET_NAME}/"

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Expense Hub <noreply@example.com>')

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

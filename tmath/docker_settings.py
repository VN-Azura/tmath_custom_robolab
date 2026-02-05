"""
Docker-specific settings for TMATH
This file is used when running the application in Docker containers.
Copy this to local_settings.py or set DJANGO_LOCAL_SETTINGS_MODULE environment variable.
"""
import os

# Static files
COMPRESS_OUTPUT_DIR = 'cache'
STATICFILES_FINDERS += ('compressor.finders.CompressorFinder',)
STATIC_ROOT = BASE_DIR / 'static'

# Security settings for production
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
SECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)

# Allowed hosts
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS = [f'http://{host}' for host in ALLOWED_HOSTS] + [f'https://{host}' for host in ALLOWED_HOSTS]

# Database configuration
# Use PostgreSQL in production, SQLite for development
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        },
    }

# Redis cache configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Celery configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)

# Channels (WebSocket) configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [os.environ.get('REDIS_URL', 'redis://localhost:6379/0')],
        },
    },
}

# Static and media files
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

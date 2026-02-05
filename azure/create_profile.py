#!/usr/bin/env python
import os
import sys

# Setup Django
sys.path.insert(0, '/opt/tmath')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tmath.settings')

import django
django.setup()

from django.contrib.auth.models import User
from judge.models import Profile, Language

admin = User.objects.get(username='admin')
try:
    p = admin.profile
    print('Profile already exists')
except User.profile.RelatedObjectDoesNotExist:
    lang = Language.objects.first()
    if not lang:
        print('No language found, creating Python')
        lang = Language.objects.create(key='PY3', name='Python 3')
    Profile.objects.create(user=admin, language=lang, timezone='Asia/Ho_Chi_Minh')
    print('Profile created for admin!')

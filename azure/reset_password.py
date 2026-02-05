#!/usr/bin/env python
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'tmath.settings_production'

import django
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(username='admin')
u.set_password('admin123')
u.save()
print('Password reset to: admin123')

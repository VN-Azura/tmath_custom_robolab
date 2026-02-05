from django.contrib.auth.models import User
from judge.models import Profile, Language
admin = User.objects.get(username='admin')
try:
    p = admin.profile
    print('Profile exists')
except User.profile.RelatedObjectDoesNotExist:
    lang = Language.objects.first()
    Profile.objects.create(user=admin, language=lang, timezone='Asia/Ho_Chi_Minh')
    print('Profile created!')
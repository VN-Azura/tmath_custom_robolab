# coding=utf-8
import re

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import \
    get_default_password_validators
from django.forms import ChoiceField
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from registration.backends.default.views import \
    ActivationView as OldActivationView
from registration.backends.default.views import \
    RegistrationView as OldRegistrationView
from registration.forms import RegistrationForm

from judge.models import TIMEZONE, Language, Profile
from judge.widgets import Select2Widget

# from sortedm2m.forms import SortedMultipleChoiceField


bad_mail_regex = list(map(re.compile, settings.BAD_MAIL_PROVIDER_REGEX))


class CustomRegistrationForm(RegistrationForm):
    username = forms.RegexField(regex=r'^(?=.{6,30}$)(?![_.])(?!.*[_.]{2})[a-z0-9_]+(?<![_.])$',
                                max_length=30, label=_('Username'),
                                error_messages={'invalid': _('A username must contain lower latinh letters, '
                                                             'numbers, min length = 6, max length = 30')})
    timezone = ChoiceField(label=_('Timezone'), choices=TIMEZONE,
                           widget=Select2Widget(attrs={'style': 'width:100%'}))
    name = forms.RegexField(regex=r'^(?!\s*$).+', max_length=50, required=True, label=_('Fullname'))

    def clean_email(self):
        if User.objects.filter(email=self.cleaned_data['email']).exists():
            raise forms.ValidationError(gettext('The email address "%s" is already taken. Only one registration '
                                                'is allowed per address.') % self.cleaned_data['email'])
        if '@' in self.cleaned_data['email']:
            domain = self.cleaned_data['email'].split('@')[-1].lower()
            if (domain in settings.BAD_MAIL_PROVIDERS or
                    any(regex.match(domain) for regex in bad_mail_regex)):
                raise forms.ValidationError(gettext('Your email provider is not allowed due to history of abuse. '
                                                    'Please use a reputable email provider.'))
        return self.cleaned_data['email']


class RegistrationView(OldRegistrationView):
    title = _('Registration')
    form_class = CustomRegistrationForm
    template_name = 'registration/registration_form.html'

    def get_success_url(self, user=None):
        return reverse_lazy('auth_login')

    def get_context_data(self, **kwargs):
        if 'title' not in kwargs:
            kwargs['title'] = self.title
        kwargs['password_validators'] = get_default_password_validators()
        return super(RegistrationView, self).get_context_data(**kwargs)

    def register(self, form):
        user = super(RegistrationView, self).register(form)
        user.is_active = True
        user.save()
        profile, _ = Profile.objects.get_or_create(user=user, defaults={
            'language': Language.get_default_language(),
        })

        cleaned_data = form.cleaned_data
        profile.timezone = cleaned_data['timezone']
        profile.name = cleaned_data['name']
        profile.save()

        return user

    def get_initial(self, *args, **kwargs):
        initial = super(RegistrationView, self).get_initial(*args, **kwargs)
        initial['timezone'] = settings.DEFAULT_USER_TIME_ZONE
        return initial


class ActivationView(OldActivationView):
    title = _('Registration')
    template_name = 'registration/activate.html'

    def get_context_data(self, **kwargs):
        if 'title' not in kwargs:
            kwargs['title'] = self.title
        return super(ActivationView, self).get_context_data(**kwargs)


def social_auth_error(request):
    return render(request, 'generic-message.html', {
        'title': gettext('Authentication failure'),
        'message': request.GET.get('message'),
    })

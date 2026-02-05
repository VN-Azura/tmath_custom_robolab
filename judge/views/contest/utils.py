import zipfile
from typing import Any

from django import forms
from django.contrib.auth.mixins import (LoginRequiredMixin,
                                        PermissionRequiredMixin)
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from judge.models import (Contest, ContestParticipation, ContestProblem,
                          ContestSubmission, Profile, Submission,
                          SubmissionSource)
from judge.models.runtime import Language
from judge.utils.views import TitleMixin, generic_message

EXTS = ('.c', '.cpp', '.java', '.py', '.pas')

LANGS = {
    'c': 'C',
    'cpp': 'CPP17',
    'java': 'JAVA8',
    'py': 'PY3',
    'pas': 'PAS',
}


class ContestDataForm(forms.Form):
    # zipfile field
    upload = forms.FileField(label='Contest data', required=True, validators=[lambda f: f.name.endswith('.zip')])
    clear = forms.BooleanField(label='Clear all data', required=False)


class ContestDataView(LoginRequiredMixin, PermissionRequiredMixin, TitleMixin, FormView):
    template_name = 'contest/contest_data.html'
    form_class = ContestDataForm
    contest: Contest | None
    success_url = '/contest/{}'

    def get_success_url(self):
        return self.success_url.format(self.contest.key)

    def has_permission(self):
        return self.request.user.is_superuser

    def get_contest(self):
        return get_object_or_404(Contest, key=self.kwargs['contest'])

    def get_title(self):
        return 'Contest data'

    def get_data(self, upload):
        data = {}
        with zipfile.ZipFile(upload, 'r') as zip_ref:
            for file in zip_ref.namelist():
                if not file.endswith(EXTS):
                    continue
                temp = file.split('/')
                if len(temp) != 2:
                    continue
                id = temp[0].split('_')[0]
                try:
                    id = int(id)
                except ValueError:
                    continue
                try:
                    source = zip_ref.open(file).read().decode('utf-8')
                except UnicodeDecodeError:
                    from sys import stderr
                    print(file, file=stderr)

                ext = file.split('.')[-1]
                if id not in data:
                    data[id] = {}
                basename = temp[1].upper().split('.')[0]
                if len(basename) != 1:
                    continue
                order = ContestProblem.get_order(temp[1].upper().split('.')[0])
                data[id][order] = (source, LANGS[ext])
        return data

    def post(self, request: HttpRequest, *args: str, **kwargs: Any) -> HttpResponse:
        try:
            self.contest = self.get_contest()
        except Http404:
            return generic_message(request, _('Contest not found'),
                                   _('The contest you are looking for does not exist.'), status=404)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form: Any) -> HttpResponse:
        data = self.get_data(form.cleaned_data['upload'])

        user_ids = list(map(int, data.keys()))

        users = Profile.objects.filter(pk__in=user_ids).order_by('pk')
        problems = ContestProblem.objects.filter(contest=self.contest).order_by('order')
        languages = Language.objects.all()

        with transaction.atomic():
            # Clear all old data
            if form.cleaned_data['clear']:
                Submission.objects.filter(contest_object=self.contest).delete()
                self.contest.users.all().delete()
            else:
                # Clear old participations in users
                Submission.objects.filter(user__in=users, contest_object=self.contest).delete()
                ContestParticipation.objects.filter(user__in=users, contest=self.contest).delete()

            # Create new participations
            participations = ContestParticipation.objects.bulk_create([
                ContestParticipation(user=user, contest=self.contest) for user in users
            ])

            # Create new submissions
            for participation in participations:
                for problem in problems:
                    if problem.order not in data[participation.user.pk]:
                        continue
                    source, lang = data[participation.user.pk][problem.order]

                    submission = Submission.objects.create(
                        user=participation.user,
                        problem=problem.problem,
                        language=languages.get(key=lang),
                        contest_object=self.contest,
                        date=self.contest.start_time,
                    )

                    SubmissionSource.objects.create(
                        submission=submission,
                        source=source,
                    )

                    ContestSubmission.objects.create(
                        submission=submission,
                        problem=problem,
                        participation=participation,
                    )

        self.contest.update_user_count()

        return super().form_valid(form)

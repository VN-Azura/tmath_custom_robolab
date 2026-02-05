import logging

from django.conf import settings
from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from judge.forms import ProblemSubmitForm
from judge.models import (Contest, ContestProblem, ContestSubmission, Judge,
                          Language, RuntimeVersion, Submission,
                          SubmissionSource)
from judge.utils.views import SingleObjectFormView, TitleMixin, generic_message
from judge.views.contests import ContestMixin, PrivateContestError
from judge.views.problem import SolvedProblemMixin

user_logger = logging.getLogger('judge.user')


def get_contest_submission_count(problem: ContestProblem, profile, virtual):
    # print(profile)
    return profile.current_contest.submissions.exclude(submission__status__in=['IE']) \
                  .filter(problem=problem, participation__virtual=virtual).count()


class ContestProblemListView(LoginRequiredMixin, ContestMixin, TitleMixin, SolvedProblemMixin, DetailView):
    template_name = 'contest/problem/list.html'

    def get_title(self):
        return 'Problem List'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['problems'] = self.object.contest_problems.select_related('problem').defer('problem__description') \
            .annotate(user_count=Count('submission__participation', distinct=True)).order_by('order')
        context['completed_problem_ids'] = self.get_completed_problems()
        context['attempted_problems'] = self.get_attempted_problems()
        context['tab'] = 'tasks'
        return context


class ContestProblemDetailView(LoginRequiredMixin, ContestMixin, TitleMixin, SolvedProblemMixin, DetailView):
    template_name = 'contest/problem/detail.html'

    def get_object(self, queryset=None):
        contest = super().get_object(queryset)
        self.problem: ContestProblem = ContestProblem.objects.filter(contest=contest,
                                                                     order=self.kwargs['problem']).first()
        if not self.problem:
            raise Http404()
        return contest

    def get_title(self):
        return self.problem.temporary_name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        authed = user.is_authenticated
        context['has_submissions'] = authed and ContestSubmission.objects.filter(participation__user=user.profile,
                                                                                 problem=self.problem).exists()
        context['problem'] = self.problem
        context['description'] = self.problem.problem.description
        context['completed_problem_ids'] = self.get_completed_problems()
        context['attempted_problems'] = self.get_attempted_problems()
        can_edit = self.problem.problem.is_editable_by(self.request.user)
        context['can_edit_problem'] = can_edit
        context['available_judges'] = Judge.objects.filter(online=True, problems=self.problem.problem)
        if user.profile.current_contest and user.profile.current_contest.contest == self.object:
            context['submission_limit'] = self.problem.max_submissions
            if self.problem.max_submissions:
                contest_submission_count = get_contest_submission_count(self.problem, user.profile,
                                                                        user.profile.current_contest.virtual)
                context['submissions_left'] = max(self.problem.max_submissions - contest_submission_count, 0)
        context['show_languages'] = self.problem.problem.allowed_languages.count() != Language.objects.count()
        return context


class ContestProblemSubmit(AccessMixin, ContestMixin, TitleMixin, SingleObjectFormView):
    template_name = 'contest/problem/submit.html'
    form_class = ProblemSubmitForm

    def get_object(self, queryset=None):
        contest = super().get_object(queryset)
        self.contest_problem: ContestProblem = ContestProblem.objects.filter(contest=contest,
                                                                             order=self.kwargs['problem']).first()
        if not self.contest_problem:
            raise Http404()
        self.problem = self.contest_problem.problem
        return contest

    @cached_property
    def remaining_submission_count(self):
        if self.request.profile.current_contest is None:
            return None
        max_subs = self.contest_problem and self.contest_problem.max_submissions
        if max_subs is None:
            return None
        # When an IE submission is rejudged into a non-IE status, it will count towards the
        # submission limit. We max with 0 to ensure that `remaining_submission_count` returns
        # a non-negative integer, which is required for future checks in this view.
        return max(
            0,
            max_subs - get_contest_submission_count(
                self.contest_problem, self.request.profile, self.request.profile.current_contest.virtual,
            ),
        )

    @cached_property
    def default_language(self):
        # If the old submission exists, use its language, otherwise use the user's default language.
        return self.request.profile.language

    def get_content_title(self):
        return mark_safe(
            escape(_('Submit to %s')) % format_html(
                '<a href="{0}" class="content_title">{1}</a>',
                self.contest_problem.get_absolute_url(),
                self.contest_problem.temporary_name,
            ),
        )

    def get_title(self):
        return _('Submit to %s') % self.contest_problem.temporary_name

    def get_initial(self):
        initial = {'language': self.default_language}
        if self.old_submission is not None:
            initial['source'] = self.old_submission.source.source
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = Submission(user=self.request.profile, problem=self.problem)

        if self.object.fastio:
            kwargs['fastio'] = True

        if self.object.forbidden_words:
            kwargs['forbidden_words'] = list(self.object.forbidden_words.split())

        if self.object.is_editable_by(self.request.user):
            kwargs['judge_choices'] = tuple(
                Judge.objects.filter(online=True, problems=self.problem).values_list('name', 'name'),
            )
        else:
            kwargs['judge_choices'] = ()

        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        if self.request.in_contest and self.request.participation.contest.is_limit_language:
            lang = self.request.participation.contest.limit_language
            form.fields['language'].queryset = (
                self.problem.usable_languages.filter(pk=lang.pk).order_by('name', 'key')
                .prefetch_related(Prefetch('runtimeversion_set', RuntimeVersion.objects.order_by('priority')))
            )
        else:
            form.fields['language'].queryset = (
                self.problem.usable_languages.order_by('name', 'key')
                .prefetch_related(Prefetch('runtimeversion_set', RuntimeVersion.objects.order_by('priority')))
            )

        form_data = getattr(form, 'cleaned_data', form.initial)
        if 'language' in form_data:
            form.fields['source'].widget.mode = form_data['language'].ace
        form.fields['source'].widget.theme = self.request.profile.ace_theme

        return form

    def get_success_url(self):
        return reverse('submission_status', args=(self.new_submission.id,))

    def form_valid(self, form):
        if (
            not self.request.user.has_perm('judge.spam_submission') and
            Submission.objects.filter(user=self.request.profile, rejudged_date__isnull=True)
                              .exclude(contest_object__isnull=False, contest_object__delay_contest=True) 
                              .exclude(status__in=['D', 'IE', 'CE', 'AB']).count() >= settings.DMOJ_SUBMISSION_LIMIT
        ):
            return HttpResponse('<h1>You submitted too many submissions.</h1>', status=429)
        if not self.problem.allowed_languages.filter(id=form.cleaned_data['language'].id).exists():
            raise PermissionDenied()
        if not self.request.user.is_superuser and self.problem.banned_users.filter(id=self.request.profile.id).exists():
            return generic_message(self.request, _('Banned from submitting'),
                                   _('You have been declared persona non grata for this problem. '
                                     'You are permanently barred from submitting this problem.'))
        # Must check for zero and not None. None means infinite submissions remaining.
        if self.remaining_submission_count == 0:
            return generic_message(self.request, _('Too many submissions'),
                                   _('You have exceeded the submission limit for this problem.'))

        with transaction.atomic():
            self.new_submission = form.save(commit=False)

            contest_problem = self.contest_problem
            if contest_problem is not None:
                # Use the contest object from current_contest.contest because we already use it
                # in profile.update_contest().
                self.new_submission.contest_object = self.request.profile.current_contest.contest
                if self.request.profile.current_contest.live:
                    self.new_submission.locked_after = self.new_submission.contest_object.locked_after
                self.new_submission.save()
                ContestSubmission(
                    submission=self.new_submission,
                    problem=contest_problem,
                    participation=self.request.profile.current_contest,
                ).save()
            else:
                self.new_submission.save()

            source_url = ''
            origin_url = ''

            source = SubmissionSource(
                submission=self.new_submission,
                source=form.cleaned_data['source'] + source_url,
                file=origin_url,
            )
            source.save()

        # Save a query.
        # self.new_submission.source = source
        if not self.object.delay_contest:
            self.new_submission.judge(force_judge=True, judge_id=form.cleaned_data['judge'])

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['langs'] = Language.objects.all()
        context['no_judges'] = not context['form'].fields['language'].queryset
        context['submission_limit'] = self.contest_problem and self.contest_problem.max_submissions
        context['submissions_left'] = self.remaining_submission_count
        context['ACE_URL'] = settings.ACE_URL
        context['default_lang'] = self.default_language
        return context

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except Http404:
            # Is this really necessary? This entire post() method could be removed if we don't log this.
            user_logger.info(
                'Naughty user %s wants to submit to %s without permission',
                request.user.username,
                kwargs.get(self.slug_url_kwarg),
            )
            return HttpResponseForbidden('<h1>Do you want me to ban you?</h1>')

    def get(self, request, *args, **kwargs):
        if not self.problem.can_submitted_by(request.user):
            return generic_message(request,
                                   _('Can\'t submit to problem'),
                                   _('You don\'t have the permission to submit this problem. '
                                     'Please contact admin for permission.'),
                                   status=403)
        return super().get(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        try:
            self.object: Contest = self.get_object()
        except Http404:
            return generic_message(request, _('Contest not found'),
                                   _('The contest you are looking for does not exist.'), status=404)
        except PrivateContestError as e:
            return render(request, 'contest/private.html', {
                'error': e, 'title': _('Access to contest "%s" denied') % e.name,
            }, status=403)

        profile = request.profile
        if not profile.current_contest or (profile.current_contest and profile.current_contest.contest != self.object):
            return generic_message(request, _('Not in contest'),
                                   _('You are not in a contest.'), status=403)

        if request.in_contest and request.participation.contest.start_time > timezone.now():
            return generic_message(request, _('Contest not ongoing'),
                                   _('You cannot submit now.'), status=403)

        if not self.contest_problem.can_view(request):
            return generic_message(request,
                                   _('Can\'t submit to problem'),
                                   _(f'You need at least {self.contest_problem.limit_point} '
                                     'points in the contest to submit this problem.'),
                                   status=403)

        submission_id = kwargs.get('submission')
        if submission_id is not None:
            self.old_submission = get_object_or_404(
                Submission.objects.select_related('source', 'language'),
                id=submission_id,
            )
            if not request.user.has_perm('judge.resubmit_other') and self.old_submission.user != request.profile:
                raise PermissionDenied()
        else:
            self.old_submission = None

        return super().dispatch(request, *args, **kwargs)

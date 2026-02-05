from celery import shared_task
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from judge.models import Contest
from judge.models.contest import Rating
from judge.ratings import rate_contest as rate_contest_func
from judge.utils.celery import Progress


@shared_task(bind=True)
def rate_contest(self, contest_id=None):
    if contest_id is None:
        contests = Contest.objects.filter(is_rated=True, end_time__lte=timezone.now()).order_by('end_time')
    else:
        contest = Contest.objects.get(pk=contest_id)
        Rating.objects.filter(contest__end_time__range=(contest.end_time, timezone.now())).delete()
        contests = Contest.objects.filter(
            is_rated=True, end_time__range=(contest.end_time, timezone.now()),
        ).order_by('end_time')

    with Progress(self, contests.count(), stage=_('Rating contests')) as p:
        for contest in contests.iterator():
            rate_contest_func(contest)
            p.done += 1
    return contests.count()

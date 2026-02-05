from django.db.models import Max
from django.utils.translation import gettext_lazy

from judge.contest_format.default import DefaultContestFormat
from judge.contest_format.registry import register_contest_format


@register_contest_format('default_limit')
class DefaultLimitContestFormat(DefaultContestFormat):
    name = gettext_lazy('Default Limit')

    def update_participation(self, participation):
        cumtime = 0
        points = 0
        format_data = {}
        map_points = {}

        for result in participation.submissions.values('problem_id', 'problem__order', 'problem__points').annotate(
                time=Max('submission__date'), points=Max('points'),
        ):
            dt = (result['time'] - participation.start).total_seconds()
            if result['points']:
                cumtime += dt
            format_data[str(result['problem_id'])] = {'time': dt, 'points': result['points']}
            map_points[result['problem__order']] = (result['points'], result['problem__points'])

        last = -1
        for i in sorted(map_points.keys()):
            if i == last + 1:
                points += map_points[i][0]
                if map_points[i][0] != map_points[i][1]:
                    break
                last = i
            else:
                break

        participation.cumtime = max(cumtime, 0)
        participation.score = round(points, self.contest.points_precision)
        participation.tiebreaker = 0
        participation.format_data = format_data
        participation.save()

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import connection
from django.template.defaultfilters import floatformat
from django.utils.translation import gettext_lazy

from judge.contest_format.default import DefaultContestFormat
from judge.contest_format.registry import register_contest_format
from judge.timezone import from_database_time
from judge.utils.timedelta import nice_repr


def calc_total_point_penalty(prev_submits, penalty_cfg):
    total = 0
    pp = sorted(penalty_cfg.items())
    pp.append((10**18, 0))

    for i in range(len(pp) - 1):
        start, pen = pp[i]
        end = pp[i + 1][0] - 1
        if prev_submits < start:
            break
        total += max(0, min(prev_submits, end) - start + 1) * pen

    return total


@register_contest_format('tmath_open')
class TmathPenaltyContestFormat(DefaultContestFormat):
    name = gettext_lazy('Tmath Open')
    config_defaults = {
        'delay_time': 15,
        'point_penalty': {4: 1, 7: 2},
        'time_penalty': {15: 2, 30: 4, 60: 8},
    }
    config_validators = {'delay_time': lambda x: x >= 0,
                         'point_penalty': lambda x: all(isinstance(k, int) and k > 0 and isinstance(v, (int, float)) and v >= 0 for k, v in x.items()),
                         'time_penalty': lambda x: all(isinstance(k, int) and k > 0 and isinstance(v, (int, float)) and v >= 0 for k, v in x.items())}
    ''' Configuration options:
    - delay_time: Time in minutes after which penalties start to apply for each problem
    - point_penalty: Dictionary mapping number of incorrect submissions to point penalty
    - time_penalty: Dictionary mapping time thresholds in minutes to time penalty points
    '''

#     def greetings(self):
#         cfg = self.config_defaults

#         delay = cfg['delay_time']
#         max_score = cfg.get('max_score', 100)

#         # ===============================
#         # Penalty theo số lần nạp
#         # ===============================
#         pp = dict(sorted(cfg['point_penalty'].items()))
#         pp_keys = list(pp.keys())

#         wrong_lines = []
#         safe_until = pp_keys[0] - 1
#         wrong_lines.append(f"1-{safe_until} lần sai: không sao")

#         for i, k in enumerate(pp_keys):
#             pen = pp[k]
#             if i + 1 < len(pp_keys):
#                 nxt = pp_keys[i + 1] - 1
#                 wrong_lines.append(f"{k}-{nxt} lần sai: -{pen} điểm / lần")
#             else:
#                 wrong_lines.append(f"≥{k} lần sai: -{pen} điểm / lần")

#         # ===============================
#         # Penalty theo thời gian
#         # ===============================
#         tp = dict(sorted(cfg['time_penalty'].items()))
#         tp_keys = list(tp.keys())

#         time_lines = []
#         time_lines.append(f"0-{tp_keys[0] - 1} phút: không bị trừ điểm")

#         for i, k in enumerate(tp_keys):
#             pen = tp[k]
#             if i + 1 < len(tp_keys):
#                 nxt = tp_keys[i + 1] - 1
#                 time_lines.append(f"{k}-{nxt} phút: -{pen} điểm")
#             else:
#                 time_lines.append(f"> {k} phút: -{pen} điểm")

#         # ===============================
#         # Render Markdown
#         # ===============================
#         return f"""
# ## ⚡ Thể lệ nhanh — Cách tính điểm

# - ✅ **Mỗi bài có đồng hồ tính giờ riêng**  
#   Bài 1 tính từ phút 0, bài 2 từ phút {delay}, bài 3 từ phút {2 * delay}, …

# - ✅ **Sai vài lần đầu KHÔNG bị trừ điểm**  
#   {'  \n  '.join(wrong_lines)}

# - ✅ **Làm sớm được điểm cao hơn**  
#   Penalty thời gian chỉ tính theo thời gian làm bài:
#   {'  \n  '.join(time_lines)}

# - ✅ **Mỗi bài tối đa {max_score} điểm**
# """

    @classmethod
    def validate(cls, config):
        if config is None:
            return

        if not isinstance(config, dict):
            raise ValidationError('Tmath-styled contest expects no config or dict as config')

        for key, value in config.items():
            if key not in cls.config_defaults:
                raise ValidationError('unknown config key "%s"' % key)
            if not isinstance(value, type(cls.config_defaults[key])):
                raise ValidationError('invalid type for config key "%s"' % key)
            if not cls.config_validators[key](value):
                raise ValidationError('invalid value "%s" for config key "%s"' % (value, key))

    def __init__(self, contest, config):
        self.config = self.config_defaults.copy()
        self.config.update(config or {})
        self.contest = contest

    def update_participation(self, participation):
        cumtime = 0
        last = 0
        score = 0
        format_data = {}

        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT 
                    MAX(cs.points) AS `points`,
                    (
                        SELECT MIN(csub.date)
                        FROM judge_contestsubmission ccs 
                        LEFT OUTER JOIN judge_submission csub 
                            ON (csub.id = ccs.submission_id)
                        WHERE ccs.problem_id = cp.id 
                        AND ccs.participation_id = %s 
                        AND ccs.points = MAX(cs.points)
                    ) AS `time`,
                    cp.id AS `prob`,
                    cp.order AS `ord`
                FROM judge_contestproblem cp
                INNER JOIN judge_contestsubmission cs 
                    ON (cs.problem_id = cp.id AND cs.participation_id = %s)
                LEFT OUTER JOIN judge_submission sub 
                    ON (sub.id = cs.submission_id)
                GROUP BY cp.id, cp.order
                ORDER BY cp.order ASC
            ''', (participation.id, participation.id))

            for points, time, prob, order in cursor.fetchall():
                time = from_database_time(time)
                dt = (time - participation.start).total_seconds()

                # Compute penalty
                if self.config['point_penalty']:
                    # An IE can have a submission result of `None`
                    subs = participation.submissions.exclude(submission__result__isnull=True) \
                                                    .exclude(submission__result__in=['IE', 'CE']) \
                                                    .filter(problem_id=prob)
                    if points:
                        prev = subs.filter(submission__date__lte=time).count() - 1
                    else:
                        # We should always display the penalty, even if the user has a score of 0
                        prev = subs.count()
                else:
                    prev = 0

                pen_points = 0
                if points:
                    cumtime += dt
                    delay = self.config['delay_time'] * order
                    overtime = max(0, dt - delay * 60)  # in minutes
                    time_pen = 0
                    for t_limit, t_pen in self.config['time_penalty'].items():
                        if overtime > t_limit * 60:
                            time_pen = max(time_pen, t_pen)
                    point_pen = calc_total_point_penalty(prev, self.config['point_penalty'])
                    pen_points = time_pen + point_pen
                    last = max(last, dt)

                format_data[str(prob)] = {'time': dt, 'points': points, 'penalty': prev, 'pen_points': pen_points}
                score += points - pen_points

        participation.cumtime = max(cumtime, 0)
        participation.score = round(score, self.contest.points_precision)
        participation.tiebreaker = last  # field is sorted from least to greatest
        participation.format_data = format_data
        participation.save()

    def display_user_problem(self, participation, contest_problem):
        format_data = (participation.format_data or {}).get(str(contest_problem.id))
        if format_data:
            point = contest_problem.points
            return {
                'has_data': True,
                'problem': contest_problem.order,
                'username': participation.user.user.username,
                'penalty': floatformat(format_data['penalty']) if format_data['penalty'] else -1,
                'points': floatformat(format_data['points'] - format_data['pen_points']),
                'time': nice_repr(timedelta(seconds=format_data['time']), 'noday'),
                'state': (('pretest-' if self.contest.run_pretests_only and contest_problem.is_pretested else '') +
                          self.best_solution_state(format_data['points'], point)),
            }
        else:
            return {
                'has_data': False,
                'state': 'unsubmitted',
            }

    def get_label_for_problem(self, index):
        index += 1
        ret = ''
        while index > 0:
            ret += chr((index - 1) % 26 + 65)
            index = (index - 1) // 26
        return ret[::-1]

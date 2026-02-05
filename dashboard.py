"""
This file was generated with the customdashboard management command and
contains the class for the main dashboard.

To activate your index dashboard add the following to your settings.py::
    GRAPPELLI_INDEX_DASHBOARD = 'tmath.dashboard.CustomIndexDashboard'
"""

from django.utils.translation import gettext_lazy as _
from grappelli.dashboard import Dashboard, modules


class TmathDashboard(Dashboard):

    def __init__(self, **kwargs):
        Dashboard.__init__(self, **kwargs)

        self.children.append(modules.AppList(
            title=_('Hot models'),
            column=1,
            collapsible=False,
            models=(
                'judge.models.problem.Problem',
                'judge.models.contest.Contest',
                'judge.models.contest.SampleContest',
                'django.contrib.auth.models.User',
                'judge.models.profile.Profile',
                'judge.models.interface.Log',
            ),
        ))

        self.children.append(modules.AppList(
            title=_('Authentication'),
            column=1,
            collapsible=True,
            css_classes=['grp-closed'],
            models=(
                'django.contrib.auth.models.User',
                "django.contrib.auth.models.Group",
                'judge.models.profile.Profile',
                'django.contrib.admin.models.LogEntry',
            ),
        ))

        self.children.append(modules.AppList(
            title=_('Organizations'),
            column=1,
            collapsible=True,
            css_classes=['grp-closed'],
            models=(
                'judge.models.profile.*',
            ),
            exclude=('judge.models.profile.Profile',),
        ))

        self.children.append(modules.AppList(
            title=_('Problems'),
            column=1,
            collapsible=True,
            css_classes=['grp-closed'],
            models=(
                'judge.models.problem.*',
                'judge.models.problem_data.PublicSolution',
            ),
        ))

        self.children.append(modules.AppList(
            title=_('Contests'),
            column=1,
            collapsible=True,
            css_classes=['grp-closed'],
            models=(
                'judge.models.contest.*',
            ),
        ))

        self.children.append(modules.AppList(
            title=_('Curriculums'),
            column=1,
            collapsible=True,
            css_classes=['grp-closed'],
            models=(
                'judge.models.curriculum.*',
            ),
        ))

        self.children.append(modules.AppList(
            title=_('Submissions'),
            column=1,
            collapsible=True,
            css_classes=['grp-closed'],
            models=(
                'judge.models.submission.*',
                'judge.models.runtime.*',
            ),
        ))

        self.children.append(modules.AppList(
            title=_('Typo'),
            column=1,
            collapsible=True,
            css_classes=['grp-closed'],
            models=(
                'typeracer.models.*',
            ),
        ))

        self.children.append(modules.AppList(
            title=_('Blogs'),
            column=1,
            collapsible=True,
            css_classes=['grp-closed'],
            models=(
                'judge.models.comment.*',
                'judge.models.ticket.*',
                'judge.models.interface.BlogPost',
            ),
        ))

        self.children.append(modules.AppList(
            title=_('Settings'),
            column=1,
            collapsible=True,
            css_classes=['grp-closed'],
            models=(
                'django.contrib.flatpages.*',
                'django.contrib.sites.*',
                'judge.models.interface.NavigationBar',
            ),
        ))

        self.children.append(modules.RecentActions(
            title=_('Recent actions'),
            column=2,
            collapsible=False,
            limit=20,
        ))

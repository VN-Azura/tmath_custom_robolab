from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.contrib.flatpages.models import FlatPage

from judge.admin.comments import CommentAdmin
from judge.admin.contest import (ContestAdmin, ContestParticipationAdmin,
                                 ContestSubmissionAdmin, ContestTagAdmin)
from judge.admin.curriculum import CurriculumAdmin
from judge.admin.interface import (BlogPostAdmin, CourseAdmin, FlatPageAdmin,
                                   LicenseAdmin, LogAdmin, LogEntryAdmin,
                                   NavigationBarAdmin)
from judge.admin.organization import (OrganizationAdmin,
                                      OrganizationRequestAdmin)
from judge.admin.problem import (LogDownloadTestCaseAdmin, ProblemAdmin,
                                 PublicSolutionAdmin)
from judge.admin.profile import ProfileAdmin, UserAdmin
from judge.admin.runtime import JudgeAdmin, LanguageAdmin
from judge.admin.submission import SubmissionAdmin
from judge.admin.taxon import (ProblemClassAdmin, ProblemGroupAdmin,
                               ProblemTypeAdmin, SchoolYearAdmin)
from judge.admin.ticket import TicketAdmin
from judge.models import (BlogPost, Comment, CommentLock, Contest,
                          ContestLevel, ContestParticipation,
                          ContestSubmission, ContestTag, CourseModel,
                          Curriculum, Judge, Language, License, Log,
                          MiscConfig, NavigationBar, Organization,
                          OrganizationRequest, Problem, ProblemClass,
                          ProblemGroup, ProblemType, Profile, SchoolYear,
                          Submission, Ticket)
from judge.models.problem_data import LogDownloadTestCase, PublicSolution

admin.site.register(BlogPost, BlogPostAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(CommentLock)
admin.site.register(Contest, ContestAdmin)
admin.site.register(ContestSubmission, ContestSubmissionAdmin)
admin.site.register(ContestLevel)
admin.site.register(ContestParticipation, ContestParticipationAdmin)
admin.site.register(ContestTag, ContestTagAdmin)
admin.site.unregister(FlatPage)
admin.site.register(FlatPage, FlatPageAdmin)
admin.site.register(Judge, JudgeAdmin)
admin.site.register(Language, LanguageAdmin)
admin.site.register(License, LicenseAdmin)
admin.site.register(LogEntry, LogEntryAdmin)
admin.site.register(Log, LogAdmin)
admin.site.register(MiscConfig)
admin.site.register(NavigationBar, NavigationBarAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(OrganizationRequest, OrganizationRequestAdmin)
admin.site.register(Problem, ProblemAdmin)
admin.site.register(ProblemGroup, ProblemGroupAdmin)
admin.site.register(ProblemType, ProblemTypeAdmin)
admin.site.register(ProblemClass, ProblemClassAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(SchoolYear, SchoolYearAdmin)
admin.site.register(Submission, SubmissionAdmin)
admin.site.register(Ticket, TicketAdmin)
admin.site.register(CourseModel, CourseAdmin)
admin.site.register(PublicSolution, PublicSolutionAdmin)
admin.site.register(Curriculum, CurriculumAdmin)
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(LogDownloadTestCase, LogDownloadTestCaseAdmin)

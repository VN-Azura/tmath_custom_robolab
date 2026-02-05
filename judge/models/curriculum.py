from django.db import models
from django.utils.translation import gettext_lazy as _

__all__ = ["Curriculum", "CurriculumContest", "PublicProblem"]


class Curriculum(models.Model):
    name = models.CharField(_("name"), max_length=255, help_text=_("Name of the curriculum"))
    description = models.TextField(_("description"), blank=True, help_text=_("Description of the curriculum"))
    problems = models.ManyToManyField('judge.Problem', verbose_name=_("problems"), blank=True,
                                      through="PublicProblem", help_text=_("Problems in the curriculum"))
    contests = models.ManyToManyField('judge.Contest', verbose_name=_("contests"), blank=True,
                                      through="CurriculumContest", help_text=_("Contests in the curriculum"))

    def __str__(self):
        return self.name


class CurriculumContest(models.Model):
    curriculum = models.ForeignKey(Curriculum, verbose_name=_("curriculum"),
                                   related_name="curriculum_contests", on_delete=models.CASCADE)
    contest = models.ForeignKey('judge.Contest', verbose_name=_("contest"),
                                related_name="curriculums", on_delete=models.CASCADE)
    description = models.CharField(_("description"), blank=True, max_length=255,
                                   help_text=_("Description of the contest in the curriculum"))
    order = models.IntegerField(_("order"), default=0, help_text=_("Order of the contest in the curriculum"))

    class Meta:
        ordering = ["order"]
        unique_together = [["curriculum", "contest"]]

    def __str__(self):
        return f"{self.curriculum.name} - {self.contest.name}"


class PublicProblem(models.Model):
    curriculum = models.ForeignKey(Curriculum, verbose_name=_("curriculum"),
                                   related_name="curriculum_problems", on_delete=models.CASCADE)
    problem = models.ForeignKey('judge.Problem', verbose_name=_("problem"),
                                related_name="curriculums", on_delete=models.CASCADE)
    order = models.IntegerField(_("order"), default=0, help_text=_("Order of the problem in the curriculum"))

    class Meta:
        ordering = ["order"]
        unique_together = [["curriculum", "problem"]]

    def __str__(self):
        return f"{self.curriculum.name} - {self.problem.name}"

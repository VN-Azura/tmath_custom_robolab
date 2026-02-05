from typing import Optional

from django import forms
from django.contrib import admin
from django.db.models import Count
from grappelli.forms import GrappelliSortableHiddenMixin

from judge.models import (Contest, Curriculum, CurriculumContest, Problem,
                          PublicProblem)


class CurriculumContestInline(GrappelliSortableHiddenMixin, admin.TabularInline):
    model = CurriculumContest
    extra = 0
    autocomplete_fields = ["contest"]
    sortable_field_name = "order"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "contest":
            kwargs["queryset"] = Contest.objects.filter(is_visible=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class PublicProblemInline(GrappelliSortableHiddenMixin, admin.TabularInline):
    model = PublicProblem
    extra = 0
    autocomplete_fields = ["problem"]
    sortable_field_name = "order"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "problem":
            kwargs["queryset"] = Problem.objects.annotate(case_count=Count('cases')) \
                .filter(case_count__gt=0, is_public=False).order_by('-pk')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class CurriculumForm(forms.ModelForm):
    class Meta:
        model = Curriculum
        fields = "__all__"


class CurriculumAdmin(admin.ModelAdmin):
    form = CurriculumForm
    list_display = ["name", "count_contest", "count_problem"]
    search_fields = ["name"]
    inlines = [CurriculumContestInline, PublicProblemInline]

    def count_contest(self, obj: Curriculum) -> Optional[int]:
        return obj.contests.count()
    count_contest.short_description = "Contests"

    def count_problem(self, obj: Curriculum) -> Optional[int]:
        return obj.problems.count()
    count_problem.short_description = "Problems"

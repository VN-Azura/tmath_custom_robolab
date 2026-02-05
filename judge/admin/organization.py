from django.contrib import admin
from django.db import transaction
from django.forms import ModelForm
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from reversion.admin import VersionAdmin

from judge.models import Contest, Organization
from judge.widgets import AdminMartorWidget


class OrganizationForm(ModelForm):
    class Meta:
        widgets = {
            'about': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('organization_preview')}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__original_rate = self.instance.rate

    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        new_rate = self.cleaned_data.get('rate')

        if self.__original_rate != new_rate:
            with transaction.atomic():
                contests = Contest.objects.filter(organizations=instance)
                for contest in contests:
                    if contest.is_rated:
                        if contest.organizations.count() == 1:
                            contest.rating_ceiling = new_rate
                        else:
                            contest.rating_ceiling = min(contest.rating_ceiling, new_rate)
                        contest.save()
        if commit:
            instance.save()

        return instance


class OrganizationAdmin(VersionAdmin):
    readonly_fields = ('creation_date',)
    fields = ('name', 'slug', 'short_name', 'rate', 'year', 'is_open', 'is_hidden', 'about', 'logo_override_image', 'slots',
              'creation_date', 'admins')
    list_display = ('name', 'short_name', 'is_open', 'is_hidden', 'slots', 'show_public')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['admins']
    search_fields = ['name', 'slug']
    actions_on_top = True
    actions_on_bottom = True
    form = OrganizationForm

    def show_public(self, obj):
        return format_html('<a href="{0}" class="view_on_site_button">{1}</a>',
                           obj.get_absolute_url(), gettext('View on site'))

    show_public.short_description = ''

    def get_actions(self, request):
        actions = super(OrganizationAdmin, self).get_actions(request)
        func, name, desc = self.get_action('make_hidden')
        actions[name] = (func, name, desc)

        func, name, desc = self.get_action('make_visible')
        actions[name] = (func, name, desc)

        return actions

    def make_hidden(self, request, queryset):
        queryset.update(is_hidden=True)
    make_hidden.short_description = _('Make hidden')

    def make_visible(self, request, queryset):
        queryset.update(is_hidden=False)
    make_visible.short_description = _('Make visible')

    def get_readonly_fields(self, request, obj=None):
        fields = self.readonly_fields
        if not request.user.has_perm('judge.organization_admin'):
            return fields + ('admins', 'is_open', 'slots')
        return fields

    def get_queryset(self, request):
        queryset = Organization.objects.all()
        if request.user.has_perm('judge.edit_all_organization'):
            return queryset
        else:
            return queryset.filter(admins=request.profile.id)

    def has_change_permission(self, request, obj=None):
        if not request.user.has_perm('judge.change_organization'):
            return False
        if request.user.has_perm('judge.edit_all_organization') or obj is None:
            return True
        return obj.admins.filter(id=request.profile.id).exists()


class OrganizationRequestAdmin(admin.ModelAdmin):
    list_display = ('username', 'organization', 'state', 'time')
    readonly_fields = ('user', 'organization', 'state', 'time', 'admin', 'reason')

    def username(self, obj):
        return obj.user.user.username
    username.short_description = _('username')
    username.admin_order_field = 'user__user__username'

    def has_add_permission(self, request):
        return False

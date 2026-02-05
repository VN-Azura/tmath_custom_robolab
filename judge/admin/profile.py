from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as OldUserAdmin
from django.forms import ModelForm
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from reversion.admin import VersionAdmin

from django_ace import AceWidget
from judge.models import Profile, WebAuthnCredential
from judge.utils.views import NoBatchDeleteMixin
from judge.widgets import AdminMartorWidget


class ProfileForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        if 'current_contest' in self.base_fields:
            # form.fields['current_contest'] does not exist when the user has only view permission on the model.
            self.fields['current_contest'].queryset = self.instance.contest_history.select_related('contest') \
                .only('contest__name', 'user_id', 'virtual')
            self.fields['current_contest'].label_from_instance = \
                lambda obj: '%s v%d' % (obj.contest.name, obj.virtual) if obj.virtual else obj.contest.name

    class Meta:
        widgets = {
            'about': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('profile_preview')}),
        }


class TimezoneFilter(admin.SimpleListFilter):
    title = _('timezone')
    parameter_name = 'timezone'

    def lookups(self, request, model_admin):
        return Profile.objects.values_list('timezone', 'timezone').distinct().order_by('timezone')

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        return queryset.filter(timezone=self.value())


class WebAuthnInline(admin.TabularInline):
    model = WebAuthnCredential
    readonly_fields = ('cred_id', 'public_key', 'counter')
    extra = 0

    def has_add_permission(self, request, obj):
        return False


class ProfileAdmin(NoBatchDeleteMixin, VersionAdmin):
    change_form_template = 'admin/judge/profile/change_form.html'
    fieldsets = (
        (None, {
            "fields": (
                'user',
                'name',
            ),
        }),
        (_('Settings'), {
            "fields": (
                'verified',
                'display_rank',
                'is_unlisted',
                'timezone',
                'language',
                'ace_theme',
                'math_engine',
                'mute',
                'can_download_all_testcases',
            ),
        }),
        (_('Information'), {
            "fields": (
                'about',
                'organizations',
                'last_access',
                'ip',
                'current_contest',
            ),
        }),
        (_('Authorized'), {
            "fields": (
                'notes',
                'expiration_date',
                # 'is_totp_enabled',
                # 'user_script',
            ),
        }),
    )

    readonly_fields = (
        'user',
        'organizations',
        'about',
        'last_access',
        'ip',
        'current_contest',
        'expiration_date',
    )
    list_display = (
        'admin_user_admin',
        'email',
        # 'is_totp_enabled',
        'timezone_full',
        'date_joined',
        'last_access',
        'ip',
        'show_public',
    )
    ordering = ('user__username',)
    search_fields = ('user__username', 'ip', 'user__email')
    list_filter = ('language', TimezoneFilter)
    actions = ('recalculate_points',)
    actions_on_top = True
    actions_on_bottom = True
    form = ProfileForm
    autocomplete_fields = [
        'language',
    ]
    inlines = [WebAuthnInline]

    def has_add_permission(self, request):
        return False

    def has_view_permission(self, request, obj=None):
        # Người dùng có quyền hoặc là chính họ
        return True if obj is None else obj.user == request.user or request.user.has_perm('judge.view_profile')

    def get_queryset(self, request):
        queryset = super(ProfileAdmin, self).get_queryset(request).select_related('user')
        if not request.user.has_perm('judge.view_profile'):
            queryset = queryset.filter(user=request.user)
        return queryset

    def get_fields(self, request, obj=None):
        if request.user.has_perm('judge.totp'):
            fields = list(self.fields)
            fields.insert(fields.index('is_totp_enabled') + 1, 'totp_key')
            fields.insert(fields.index('totp_key') + 1, 'scratch_codes')
            return tuple(fields)
        else:
            return self.fields

    def get_readonly_fields(self, request, obj=None):
        fields = self.readonly_fields
        if not request.user.has_perm('judge.totp'):
            fields += ('is_totp_enabled',)
        if obj and obj.verified:
            fields += ('name',)
        if not request.profile.super_admin:
            fields += ('can_download_all_testcases',)
        return fields

    def show_public(self, obj):
        return format_html('<a href="{0}" class="view_on_site_button">{1}</a>',
                           obj.get_absolute_url(), gettext('View on site'))
    show_public.short_description = ''

    def admin_user_admin(self, obj):
        return obj.username
    admin_user_admin.admin_order_field = 'user__username'
    admin_user_admin.short_description = _('User')

    def email(self, obj):
        return obj.user.email
    email.admin_order_field = 'user__email'
    email.short_description = _('Email')

    def timezone_full(self, obj):
        return obj.timezone
    timezone_full.admin_order_field = 'timezone'
    timezone_full.short_description = _('Timezone')

    def date_joined(self, obj):
        return obj.user.date_joined
    date_joined.admin_order_field = 'user__date_joined'
    date_joined.short_description = _('date joined')

    def recalculate_points(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.calculate_points()
            count += 1
        self.message_user(request, ngettext('%d user have scores recalculated.',
                                            '%d users have scores recalculated.',
                                            count) % count)
    recalculate_points.short_description = _('Recalculate scores')

    def get_form(self, request, obj=None, **kwargs):
        form = super(ProfileAdmin, self).get_form(request, obj, **kwargs)
        if 'user_script' in form.base_fields:
            # form.base_fields['user_script'] does not exist when the user has only view permission on the model.
            form.base_fields['user_script'].widget = AceWidget('javascript', request.profile.ace_theme)
        return form


class UserAdmin(OldUserAdmin):
    def get_readonly_fields(self, request, obj):
        fields = super().get_readonly_fields(request, obj)
        if not request.profile.super_admin and 'is_superuser' not in fields:
            fields += ('is_superuser', 'user_permissions')

        if not request.user.is_superuser:
            fields += ('username', 'is_staff', 'is_active', 'date_joined', 'last_login', 'groups')

        return fields

    def has_add_permission(self, request):
        return False

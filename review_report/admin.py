from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from .models import Report, Review
from .services import can_moderate, moderate_report, validate_transition


class ModerationForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['status', 'internal_notes', 'public_result']

    def clean(self):
        data = super().clean()
        if self.instance.pk and data.get('status'):
            current = Report.objects.get(pk=self.instance.pk)
            validate_transition(current.status, data['status'], data.get('public_result', ''))
        return data


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    form = ModerationForm
    list_display = ['id', 'reporter', 'category', 'status', 'created_at', 'reviewed_by']
    list_filter = ['status', 'category']
    search_fields = ['reporter__username', 'description']
    readonly_fields = ['id', 'reporter', 'target_item', 'target_user', 'category', 'description',
                       'created_at', 'updated_at', 'reviewed_by', 'reviewed_at', 'resolved_at']
    fields = readonly_fields + ['status', 'internal_notes', 'public_result']
    list_select_related = ['reporter', 'reviewed_by']
    actions = None

    def has_module_permission(self, request):
        return can_moderate(request.user)

    def has_view_permission(self, request, obj=None):
        return can_moderate(request.user)

    def has_change_permission(self, request, obj=None):
        return can_moderate(request.user)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if can_moderate(request.user) else qs.none()

    def save_model(self, request, obj, form, change):
        moderate_report(obj, request.user, form.cleaned_data['status'],
                        internal_notes=form.cleaned_data['internal_notes'], public_result=form.cleaned_data['public_result'])

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except ValidationError as exc:
            # A concurrent moderator may have changed the state after form validation.
            self.message_user(request, '; '.join(exc.messages), messages.ERROR)
            return redirect(request.path)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'item_request', 'rating', 'created_at']
    list_select_related = ['item_request__item']
    readonly_fields = ['id', 'item_request', 'rating', 'comment', 'created_at', 'updated_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

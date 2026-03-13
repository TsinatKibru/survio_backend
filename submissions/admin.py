from django.contrib import admin
from import_export.admin import ExportMixin
from .models import Submission, Answer
from survio.admin import survio_admin_site

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ('question', 'question_label_snapshot', 'value', 'image')

@admin.register(Submission, site=survio_admin_site)
class SubmissionAdmin(ExportMixin, admin.ModelAdmin):
    list_display = ('id', 'form', 'period', 'organization', 'submitted_by', 'status', 'is_late', 'submitted_at')
    list_filter = ('status', 'is_late', 'form')
    search_fields = ('organization__name', 'submitted_by__username', 'industry_name')
    readonly_fields = ('form', 'period', 'organization', 'submitted_by', 'submitted_at', 'form_version')
    inlines = [AnswerInline]

    def has_add_permission(self, request):
        return False  # Submissions come from mobile

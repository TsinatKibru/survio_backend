from django.contrib import admin
from .models import Form, Section, Question, QuestionOption, FormAssignment, ReportingPeriod
from survio.admin import survio_admin_site

class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 1

class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    show_change_link = True

class SectionInline(admin.TabularInline):
    model = Section
    extra = 1
    show_change_link = True

class ReportingPeriodInline(admin.TabularInline):
    model = ReportingPeriod
    extra = 1
    fields = ('label', 'period_start', 'period_end', 'due_date', 'close_date')
    readonly_fields = ()

@admin.register(Form, site=survio_admin_site)
class FormAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'schedule_type', 'version', 'is_active', 'created_at')
    list_filter = ('category', 'schedule_type', 'is_active')
    search_fields = ('title',)
    inlines = [SectionInline, ReportingPeriodInline]
    list_per_page = 10

@admin.register(ReportingPeriod, site=survio_admin_site)
class ReportingPeriodAdmin(admin.ModelAdmin):
    list_display = ('label', 'form', 'period_start', 'period_end', 'due_date', 'close_date', 'computed_status')
    list_filter = ('form',)
    search_fields = ('label', 'form__title')
    list_per_page = 10

    @admin.display(description='Status')
    def computed_status(self, obj):
        return obj.status

@admin.register(Section, site=survio_admin_site)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'form', 'order')
    list_filter = ('form',)
    inlines = [QuestionInline]
    list_per_page = 10

@admin.register(Question, site=survio_admin_site)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('label', 'section', 'question_type', 'is_required', 'order')
    list_filter = ('question_type', 'section__form')
    search_fields = ('label',)
    inlines = [QuestionOptionInline]
    list_per_page = 10

@admin.register(FormAssignment, site=survio_admin_site)
class FormAssignmentAdmin(admin.ModelAdmin):
    list_display = ('form', 'industry', 'user', 'is_active')
    list_filter = ('is_active', 'form')
    list_per_page = 10

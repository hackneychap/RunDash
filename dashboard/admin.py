from django.contrib import admin
from .models import ARace, TrainingBlock, TrainingBlockSection, BRace, RunActivity


class TrainingBlockSectionInline(admin.TabularInline):
    model = TrainingBlockSection
    extra = 1
    ordering = ['order']


class BRaceInline(admin.TabularInline):
    model = BRace
    extra = 0


@admin.register(ARace)
class ARaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'feeling']
    list_filter = ['date']
    search_fields = ['name']
    date_hierarchy = 'date'


@admin.register(TrainingBlock)
class TrainingBlockAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'a_race']
    list_filter = ['start_date']
    inlines = [TrainingBlockSectionInline, BRaceInline]


@admin.register(TrainingBlockSection)
class TrainingBlockSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'training_block', 'order', 'start_date', 'end_date']
    list_filter = ['training_block']
    ordering = ['training_block', 'order']


@admin.register(BRace)
class BRaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'distance_km', 'training_block']
    list_filter = ['date', 'training_block']
    search_fields = ['name']


@admin.register(RunActivity)
class RunActivityAdmin(admin.ModelAdmin):
    list_display = ['activity_id', 'date', 'distance_km', 'duration_minutes', 'training_block']
    list_filter = ['date', 'training_block']
    search_fields = ['activity_id']

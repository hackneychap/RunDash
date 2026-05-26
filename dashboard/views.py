import json
from django.shortcuts import render
from django.db.models import Sum, Avg
from django.db.models.functions import TruncWeek, TruncMonth
from django.http import HttpResponse
from django_q.tasks import async_task, Task
from .models import RunActivity
from .tasks import sync_garmin_data

def dashboard(request):
    runs = RunActivity.objects.all().order_by('date')
    
    total_km = runs.aggregate(Sum('distance_km'))['distance_km__sum'] or 0
    total_duration = runs.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
    avg_tss = runs.aggregate(Avg('tss'))['tss__avg'] or 0
    
    weekly_stats = runs.annotate(week=TruncWeek('date')).values('week').annotate(
        total_km=Sum('distance_km'),
        total_duration=Sum('duration_minutes'),
        total_tss=Sum('tss'),
        total_elevation=Sum('elevation_gain')
    ).order_by('week')
    
    monthly_stats = runs.annotate(month=TruncMonth('date')).values('month').annotate(
        total_km=Sum('distance_km'),
        total_duration=Sum('duration_minutes'),
        total_tss=Sum('tss')
    ).order_by('month')
    
    weekly_labels = [stat['week'].strftime('%Y-%m-%d') if stat['week'] else '' for stat in weekly_stats]
    weekly_km = [round(stat['total_km'], 1) if stat['total_km'] else 0 for stat in weekly_stats]
    weekly_tss = [round(stat['total_tss'], 1) if stat['total_tss'] else 0 for stat in weekly_stats]
    weekly_elevation = [round(stat['total_elevation'], 1) if stat['total_elevation'] else 0 for stat in weekly_stats]
    
    monthly_labels = [stat['month'].strftime('%Y-%m') if stat['month'] else '' for stat in monthly_stats]
    monthly_km = [round(stat['total_km'], 1) if stat['total_km'] else 0 for stat in monthly_stats]
    
    context = {
        'total_km': round(total_km, 2),
        'total_duration': round(total_duration / 60, 1), # Hours
        'avg_tss': round(avg_tss, 1),
        'weekly_labels': json.dumps(weekly_labels),
        'weekly_km': json.dumps(weekly_km),
        'weekly_tss': json.dumps(weekly_tss),
        'weekly_elevation': json.dumps(weekly_elevation),
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_km': json.dumps(monthly_km),
    }
    return render(request, 'dashboard.html', context)

def trigger_sync(request):
    task_id = async_task(sync_garmin_data)
    return HttpResponse(f"""
        <div id="sync-container" hx-get="/sync-status/{task_id}/" hx-trigger="every 5s" hx-swap="outerHTML" class="flex items-center gap-3 p-4 bg-base-200 rounded-xl mt-4">
            <span class="loading loading-spinner loading-md text-primary"></span>
            <span class="text-sm font-medium">Syncing with Garmin (this may take several minutes)...</span>
        </div>
    """)

def sync_status(request, task_id):
    # In django-q2, Task.get_task returns a Task object if done, None if not done
    task = Task.get_task(task_id)
    if task:
        if task.success:
            return HttpResponse("""
                <div class="alert alert-success mt-4">
                    <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    <span>Sync complete! Refreshing...</span>
                </div>
                <script>setTimeout(() => window.location.reload(), 1500);</script>
            """)
        else:
            return HttpResponse("""
                <div class="alert alert-error mt-4">
                    <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    <span>Sync failed. Check console or worker logs.</span>
                </div>
            """)
    else:
        return HttpResponse(f"""
            <div id="sync-container" hx-get="/sync-status/{task_id}/" hx-trigger="every 5s" hx-swap="outerHTML" class="flex items-center gap-3 p-4 bg-base-200 rounded-xl mt-4">
                <span class="loading loading-spinner loading-md text-primary"></span>
                <span class="text-sm font-medium">Syncing with Garmin (this may take several minutes)...</span>
            </div>
        """)

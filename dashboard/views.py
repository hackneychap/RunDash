import json
import os
import time
from django.shortcuts import render
from django.db.models import Sum, Avg
from django.db.models.functions import TruncWeek, TruncMonth
from django.core.cache import cache
from django.http import HttpResponse
from django.conf import settings
from django_q.tasks import async_task, Task
from .models import RunActivity
from .tasks import sync_garmin_data

LOCK_FILE = os.path.join(settings.BASE_DIR, 'garmin_sync.lock')
LOCK_TIMEOUT = 1200  # 20 minutes timeout

def dashboard(request):
    # ⚡ Bolt Optimization: Cache the entire dashboard context to avoid expensive DB aggregations on every load
    # Expected impact: Dramatically faster load times as DB hit count goes from 3 expensive group-bys to 0 on cache hit.
    context = cache.get('dashboard_context')
    
    if not context:
        runs = RunActivity.objects.all().order_by('date')

        # ⚡ Bolt Optimization: Combine 3 separate aggregates into a single DB query
        # Reduces N+1 query pattern on the dashboard load
        aggregates = runs.aggregate(
            total_km=Sum('distance_km'),
            total_duration=Sum('duration_minutes'),
            avg_tss=Avg('tss')
        )

        total_km = aggregates['total_km'] or 0
        total_duration = aggregates['total_duration'] or 0
        avg_tss = aggregates['avg_tss'] or 0

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

        weekly_labels, weekly_km, weekly_tss, weekly_elevation = [], [], [], []
        for stat in weekly_stats:
            weekly_labels.append(stat['week'].strftime('%Y-%m-%d') if stat['week'] else '')
            weekly_km.append(round(stat['total_km'], 1) if stat['total_km'] else 0)
            weekly_tss.append(round(stat['total_tss'], 1) if stat['total_tss'] else 0)
            weekly_elevation.append(round(stat['total_elevation'], 1) if stat['total_elevation'] else 0)

        monthly_labels, monthly_km = [], []
        for stat in monthly_stats:
            monthly_labels.append(stat['month'].strftime('%Y-%m') if stat['month'] else '')
            monthly_km.append(round(stat['total_km'], 1) if stat['total_km'] else 0)

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
        # Cache the resulting context indefinitely (invalidated by signals on model changes or sync)
        cache.set('dashboard_context', context, timeout=None)

    return render(request, 'dashboard.html', context)

def trigger_sync(request):
    # Check if lock file exists and is fresh
    if os.path.exists(LOCK_FILE):
        file_age = time.time() - os.path.getmtime(LOCK_FILE)
        if file_age < LOCK_TIMEOUT:
            return HttpResponse("""
                <div id="sync-container" hx-get="/sync-status/active/" hx-trigger="every 5s" hx-swap="outerHTML" class="flex items-center gap-3 p-4 bg-base-200 rounded-xl mt-4">
                    <span class="loading loading-spinner loading-md text-primary"></span>
                    <span class="text-sm font-medium">Syncing with Garmin (checking status)...</span>
                </div>
            """)

    # If no active lock exists, trigger a new sync task
    task_id = async_task(sync_garmin_data)
    
    # Write the task_id to the lock file
    try:
        with open(LOCK_FILE, 'w') as f:
            json.dump({"task_id": task_id, "status": "downloading"}, f, indent=4)
    except IOError:
        pass

    return HttpResponse(f"""
        <div id="sync-container" hx-get="/sync-status/{task_id}/" hx-trigger="every 5s" hx-swap="outerHTML" class="flex items-center gap-3 p-4 bg-base-200 rounded-xl mt-4">
            <span class="loading loading-spinner loading-md text-primary"></span>
            <span class="text-sm font-medium">Syncing with Garmin (this may take several minutes)...</span>
        </div>
    """)


def sync_status(request, task_id):
    if not os.path.exists(LOCK_FILE):
        return HttpResponse("""
            <div class="alert alert-success mt-4">
                <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span>Sync complete! Refreshing...</span>
            </div>
            <script>setTimeout(() => window.location.reload(), 1500);</script>
        """)

    try:
        with open(LOCK_FILE, 'r') as f:
            status_data = json.load(f)
    except Exception:
        status_data = {}

    status = status_data.get("status")
    active_task_id = status_data.get("task_id", task_id)

    if status == "failed":
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass
        error_msg = status_data.get("error", "Check logs.")
        return HttpResponse(f"""
            <div class="alert alert-error mt-4">
                <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span>Sync failed: {error_msg}</span>
            </div>
        """)

    if active_task_id:
        task = Task.get_task(active_task_id)
        if task and not task.success:
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
            return HttpResponse("""
                <div class="alert alert-error mt-4">
                    <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    <span>Sync task failed. Check worker logs.</span>
                </div>
            """)

    # Map status to nice readable message
    if status == "downloading":
        msg = "Downloading activities from Garmin Connect..."
    elif status == "importing":
        current = status_data.get("current_batch", 1)
        total = status_data.get("total_batches", 1)
        msg = f"Importing runs to database (Batch {current} of {total})..."
    elif status == "finalizing":
        msg = "Finalizing dashboard sync..."
    else:
        msg = "Syncing with Garmin (this may take several minutes)..."

    return HttpResponse(f"""
        <div id="sync-container" hx-get="/sync-status/{task_id}/" hx-trigger="every 5s" hx-swap="outerHTML" class="flex items-center gap-3 p-4 bg-base-200 rounded-xl mt-4">
            <span class="loading loading-spinner loading-md text-primary"></span>
            <span class="text-sm font-medium">{msg}</span>
        </div>
    """)

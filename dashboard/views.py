import json
import os
import time
from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect
from django.db.models import Sum, Avg, Count, OuterRef, Subquery, IntegerField, FloatField
from django.db.models.functions import TruncWeek, TruncMonth, Coalesce
from django.http import HttpResponse
from django.conf import settings
from django_q.tasks import async_task, Task
from .models import RunActivity, TrainingBlock, BRace
from .tasks import sync_garmin_data

LOCK_FILE = os.path.join(settings.BASE_DIR, 'garmin_sync.lock')
LOCK_TIMEOUT = 1200  # 20 minutes timeout

def dashboard(request):
    runs = RunActivity.objects.all().order_by('date')
    
    # ⚡ Bolt Optimization: Combine 3 separate aggregates into a single DB query
    # Reduces N+1 query pattern on the dashboard load
    aggregates = runs.aggregate(
        total_km=Sum('distance_km'),
        total_duration=Sum('duration_minutes'),
        total_elevation=Sum('elevation_gain'),
        avg_tss=Avg('tss')
    )

    total_km = aggregates['total_km'] or 0
    total_duration = aggregates['total_duration'] or 0
    total_elevation = aggregates['total_elevation'] or 0
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
    
    weekly_labels, weekly_km, weekly_tss, weekly_elevation, weekly_duration = [], [], [], [], []
    for stat in weekly_stats:
        weekly_labels.append(stat['week'].strftime('%Y-%m-%d') if stat['week'] else '')
        weekly_km.append(round(stat['total_km'], 1) if stat['total_km'] else 0)
        weekly_tss.append(round(stat['total_tss'], 1) if stat['total_tss'] else 0)
        weekly_elevation.append(round(stat['total_elevation'], 1) if stat['total_elevation'] else 0)
        weekly_duration.append(round((stat['total_duration'] or 0) / 60, 1))

    monthly_labels, monthly_km = [], []
    for stat in monthly_stats:
        monthly_labels.append(stat['month'].strftime('%Y-%m') if stat['month'] else '')
        monthly_km.append(round(stat['total_km'], 1) if stat['total_km'] else 0)
    
    # Week-vs-week comparison (proportional: same days into the week)
    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())  # Most recent Monday
    last_week_start = this_week_start - timedelta(days=7)
    last_week_same_point = last_week_start + (today - this_week_start)

    this_week_qs = RunActivity.objects.filter(date__gte=this_week_start, date__lte=today)
    last_week_qs = RunActivity.objects.filter(date__gte=last_week_start, date__lte=last_week_same_point)

    tw_agg = this_week_qs.aggregate(
        d=Sum('distance_km'), e=Sum('elevation_gain'),
        dur=Sum('duration_minutes'), t=Sum('tss'))
    lw_agg = last_week_qs.aggregate(
        d=Sum('distance_km'), e=Sum('elevation_gain'),
        dur=Sum('duration_minutes'), t=Sum('tss'))

    tw_dist = round(tw_agg['d'] or 0, 1)
    lw_dist = round(lw_agg['d'] or 0, 1)
    tw_elev = round(tw_agg['e'] or 0, 1)
    lw_elev = round(lw_agg['e'] or 0, 1)
    tw_dur  = round((tw_agg['dur'] or 0) / 60, 1)
    lw_dur  = round((lw_agg['dur'] or 0) / 60, 1)
    tw_tss  = round(tw_agg['t'] or 0, 1)
    lw_tss  = round(lw_agg['t'] or 0, 1)

    def pct(this, last):
        if last == 0:
            return None
        return round(((this - last) / last) * 100, 1)

    context = {
        'total_km': round(total_km, 2),
        'total_duration': round(total_duration / 60, 1), # Hours
        'total_elevation': round(total_elevation, 1),
        'avg_tss': round(avg_tss, 1),
        'weekly_labels': json.dumps(weekly_labels),
        'weekly_km': json.dumps(weekly_km),
        'weekly_tss': json.dumps(weekly_tss),
        'weekly_elevation': json.dumps(weekly_elevation),
        'weekly_duration': json.dumps(weekly_duration),
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_km': json.dumps(monthly_km),
        # Week-vs-week comparison cards
        'tw_dist': tw_dist, 'lw_dist': lw_dist, 'pct_dist': pct(tw_dist, lw_dist),
        'tw_elev': tw_elev, 'lw_elev': lw_elev, 'pct_elev': pct(tw_elev, lw_elev),
        'tw_dur': tw_dur, 'lw_dur': lw_dur, 'pct_dur': pct(tw_dur, lw_dur),
        'tw_tss': tw_tss, 'lw_tss': lw_tss, 'pct_tss': pct(tw_tss, lw_tss),
    }
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


def block_compare(request):
    """
    Compare two training blocks aligned by weeks out from race date.
    
    The race date is the anchor - we count backwards from it.
    Both blocks are plotted on the same 'weeks out from race' axis.
    """
    from .models import TrainingBlock, TrainingBlockSection, RunActivity
    from datetime import timedelta
    
    today = date.today()
    
    # Get all blocks ordered by start date
    all_blocks = TrainingBlock.objects.select_related('a_race').order_by('-start_date')
    
    # Auto-detect current block (today is within its dates)
    current_block = None
    for block in all_blocks:
        if block.start_date <= today <= block.end_date:
            current_block = block
            break
    
    # If no current block, use the most recent one
    if current_block is None and all_blocks.exists():
        current_block = all_blocks.first()
    
    # Get the selected comparison block from query params
    compare_block_id = request.GET.get('compare_block')
    compare_block = None
    if compare_block_id:
        compare_block = TrainingBlock.objects.filter(id=compare_block_id).first()
    elif current_block:
        # Default: compare with the next most recent block
        compare_block = all_blocks.exclude(id=current_block.id).first()
    
    # Calculate weeks out from race for a given date in a block
    def get_weeks_out(block, d):
        """Calculate weeks out from race date."""
        delta = block.a_race.date - d
        return delta.days // 7
    
    # Query data for both blocks
    block_a_data = []
    block_b_data = []
    block_a_sections = []
    block_b_sections = []
    
    if current_block and compare_block:
        # Block A (current block) - query all activities
        activities_a = RunActivity.objects.filter(
            training_block=current_block
        ).order_by('date')
        
        # Group by weeks out from race
        weeks_a = {}
        for activity in activities_a:
            weeks_out = get_weeks_out(current_block, activity.date)
            if weeks_out not in weeks_a:
                weeks_a[weeks_out] = {'distance': 0, 'duration': 0, 'elevation': 0, 'tss': 0}
            weeks_a[weeks_out]['distance'] += activity.distance_km
            weeks_a[weeks_out]['duration'] += activity.duration_minutes
            weeks_a[weeks_out]['elevation'] += (activity.elevation_gain or 0)
            weeks_a[weeks_out]['tss'] += (activity.tss or 0)
        
        # Convert to sorted list
        for week_num in sorted(weeks_a.keys(), reverse=True):
            data = weeks_a[week_num]
            block_a_data.append({
                'week': week_num,
                'distance': round(data['distance'], 1),
                'duration': round(data['duration'] / 60, 1),  # Convert to hours
                'elevation': round(data['elevation'], 0),
                'tss': round(data['tss'], 0),
            })
        
        # Block A sections
        sections_a = current_block.sections.all().order_by('order')
        for section in sections_a:
            block_a_sections.append({
                'name': section.name,
                'start_week': get_weeks_out(current_block, section.start_date),
                'end_week': get_weeks_out(current_block, section.end_date),
            })
        
        # Block B (comparison block) - query all activities
        activities_b = RunActivity.objects.filter(
            training_block=compare_block
        ).order_by('date')
        
        # Group by weeks out from race
        weeks_b = {}
        for activity in activities_b:
            weeks_out = get_weeks_out(compare_block, activity.date)
            if weeks_out not in weeks_b:
                weeks_b[weeks_out] = {'distance': 0, 'duration': 0, 'elevation': 0, 'tss': 0}
            weeks_b[weeks_out]['distance'] += activity.distance_km
            weeks_b[weeks_out]['duration'] += activity.duration_minutes
            weeks_b[weeks_out]['elevation'] += (activity.elevation_gain or 0)
            weeks_b[weeks_out]['tss'] += (activity.tss or 0)
        
        # Convert to sorted list
        for week_num in sorted(weeks_b.keys(), reverse=True):
            data = weeks_b[week_num]
            block_b_data.append({
                'week': week_num,
                'distance': round(data['distance'], 1),
                'duration': round(data['duration'] / 60, 1),
                'elevation': round(data['elevation'], 0),
                'tss': round(data['tss'], 0),
            })
        
        # Block B sections
        sections_b = compare_block.sections.all().order_by('order')
        for section in sections_b:
            block_b_sections.append({
                'name': section.name,
                'start_week': get_weeks_out(compare_block, section.start_date),
                'end_week': get_weeks_out(compare_block, section.end_date),
            })
    
    context = {
        'all_blocks': all_blocks,
        'current_block': current_block,
        'compare_block': compare_block,
        'block_a_data': json.dumps(block_a_data),
        'block_b_data': json.dumps(block_b_data),
        'block_a_sections': json.dumps(block_a_sections),
        'block_b_sections': json.dumps(block_b_sections),
        'block_a_name': current_block.name if current_block else 'Current Block',
        'block_b_name': compare_block.name if compare_block else 'Compare Block',
    }
    
    return render(request, 'block_compare.html', context)


def blocks_list(request):
    """List all training blocks with summary stats."""
    today = date.today()

    # ⚡ Bolt Optimization: Replace prefetch_related and in-memory aggregation
    # with database-level subqueries to avoid serialization overhead and N+1 issues
    # Expected impact: Significantly reduces memory usage and execution time (~2-3x faster)
    runs_subquery = RunActivity.objects.filter(
        training_block=OuterRef('pk')
    ).values('training_block').annotate(
        total_km=Sum('distance_km'),
        total_runs=Count('id')
    )

    b_races_subquery = BRace.objects.filter(
        training_block=OuterRef('pk')
    ).values('training_block').annotate(
        count=Count('id')
    )

    all_blocks = TrainingBlock.objects.select_related('a_race').annotate(
        annotated_total_km=Coalesce(Subquery(runs_subquery.values('total_km')[:1], output_field=FloatField()), 0.0),
        annotated_total_runs=Coalesce(Subquery(runs_subquery.values('total_runs')[:1], output_field=IntegerField()), 0),
        annotated_b_races_count=Coalesce(Subquery(b_races_subquery.values('count')[:1], output_field=IntegerField()), 0)
    ).order_by('-start_date')

    # Annotate each block with stats
    blocks_with_stats = []
    for block in all_blocks:
        # Status determination
        if block.start_date <= today <= block.end_date:
            status = 'active'
        elif today > block.end_date:
            status = 'completed'
        else:
            status = 'upcoming'

        # Duration in weeks
        duration_days = (block.end_date - block.start_date).days
        duration_weeks = max(round(duration_days / 7), 1)

        blocks_with_stats.append({
            'block': block,
            'status': status,
            'duration_weeks': duration_weeks,
            'total_km': round(block.annotated_total_km, 1),
            'total_runs': block.annotated_total_runs,
            'b_races_count': block.annotated_b_races_count,
        })


    # Sort: active first, then completed in reverse date order, then upcoming
    active = [b for b in blocks_with_stats if b['status'] == 'active']
    completed = [b for b in blocks_with_stats if b['status'] == 'completed']
    upcoming = [b for b in blocks_with_stats if b['status'] == 'upcoming']
    sorted_blocks = active + completed + upcoming

    context = {
        'blocks': sorted_blocks,
        'today': today,
    }
    return render(request, 'blocks_list.html', context)


def block_create(request):
    """Create a new A Race and Training Block in one form."""
    from datetime import timedelta
    from .forms import ARaceForm, TrainingBlockForm

    if request.method == 'POST':
        race_form = ARaceForm(request.POST, prefix='race')
        block_form = TrainingBlockForm(request.POST, prefix='block')
        if race_form.is_valid() and block_form.is_valid():
            a_race = race_form.save()
            training_block = block_form.save(commit=False)
            training_block.a_race = a_race
            if not training_block.start_date:
                training_block.start_date = a_race.date - timedelta(weeks=TrainingBlockForm.DEFAULT_BLOCK_LENGTH_WEEKS)
            if not training_block.end_date:
                training_block.end_date = a_race.date
            if not training_block.name:
                training_block.name = f"{a_race.name} Block"
            training_block.save()
            return redirect('block_detail', block_id=training_block.id)
    else:
        race_form = ARaceForm(prefix='race')
        block_form = TrainingBlockForm(prefix='block')

    context = {
        'race_form': race_form,
        'block_form': block_form,
    }
    return render(request, 'block_create.html', context)


def block_detail(request, block_id):
    """Detail page for a single training block."""
    from .models import TrainingBlock, ARace, TrainingBlockSection, BRace
    from collections import defaultdict
    from datetime import date
    
    try:
        training_block = TrainingBlock.objects.select_related('a_race').prefetch_related(
            'sections', 'b_races', 'activities'
        ).get(id=block_id)
    except TrainingBlock.DoesNotExist:
        from django.http import Http404
        raise Http404("Training block not found")
    
    a_race = training_block.a_race
    sections = training_block.sections.all()
    b_races = training_block.b_races.all()
    activities = training_block.activities.all().order_by('date')
    
    # Calculate weeks out from race for each run
    # (a_race.date - run.date).days / 7
    for activity in activities:
        days_to_race = (a_race.date - activity.date).days
        activity.weeks_out = round(days_to_race / 7, 1)
    
    # Group runs by week number (counting from block start)
    weekly_data = defaultdict(lambda: {'distance': 0, 'duration': 0, 'elevation': 0, 'tss': 0, 'run_count': 0})
    
    for activity in activities:
        # Calculate week number from block start
        days_since_start = (activity.date - training_block.start_date).days
        week_num = (days_since_start // 7) + 1  # Week 1, Week 2, etc.
        activity.week_number = week_num
        
        weekly_data[week_num]['distance'] += activity.distance_km or 0
        weekly_data[week_num]['duration'] += activity.duration_minutes or 0
        weekly_data[week_num]['elevation'] += activity.elevation_gain or 0
        weekly_data[week_num]['tss'] += activity.tss or 0
        weekly_data[week_num]['run_count'] += 1
    
    # Convert to sorted list for template
    weekly_stats = []
    for week_num in sorted(weekly_data.keys()):
        data = weekly_data[week_num]
        weekly_stats.append({
            'week_number': week_num,
            'distance': round(data['distance'], 1),
            'duration': round(data['duration'] / 60, 1),  # Convert to hours
            'elevation': round(data['elevation'], 0),
            'tss': round(data['tss'], 1),
            'run_count': data['run_count'],
        })
    
    # Prepare chart data
    chart_labels = [f"Week {s['week_number']}" for s in weekly_stats]
    chart_distance = [s['distance'] for s in weekly_stats]
    chart_tss = [s['tss'] for s in weekly_stats]
    
    # Check if block is active (current date is between start and end)
    today = date.today()
    is_active = training_block.start_date <= today <= training_block.end_date
    
    # Calculate current week number if active
    current_week = None
    if is_active:
        days_since_start = (today - training_block.start_date).days
        current_week = (days_since_start // 7) + 1
    
    # Block duration in weeks
    block_duration_days = (training_block.end_date - training_block.start_date).days
    block_duration_weeks = (block_duration_days // 7) + 1
    
    # Days to race
    days_to_race = (a_race.date - today).days
    
    context = {
        'training_block': training_block,
        'a_race': a_race,
        'sections': sections,
        'b_races': b_races,
        'activities': activities,
        'weekly_stats': weekly_stats,
        'chart_labels': chart_labels,
        'chart_distance': chart_distance,
        'chart_tss': chart_tss,
        'is_active': is_active,
        'current_week': current_week,
        'block_duration_weeks': block_duration_weeks,
        'days_to_race': days_to_race,
        'today': today,
    }
    return render(request, 'block_detail.html', context)

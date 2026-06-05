import os
import json
import sqlite3
import subprocess
import datetime
import shutil
import glob
import sys
from django.conf import settings
from django_q.tasks import async_task
from .models import RunActivity

# Paths
HEALTH_DATA_DIR = os.path.expanduser("~/HealthData")
ACTIVITIES_DIR = os.path.join(HEALTH_DATA_DIR, "FitFiles", "Activities")
STAGING_DIR = os.path.join(HEALTH_DATA_DIR, "FitFiles", "Activities_Staging")
PROCESSED_DIR = os.path.join(HEALTH_DATA_DIR, "FitFiles", "Activities_Processed")
LOCK_FILE = os.path.join(settings.BASE_DIR, 'garmin_sync.lock')


def _is_testing():
    return 'test' in sys.argv or any('test' in arg for arg in sys.argv)


def _write_lock_status(data):
    try:
        with open(LOCK_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"Error writing lock file: {e}")


def _delete_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except OSError as e:
        print(f"Error deleting lock file: {e}")


def _setup_config(garmin_user, garmin_pass):
    # Setup GarminDB config
    garmin_db_dir = os.path.expanduser("~/.GarminDb")
    os.makedirs(garmin_db_dir, exist_ok=True)
    
    config_path = os.path.join(garmin_db_dir, "GarminConnectConfig.json")
    
    # Calculate date 2 years ago
    two_years_ago = (datetime.datetime.now() - datetime.timedelta(days=2*365)).strftime("%m/%d/%Y")

    config = {
        "db": {"type": "sqlite"},
        "garmin": {"domain": "garmin.com"},
        "credentials": {
            "user": garmin_user,
            "secure_password": False,
            "password": garmin_pass,
            "password_file": None
        },
        "data": {
            "weight_start_date": two_years_ago,
            "sleep_start_date": two_years_ago,
            "rhr_start_date": two_years_ago,
            "hrv_start_date": two_years_ago,
            "monitoring_start_date": two_years_ago,
            "download_latest_activities": 25,
            "download_all_activities": 1500  # Allows enough for 2 years of daily runs
        },
        "directories": {
            "relative_to_home": True,
            "base_dir": "HealthData",
            "mount_dir": "/Volumes/GARMIN"
        },
        "enabled_stats": {
            "monitoring": False,
            "steps": False,
            "itime": False,
            "sleep": False,
            "rhr": False,
            "hrv": False,
            "weight": False,
            "activities": True
        },
        "course_views": {"steps": []},
        "modes": {},
        "activities": {"display": []},
        "settings": {
            "metric": True,
            "default_display_activities": ["running"]
        },
        "checkup": {"look_back_days": 90}
    }

    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)


def sync_garmin_data():
    """
    Background task to run GarminDB download and trigger chunked import.
    """
    garmin_user = os.environ.get("GARMIN_USERNAME")
    garmin_pass = os.environ.get("GARMIN_PASSWORD")

    if not garmin_user or not garmin_pass:
        print("Garmin credentials missing in .env")
        _delete_lock()
        return

    _setup_config(garmin_user, garmin_pass)

    python_exec = os.path.join(settings.BASE_DIR, "venv", "Scripts", "python.exe")
    garmindb_cli = os.path.join(settings.BASE_DIR, "venv", "Scripts", "garmindb_cli.py")
    sqlite_db_path = os.path.join(HEALTH_DATA_DIR, "DBs", "garmin_activities.db")
    
    # We use --all if first time, --latest if subsequent to be faster
    is_first_run = not os.path.exists(sqlite_db_path)
    
    # Prepare download directories
    os.makedirs(ACTIVITIES_DIR, exist_ok=True)
    os.makedirs(STAGING_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    cmd = [python_exec, garmindb_cli, "--download", "--all"]
    if not is_first_run:
        cmd.append("--latest")

    print(f"Starting download command: {cmd}")
    try:
        # Run download process
        subprocess.run(cmd, check=True, cwd=settings.BASE_DIR)
    except subprocess.CalledProcessError as e:
        print(f"Error downloading Garmin data: {e}")
        _write_lock_status({"status": "failed", "error": f"Download failed: {e}"})
        return

    # Move newly downloaded files to staging directory
    downloaded_files = glob.glob(os.path.join(ACTIVITIES_DIR, "*.fit"))
    print(f"Downloaded {len(downloaded_files)} FIT files.")

    for f in downloaded_files:
        filename = os.path.basename(f)
        dest = os.path.join(STAGING_DIR, filename)
        try:
            shutil.move(f, dest)
        except Exception as e:
            print(f"Error moving {filename} to staging: {e}")

    # Check staging directory for pending files
    pending_files = glob.glob(os.path.join(STAGING_DIR, "*.fit"))
    if not pending_files:
        print("No new files to process.")
        if _is_testing():
            finalize_garmin_import()
        else:
            finalize_task_id = async_task(finalize_garmin_import)
            _write_lock_status({"task_id": finalize_task_id, "status": "finalizing"})
        return

    # Calculate batches
    total_batches = (len(pending_files) + 99) // 100
    print(f"Starting batch import: {len(pending_files)} files in {total_batches} batches.")

    if _is_testing():
        for b in range(1, total_batches + 1):
            process_garmin_batch(b, total_batches)
        finalize_garmin_import()
    else:
        batch_task_id = async_task(process_garmin_batch, 1, total_batches)
        _write_lock_status({
            "task_id": batch_task_id,
            "status": "importing",
            "current_batch": 1,
            "total_batches": total_batches
        })


def process_garmin_batch(batch_number, total_batches):
    """
    Task to import a single batch of 100 FIT files.
    """
    print(f"Processing batch {batch_number}/{total_batches}...")

    # Fetch and sort files from staging directory
    pending_files = sorted(glob.glob(os.path.join(STAGING_DIR, "*.fit")))
    if not pending_files:
        print("No pending files found in staging. Finalizing.")
        if _is_testing():
            finalize_garmin_import()
        else:
            finalize_task_id = async_task(finalize_garmin_import)
            _write_lock_status({"task_id": finalize_task_id, "status": "finalizing"})
        return

    # Take up to 100 files
    batch_files = pending_files[:100]

    # Ensure ACTIVITIES_DIR is empty before moving batch files in
    for f in glob.glob(os.path.join(ACTIVITIES_DIR, "*")):
        try:
            if os.path.isfile(f):
                os.remove(f)
        except OSError as e:
            print(f"Error cleaning ACTIVITIES_DIR: {e}")

    # Move batch files to ACTIVITIES_DIR
    for f in batch_files:
        filename = os.path.basename(f)
        try:
            shutil.move(f, os.path.join(ACTIVITIES_DIR, filename))
        except Exception as e:
            print(f"Error moving {filename} to activities: {e}")

    # Run import command
    python_exec = os.path.join(settings.BASE_DIR, "venv", "Scripts", "python.exe")
    garmindb_cli = os.path.join(settings.BASE_DIR, "venv", "Scripts", "garmindb_cli.py")
    
    cmd = [python_exec, garmindb_cli, "--import", "--analyze", "--all"]
    print(f"Running import command for batch {batch_number}: {cmd}")

    try:
        subprocess.run(cmd, check=True, cwd=settings.BASE_DIR)
    except subprocess.CalledProcessError as e:
        print(f"Error importing batch {batch_number}: {e}")
        _write_lock_status({"status": "failed", "error": f"Import failed at batch {batch_number}: {e}"})
        return

    # Move batch files from ACTIVITIES_DIR to PROCESSED_DIR to keep import fast
    for f in glob.glob(os.path.join(ACTIVITIES_DIR, "*.fit")):
        filename = os.path.basename(f)
        dest = os.path.join(PROCESSED_DIR, filename)
        if os.path.exists(dest):
            try:
                os.remove(f)
            except OSError:
                pass
        else:
            try:
                shutil.move(f, dest)
            except IOError as e:
                print(f"Error moving {filename} to processed: {e}")

    # Queue next batch or finalize
    remaining_files = glob.glob(os.path.join(STAGING_DIR, "*.fit"))
    if remaining_files and batch_number < total_batches:
        next_batch = batch_number + 1
        if _is_testing():
            process_garmin_batch(next_batch, total_batches)
        else:
            batch_task_id = async_task(process_garmin_batch, next_batch, total_batches)
            _write_lock_status({
                "task_id": batch_task_id,
                "status": "importing",
                "current_batch": next_batch,
                "total_batches": total_batches
            })
    else:
        if _is_testing():
            finalize_garmin_import()
        else:
            finalize_task_id = async_task(finalize_garmin_import)
            _write_lock_status({"task_id": finalize_task_id, "status": "finalizing"})


def finalize_garmin_import():
    """
    Task to copy data from garmin.db to Django models and clean up.
    """
    print("Finalizing import: updating Django models...")
    sqlite_db_path = os.path.join(HEALTH_DATA_DIR, "DBs", "garmin_activities.db")
    try:
        _import_data(sqlite_db_path)
        print("Import completed successfully.")

        # ⚡ Bolt Optimization: Invalidate dashboard cache after new data is imported
        # Ensures users immediately see the new data instead of a stale cached view.
        from django.core.cache import cache
        cache.delete('dashboard_context')
    except Exception as e:
        print(f"Error during Django DB import: {e}")
        _write_lock_status({"status": "failed", "error": f"Finalization failed: {e}"})
        return

    # Check lock status before deleting
    try:
        with open(LOCK_FILE, 'r') as f:
            status = json.load(f)
    except Exception:
        status = {}
        
    if status.get("status") != "failed":
        _delete_lock()


def _parse_time_to_seconds(time_str):
    if not time_str:
        return 0
    parts = str(time_str).split(':')
    if len(parts) == 3:
        try:
            # Handle possible decimal seconds
            seconds = float(parts[2])
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + seconds
        except ValueError:
            return 0
    return 0


def _import_data(sqlite_db_path):
    # Now read the garmin_activities.db SQLite file and insert into Django
    print("Importing to Django models...")
    if not os.path.exists(sqlite_db_path):
        print(f"Garmin activities DB not found at {sqlite_db_path}")
        return

    conn = sqlite3.connect(sqlite_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        two_years_ago_date = (datetime.datetime.now() - datetime.timedelta(days=2*365)).date()
        two_years_ago_str = two_years_ago_date.isoformat()

        # Query all running activities in last 2 years, using sport='running' instead of type
        cursor.execute("""
            SELECT activity_id, start_time, distance, elapsed_time, moving_time, avg_speed, avg_hr, ascent
            FROM activities 
            WHERE sport = 'running' AND start_time >= ?
            ORDER BY start_time DESC
        """, (two_years_ago_str,))
        
        runs = cursor.fetchall()

        parsed_runs = []
        activity_ids = []
        
        # Load custom thresholds from env or reasonable defaults
        threshold_speed = float(os.environ.get("THRESHOLD_SPEED", 12.0))  # in km/h
        threshold_hr = float(os.environ.get("THRESHOLD_HEART_RATE", 165.0))  # in bpm

        for run in runs:
            try:
                run_date = datetime.date.fromisoformat(run['start_time'][:10])
                activity_id = str(run['activity_id'])
                
                # GarminDB stores distance in km when metric settings are enabled
                distance_km = float(run['distance']) if run['distance'] is not None else 0.0
                
                elapsed_seconds = _parse_time_to_seconds(run['elapsed_time'])
                duration_minutes = elapsed_seconds / 60.0 if elapsed_seconds else 0.0
                
                moving_seconds = _parse_time_to_seconds(run['moving_time'])
                avg_speed = float(run['avg_speed']) if run['avg_speed'] is not None else 0.0
                avg_hr = float(run['avg_hr']) if run['avg_hr'] is not None else 0.0

                # Compute TSS based on standard formula (duration_seconds * IF^2) / 3600 * 100
                speed_tss = (moving_seconds * (avg_speed / threshold_speed) ** 2) / 3600.0 * 100.0 if threshold_speed and avg_speed else 0.0
                hr_tss = (moving_seconds * (avg_hr / threshold_hr) ** 2) / 3600.0 * 100.0 if threshold_hr and avg_hr else 0.0

                # Use heart rate TSS primarily, fall back to speed TSS
                tss = hr_tss if hr_tss > 0 else speed_tss
                if tss == 0.0:
                    tss = None

                elevation_gain = float(run['ascent']) if 'ascent' in run.keys() and run['ascent'] is not None else None

                parsed_runs.append({
                    'activity_id': activity_id,
                    'date': run_date,
                    'distance_km': distance_km,
                    'duration_minutes': duration_minutes,
                    'tss': tss,
                    'elevation_gain': elevation_gain
                })
                activity_ids.append(activity_id)

            except Exception as e:
                print(f"Error processing run {run['activity_id']}: {e}")
                continue

        # Fetch existing records
        existing_activities = {
            activity.activity_id: activity
            for activity in RunActivity.objects.filter(activity_id__in=activity_ids)
        }

        create_list = []
        update_list = []

        for run_data in parsed_runs:
            activity_id = run_data['activity_id']
            if activity_id in existing_activities:
                # Update existing instance
                instance = existing_activities[activity_id]
                changed = False
                for field in ['date', 'distance_km', 'duration_minutes', 'tss', 'elevation_gain']:
                    if getattr(instance, field) != run_data[field]:
                        setattr(instance, field, run_data[field])
                        changed = True

                if changed:
                    update_list.append(instance)
            else:
                # Create new instance
                create_list.append(RunActivity(**run_data))

        if create_list:
            RunActivity.objects.bulk_create(create_list, batch_size=500)
        if update_list:
            RunActivity.objects.bulk_update(update_list, fields=['date', 'distance_km', 'duration_minutes', 'tss', 'elevation_gain'], batch_size=500)

    except sqlite3.OperationalError as e:
        print(f"Error querying garmin_activities.db: {e}")
    finally:
        conn.close()

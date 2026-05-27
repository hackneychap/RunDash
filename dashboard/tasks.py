import os
import json
import sqlite3
import subprocess
import datetime
from django.conf import settings
from .models import RunActivity

def sync_garmin_data():
    """
    Background task to run GarminDB sync and import the data into Django.
    """
    garmin_user = os.environ.get("GARMIN_USERNAME")
    garmin_pass = os.environ.get("GARMIN_PASSWORD")

    if not garmin_user or not garmin_pass:
        print("Garmin credentials missing in .env")
        return

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

    # Run GarminDB sync
    print("Running GarminDB sync...")
    
    python_exec = os.path.join(settings.BASE_DIR, "venv", "Scripts", "python.exe")
    garmindb_cli = os.path.join(settings.BASE_DIR, "venv", "Scripts", "garmindb_cli.py")
    
    # Check if GarminDB has ever been run (garmin.db exists)
    sqlite_db_path = os.path.join(os.path.expanduser("~/HealthData"), "garmin.db")
    if not os.path.exists(os.path.dirname(sqlite_db_path)):
        os.makedirs(os.path.dirname(sqlite_db_path), exist_ok=True)
    
    # We use --all if first time, --latest if subsequent to be faster
    is_first_run = not os.path.exists(sqlite_db_path)
    
    cmd = [python_exec, garmindb_cli, "--download", "--import", "--analyze"]
    if is_first_run:
        cmd.append("--all")
    else:
        cmd.append("--latest")

    try:
        # Run process (this may take a long time)
        subprocess.run(cmd, check=True, cwd=settings.BASE_DIR)
    except subprocess.CalledProcessError as e:
        print(f"Error running GarminDB: {e}")
        return

    # Now read the garmin.db SQLite file and insert into Django
    print("Importing to Django models...")
    if not os.path.exists(sqlite_db_path):
        print(f"Garmin DB not found at {sqlite_db_path}")
        return

    conn = sqlite3.connect(sqlite_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # The activities table usually contains start_time, distance, duration, type, etc.
    # The exact columns vary but usually it's activity_id, start_time, distance, elapsed_time, type
    try:
        cursor.execute("""
            SELECT activity_id, start_time, distance, elapsed_time, tss, ascent
            FROM activities 
            WHERE type = 'running'
            ORDER BY start_time DESC
        """)
        
        runs = cursor.fetchall()
        two_years_ago_date = (datetime.datetime.now() - datetime.timedelta(days=2*365)).date()

        parsed_runs = []
        activity_ids = []
        for run in runs:
            try:
                # GarminDB stores start_time as string like '2023-10-25 08:30:00' or similar
                date_str = run['start_time'].split(' ')[0]
                run_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # Filter to only last 2 years
                if run_date < two_years_ago_date:
                    continue

                activity_id = str(run['activity_id'])
                # GarminDB distance is usually in meters, convert to km
                distance_km = float(run['distance']) / 1000.0 if run['distance'] else 0.0
                # elapsed_time might be in seconds or hh:mm:ss, but usually seconds in FIT/DB
                try:
                    duration_minutes = float(run['elapsed_time']) / 60.0 if run['elapsed_time'] else 0.0
                except ValueError:
                    # If it's a string like '01:30:00'
                    parts = str(run['elapsed_time']).split(':')
                    if len(parts) == 3:
                        duration_minutes = int(parts[0]) * 60 + int(parts[1]) + float(parts[2]) / 60.0
                    else:
                        duration_minutes = 0.0

                tss = float(run['tss']) if run['tss'] is not None else None
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
            # batch_size optimization
            RunActivity.objects.bulk_update(update_list, fields=['date', 'distance_km', 'duration_minutes', 'tss', 'elevation_gain'], batch_size=500)

    except sqlite3.OperationalError as e:
        print(f"Error querying garmin.db: {e}")
    finally:
        conn.close()

    print("Sync complete.")


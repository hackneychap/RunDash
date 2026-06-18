from django.test import TestCase
import datetime
import os
from .models import RunActivity

class RunActivityModelTests(TestCase):
    def test_elevation_gain_field_can_be_saved(self):
        run = RunActivity.objects.create(
            activity_id="test_elevation_123",
            date=datetime.date.today(),
            distance_km=10.0,
            duration_minutes=60.0,
            elevation_gain=150.5
        )
        run.refresh_from_db()
        self.assertEqual(run.elevation_gain, 150.5)

class DashboardViewTests(TestCase):
    def test_dashboard_view_includes_elevation_data(self):
        RunActivity.objects.create(
            activity_id="test_view_1",
            date=datetime.date.today(),
            distance_km=10.0,
            duration_minutes=60.0,
            elevation_gain=150.5
        )
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('weekly_elevation', response.context)

        weekly_elevation_json = response.context['weekly_elevation']
        self.assertIn('150.5', weekly_elevation_json)

from unittest.mock import patch, MagicMock
from .tasks import sync_garmin_data

class TriggerSyncViewTests(TestCase):
    @patch('dashboard.views.async_task')
    def test_trigger_sync_view(self, mock_async_task):
        mock_async_task.return_value = 'mock-task-123'

        response = self.client.get('/trigger-sync/')

        self.assertEqual(response.status_code, 200)
        mock_async_task.assert_called_once_with(sync_garmin_data)

        self.assertIn('hx-get="/sync-status/mock-task-123/"', response.content.decode())
        self.assertIn('Syncing with Garmin', response.content.decode())

class SyncTaskTests(TestCase):
    @patch('dashboard.tasks.subprocess.run')
    @patch('dashboard.tasks.sqlite3.connect')
    def test_sync_garmin_data_imports_elevation_gain(self, mock_connect, mock_subprocess):
        # Mock environment variables
        with patch.dict('os.environ', {'GARMIN_USERNAME': 'test', 'GARMIN_PASSWORD': 'test'}):
            # Setup mock SQLite connection
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor

            # Setup mock data return
            # Columns: activity_id, start_time, distance, elapsed_time, tss, ascent
            import datetime
            # Date needs to be within last 2 years for sync task to import it
            recent_date = datetime.datetime.now() - datetime.timedelta(days=10)
            mock_row = {
                'activity_id': '12345',
                'start_time': recent_date.strftime('%Y-%m-%d %H:%M:%S'),
                'distance': 5.0,
                'elapsed_time': '00:30:00',
                'moving_time': '00:30:00',
                'avg_speed': 10.0,
                'avg_hr': 150,
                'ascent': 120.5
            }
            mock_cursor.fetchall.return_value = [mock_row]

            # Mock os.path.exists selectively for db file
            orig_exists = os.path.exists
            def side_effect(path):
                if 'garmin.db' in str(path):
                    return True
                if 'garmin_activities.db' in str(path):
                    return True
                return orig_exists(path)
            with patch('os.path.exists', side_effect=side_effect):
                sync_garmin_data()

            # Verify data was imported
            run = RunActivity.objects.get(activity_id='12345')
            self.assertEqual(run.elevation_gain, 120.5)

    @patch('builtins.print')
    @patch('dashboard.tasks.os.makedirs')
    def test_sync_garmin_data_missing_credentials(self, mock_makedirs, mock_print):
        with patch.dict('os.environ', {'GARMIN_USERNAME': '', 'GARMIN_PASSWORD': ''}):
            sync_garmin_data()

            mock_print.assert_any_call("Garmin credentials missing in .env")
            mock_makedirs.assert_not_called()
    @patch('dashboard.tasks.subprocess.run')
    def test_sync_garmin_data_handles_subprocess_error(self, mock_subprocess):
        import subprocess
        # Setup mock to raise CalledProcessError
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=['garmindb_cli.py']
        )

        with patch.dict('os.environ', {'GARMIN_USERNAME': 'test', 'GARMIN_PASSWORD': 'test'}):
            # This should catch the exception and return gracefully without crashing
            sync_garmin_data()

            # Verify the mock was actually called
            mock_subprocess.assert_called_once()

from django.test import TestCase
import datetime
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
                'distance': 5000,
                'elapsed_time': 1800,
                'tss': 45.0,
                'ascent': 120.5
            }
            mock_cursor.fetchall.return_value = [mock_row]

            # Mock os.path.exists for db file
            with patch('os.path.exists', return_value=True):
                sync_garmin_data()

            # Verify data was imported
            run = RunActivity.objects.get(activity_id='12345')
            self.assertEqual(run.elevation_gain, 120.5)

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

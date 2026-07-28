import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['DJANGO_SETTINGS_MODULE'] = 'garmin_dashboard.settings'
import django
django.setup()

from dashboard.models import RunActivity, TrainingBlock
print(f'RunActivity count: {RunActivity.objects.count()}')
print(f'Unlinked runs: {RunActivity.objects.filter(training_block__isnull=True).count()}')
print(f'TrainingBlock count: {TrainingBlock.objects.count()}')
for b in TrainingBlock.objects.all():
    print(f'  Block: {b.name} ({b.start_date} to {b.end_date})')
for r in RunActivity.objects.all()[:5]:
    print(f'  Run: {r.activity_id} date={r.date} block={r.training_block}')

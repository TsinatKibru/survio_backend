from django.core.management.base import BaseCommand
from notifications.tasks import check_pending_forms, send_due_date_alerts

class Command(BaseCommand):
    help = 'Runs periodic notification tasks (check pending forms and send due date alerts)'

    def handle(self, *args, **options):
        self.stdout.write('Checking pending forms...')
        check_pending_forms()
        self.stdout.write('Sending due date alerts...')
        send_due_date_alerts()
        self.stdout.write(self.style.SUCCESS('Successfully ran notification tasks'))

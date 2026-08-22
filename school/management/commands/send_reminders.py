from django.core.management.base import BaseCommand

from school.services import send_visit_reminders


class Command(BaseCommand):
    help = 'Send visit program reminders due tomorrow (run via scheduler/cron).'

    def handle(self, *args, **options):
        send_visit_reminders()
        self.stdout.write(self.style.SUCCESS('Visit reminders processed.'))

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.models import Aircraft, AircraftRole

User = get_user_model()


class Command(BaseCommand):
    help = 'Assign owner roles to aircraft for existing data'

    def add_arguments(self, parser):
        parser.add_argument('--user', required=True, help='Username to assign as owner')
        parser.add_argument('--all', action='store_true', dest='assign_all',
                            help='Assign to all aircraft without an owner')
        parser.add_argument('--aircraft', nargs='*', help='Specific tail numbers to assign')

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options['user'])
        except User.DoesNotExist:
            raise CommandError(f"User '{options['user']}' does not exist")

        if options['assign_all']:
            aircraft_qs = Aircraft.objects.exclude(
                roles__role='owner'
            ).distinct()
        elif options['aircraft']:
            aircraft_qs = Aircraft.objects.filter(
                tail_number__in=options['aircraft']
            ).exclude(roles__role='owner').distinct()
        else:
            raise CommandError('Specify --all or --aircraft <tail_numbers>')

        count = 0
        for aircraft in aircraft_qs:
            _, created = AircraftRole.objects.get_or_create(
                aircraft=aircraft, user=user,
                defaults={'role': 'owner'},
            )
            if created:
                count += 1
                self.stdout.write(f"  Assigned {user.username} as owner of {aircraft.tail_number}")
            else:
                self.stdout.write(f"  {user.username} already has a role on {aircraft.tail_number}, skipping")

        self.stdout.write(self.style.SUCCESS(f"Assigned ownership of {count} aircraft to {user.username}"))

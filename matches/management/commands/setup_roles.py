# operations/management/commands/setup_roles.py

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates default roles/groups for the operations system."

    def handle(self, *args, **options):
        Group.objects.get_or_create(name="Club Manager")
        Group.objects.get_or_create(name="Operations Director")
        self.stdout.write(self.style.SUCCESS("Groups created: Club Manager, Operations Director"))
from django.core.management.base import BaseCommand

from matches.models import Match
from checklists.models import CMSSubmission


class Command(BaseCommand):
    help = "Generate CMS submission records for all matches"

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        for match in Match.objects.all():
            _, created = CMSSubmission.objects.get_or_create(match=match)
            if created:
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"CMS submission generation completed. Created: {created_count}, Skipped existing: {skipped_count}"
            )
        )
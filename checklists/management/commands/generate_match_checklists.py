from django.core.management.base import BaseCommand

from matches.models import Match
from checklists.models import ChecklistTemplateItem, MatchChecklistItem


class Command(BaseCommand):
    help = "Generate checklist items for all matches from checklist templates"

    def handle(self, *args, **options):
        matches = Match.objects.all().order_by("event_date", "id")
        template_items = list(
            ChecklistTemplateItem.objects.filter(is_active=True)
            .select_related("category")
            .order_by("category__sort_order", "sort_order", "id")
        )

        created_count = 0
        skipped_count = 0

        for match in matches:
            for template_item in template_items:
                _, created = MatchChecklistItem.objects.get_or_create(
                    match=match,
                    template_item=template_item,
                    defaults={
                        "status": MatchChecklistItem.Status.NOT_STARTED,
                    },
                )

                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Checklist generation completed. Created: {created_count}, Skipped existing: {skipped_count}"
            )
        )
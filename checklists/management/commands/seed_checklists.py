from django.core.management.base import BaseCommand
from checklists.models import ChecklistCategory, ChecklistTemplateItem


DATA = [
    {
        "name": "Event Settings",
        "code": "event-settings",
        "sort_order": 1,
        "items": [
            ("Poster uploaded", True),
            ("Stadium image uploaded", True),
            ("Sponsor banner uploaded", True),
            ("Sponsors image uploaded", True),
            ("Zone selected", True),
            ("Event reminder email subject added", True),
            ("Description reviewed", True),
            ("Refund policy reviewed", True),
        ],
    },
    {
        "name": "Tickets",
        "code": "tickets",
        "sort_order": 2,
        "items": [
            ("Ticket types created", True),
            ("Ticket prices added", True),
            ("Ticket quantities added", True),
            ("Online sale dates added", True),
            ("Offline sale dates added", False),
            ("Tickets activated", True),
        ],
    },
    {
        "name": "Ticket Allocations",
        "code": "ticket-allocations",
        "sort_order": 3,
        "items": [
            ("Home allocation added", True),
            ("Away allocation added", True),
            ("Common allocation reviewed", False),
            ("Blocked allocation reviewed", False),
            ("Accessibility allocation reviewed", False),
        ],
    },
    {
        "name": "Gates & Admins",
        "code": "gates-admins",
        "sort_order": 4,
        "items": [
            ("Gates created", True),
            ("Admins assigned", True),
            ("Gate emails mapped", True),
        ],
    },
    {
        "name": "Manage Teams",
        "code": "manage-teams",
        "sort_order": 5,
        "items": [
            ("Home team confirmed", True),
            ("Away team confirmed", True),
            ("Home team channel mapped", True),
            ("Away team channel mapped", True),
            ("Common channel mapped", False),
        ],
    },
    {
        "name": "KVs",
        "code": "kvs",
        "sort_order": 6,
        "items": [
            ("KVs received from design", True),
            ("KVs uploaded to event", True),
            ("KVs reviewed on web", True),
            ("KVs reviewed on app", True),
        ],
    },
    {
        "name": "CMS Submission",
        "code": "cms-submission",
        "sort_order": 7,
        "items": [
            ("Final review completed", True),
            ("Sent to CMS", True),
            ("CMS confirmation received", True),
        ],
    },
]


class Command(BaseCommand):
    help = "Seed checklist categories and template items"

    def handle(self, *args, **options):
        for category_data in DATA:
            category, _ = ChecklistCategory.objects.update_or_create(
                code=category_data["code"],
                defaults={
                    "name": category_data["name"],
                    "sort_order": category_data["sort_order"],
                },
            )

            for index, (title, is_required) in enumerate(category_data["items"], start=1):
                ChecklistTemplateItem.objects.update_or_create(
                    category=category,
                    title=title,
                    defaults={
                        "sort_order": index,
                        "is_required": is_required,
                        "is_active": True,
                    },
                )

        self.stdout.write(self.style.SUCCESS("Checklist seed completed successfully."))
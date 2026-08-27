from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from events.models import Category, CategoryGroup, EventChecklistCategory, EventChecklistTemplateItem
from events.permissions import EVENTS_MANAGER_GROUP

GROUPS = [
    (CategoryGroup.Code.EVENTS, "الفعاليات", "Events"),
    (CategoryGroup.Code.SEASONS, "المواسم", "Seasons"),
    (CategoryGroup.Code.EXPERIENCES, "التجارب", "Experiences"),
    (CategoryGroup.Code.DINING, "المطاعم", "Dining"),
]

# (group code, name_ar, name_en) - verbatim from the user's category list.
CATEGORIES = [
    (CategoryGroup.Code.EVENTS, "الحفلات والموسيقى", "Concerts & Music"),
    (CategoryGroup.Code.EVENTS, "الرياضة والمباريات", "Sports"),
    (CategoryGroup.Code.EVENTS, "المسرح والعروض", "Theater & Shows"),
    (CategoryGroup.Code.EVENTS, "الكوميديا", "Comedy"),
    (CategoryGroup.Code.EVENTS, "المعارض", "Exhibitions"),
    (CategoryGroup.Code.EVENTS, "الفعاليات الثقافية", "Cultural Events"),
    (CategoryGroup.Code.EVENTS, "المهرجانات", "Festivals"),
    (CategoryGroup.Code.EVENTS, "الفعاليات العائلية", "Family Events"),
    (CategoryGroup.Code.EVENTS, "فعاليات الأطفال", "Kids Events"),
    (CategoryGroup.Code.EVENTS, "الترفيه المباشر", "Live Entertainment"),
    (CategoryGroup.Code.EVENTS, "الفعاليات الفنية", "Art Events"),
    (CategoryGroup.Code.EVENTS, "فعاليات الطعام والمطاعم", "Food & Dining Events"),
    (CategoryGroup.Code.EVENTS, "المغامرات والفعاليات الخارجية", "Adventure & Outdoor Events"),
    # Seasons: intentionally empty for now (Riyadh Season, Jeddah Season,
    # Diriyah Season, Gamers Season, etc. to be added later via the panel).
    (CategoryGroup.Code.EXPERIENCES, "المسرح", "Theater"),
    (CategoryGroup.Code.EXPERIENCES, "الفعاليات الموسيقية", "Music Events"),
    (CategoryGroup.Code.EXPERIENCES, "المطاعم", "Restaurants"),
    (CategoryGroup.Code.EXPERIENCES, "التجربة", "Experience"),
    (CategoryGroup.Code.EXPERIENCES, "الرياضة", "Sports"),
    (CategoryGroup.Code.EXPERIENCES, "التجزئة", "Retail"),
    (CategoryGroup.Code.EXPERIENCES, "المغامرات والأنشطة", "Activities & Adventures"),
    (CategoryGroup.Code.DINING, "المطاعم", "Restaurants"),
]

# A small, generic starting checklist config admins can expand independently
# via the Events Panel - deliberately not football's full list (drops
# football-only categories like "Manage Teams").
CHECKLIST_CATEGORIES = [
    ("Event Settings", [
        ("Poster uploaded", True),
        ("Venue image uploaded", True),
        ("Description reviewed", True),
    ]),
    ("Tickets", [
        ("Ticket types created", True),
        ("Ticket prices added", True),
        ("Online sale dates added", True),
        ("Tickets activated", True),
    ]),
    ("KVs", [
        ("KVs received from design", True),
        ("KVs uploaded to event", True),
        ("KVs reviewed on web", True),
        ("KVs reviewed on app", True),
    ]),
    ("CMS Submission", [
        ("Final review completed", True),
        ("Sent to CMS", True),
        ("CMS confirmation received", True),
    ]),
]


class Command(BaseCommand):
    help = "Seed the fixed CategoryGroups, their Categories, and a starting checklist config for the events app."

    def handle(self, *args, **options):
        _, created = Group.objects.get_or_create(name=EVENTS_MANAGER_GROUP)
        self.stdout.write(f"{'Created' if created else 'Exists'}: group role {EVENTS_MANAGER_GROUP}")

        group_objs = {}
        for i, (code, name_ar, name_en) in enumerate(GROUPS):
            group, created = CategoryGroup.objects.get_or_create(
                code=code, defaults={"name_ar": name_ar, "name_en": name_en, "sort_order": i}
            )
            group_objs[code] = group
            self.stdout.write(f"{'Created' if created else 'Exists'}: group {group.name_en}")

        for i, (code, name_ar, name_en) in enumerate(CATEGORIES):
            category, created = Category.objects.get_or_create(
                group=group_objs[code],
                name_en=name_en,
                defaults={"name_ar": name_ar, "sort_order": i},
            )
            self.stdout.write(f"{'Created' if created else 'Exists'}: category {category.name_en} ({category.group.name_en})")

        for cat_i, (cat_name, items) in enumerate(CHECKLIST_CATEGORIES):
            checklist_category, created = EventChecklistCategory.objects.get_or_create(
                name=cat_name, defaults={"sort_order": cat_i}
            )
            self.stdout.write(f"{'Created' if created else 'Exists'}: checklist category {checklist_category.name}")
            for item_i, (title, is_required) in enumerate(items):
                item, created = EventChecklistTemplateItem.objects.get_or_create(
                    category=checklist_category,
                    title=title,
                    defaults={"sort_order": item_i, "is_required": is_required},
                )
                self.stdout.write(f"  {'Created' if created else 'Exists'}: item {item.title}")

        self.stdout.write(self.style.SUCCESS("Done seeding event categories and checklist config."))

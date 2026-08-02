# matches/migrations/00XX_assign_club_owners.py

from django.conf import settings
from django.db import migrations


CLUB_OWNERS = {
    "Al Ahli": "mohamed.idris",
    "Al Ittihad": "mohamed.idris",
    "NEOM SC": "mohamed.idris",
    "Al Qadsiah": "mohamed.idris",
    "Al Khaleej": "mohamed.idris",

    "Al Nasr": "osama",
    "Diriyah": "osama",
    "Al Shabab": "osama",
    "Al Riyadh": "osama",
    "Abha": "osama",

    "Al Ettifaq": "mohamed.gamal",
    "Al Fateh": "mohamed.gamal",
    "Al Kholood": "mohamed.gamal",
    "Al Taawoun": "mohamed.gamal",
    "Al Hazem": "mohamed.gamal",
    "Al Fayha": "mohamed.gamal",
    "Al-Faisaly": "mohamed.gamal",
}


def assign_owners(apps, schema_editor):
    Club = apps.get_model("matches", "Club")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    for club_name_en, username in CLUB_OWNERS.items():
        try:
            club = Club.objects.get(name_en=club_name_en)
        except Club.DoesNotExist:
            continue

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            continue

        club.owner = user
        club.save(update_fields=["owner"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("matches", "0003_club_owner"),
    ]

    operations = [
        migrations.RunPython(assign_owners, reverse_noop),
    ]
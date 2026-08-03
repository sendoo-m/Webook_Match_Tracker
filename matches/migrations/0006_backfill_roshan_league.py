# matches/migrations/0006_backfill_roshan_league.py

from django.db import migrations

ROSHAN_LEAGUE_NAME_AR = "دوري روشن للمحترفين"
ROSHAN_LEAGUE_NAME_EN = "Roshan League"


def backfill_roshan_league(apps, schema_editor):
    Competition = apps.get_model("matches", "Competition")
    Match = apps.get_model("matches", "Match")
    Club = apps.get_model("matches", "Club")
    UserCompetitionAccess = apps.get_model("matches", "UserCompetitionAccess")

    roshan_league, _ = Competition.objects.get_or_create(
        name_en=ROSHAN_LEAGUE_NAME_EN,
        defaults={"name_ar": ROSHAN_LEAGUE_NAME_AR, "sort_order": 0},
    )

    Match.objects.filter(competition__isnull=True).update(competition_id=roshan_league.id)

    owner_ids = (
        Club.objects.filter(owner__isnull=False)
        .values_list("owner_id", flat=True)
        .distinct()
    )
    for owner_id in owner_ids:
        UserCompetitionAccess.objects.get_or_create(
            user_id=owner_id,
            competition_id=roshan_league.id,
        )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("matches", "0005_competition_and_access"),
    ]

    operations = [
        migrations.RunPython(backfill_roshan_league, reverse_noop),
    ]

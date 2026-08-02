from operations.permissions import get_visible_matches


class MatchScopedQuerysetMixin:
    def get_visible_matches(self, queryset=None):
        if queryset is None:
            from matches.models import Match
            queryset = Match.objects.all()
        return get_visible_matches(self.request.user, queryset)

    def filter_matches_queryset(self, queryset):
        return self.get_visible_matches(queryset)
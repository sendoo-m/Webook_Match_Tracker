# operations/views/manager_overview.py

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

User = get_user_model()


class ManagerOverviewView(LoginRequiredMixin, TemplateView):
    template_name = "operations/overview/manager_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        managers = (
            User.objects.filter(groups__name="Club Manager")
            .prefetch_related("owned_clubs")
            .distinct()
        )

        rows = [
            {
                "manager": manager,
                "clubs": manager.owned_clubs.filter(is_active=True),
                "clubs_count": manager.owned_clubs.filter(is_active=True).count(),
            }
            for manager in managers
        ]

        context["manager_rows"] = rows
        return context
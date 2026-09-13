# Suggested location: operations/auth_views.py (or wherever you keep custom
# auth views). Wire it up in config/urls.py in place of the stock
# auth_views.LoginView — see the updated urls.py snippet below.

from django.contrib.auth.views import LoginView
from django.http import HttpResponse


class HtmxLoginView(LoginView):
    """
    Same LoginView behavior, with two htmx-aware additions:

    1. On an invalid form (wrong credentials), an htmx request gets back
       just the login card partial instead of the full page — same
       pattern as OperationsDashboardView.get_template_names.
    2. On a valid form, an htmx request gets a 204 response with an
       HX-Redirect header instead of a normal 302, so htmx does a full
       browser navigation to the dashboard rather than trying to swap
       a redirected page's HTML into #login-card.
    """

    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def is_htmx(self):
        return self.request.headers.get("HX-Request") == "true"

    def get_template_names(self):
        if self.is_htmx():
            return ["registration/_login_card.html"]
        return [self.template_name]

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.is_htmx():
            htmx_response = HttpResponse(status=204)
            htmx_response["HX-Redirect"] = response.url
            return htmx_response
        return response

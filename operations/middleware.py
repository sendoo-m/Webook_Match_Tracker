# operations/middleware.py

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect

DEFAULT_MESSAGE = "معندكش صلاحية تعمل الحاجة دي — حسابك للعرض بس."


class FriendlyPermissionDeniedMiddleware:
    """
    يمسك أي PermissionDenied حصل في أي view في المشروع (زي require_match_access
    في operations/permissions.py أو ControlPanelAccessMixin في control_panel)
    ويحوّله لتجربة لطيفة بدل شاشة 403 الافتراضية بتاعة Django:

    - لو الطلب HTMX (checklist toggle, send-to-cms partial update...): بيرجع
      شريحة HTML صغيرة برسالة تحذير، تتحط مكان الاستجابة المتوقعة، من غير ما
      تكسر الصفحة.
    - لو الطلب عادي (POST فورم، أو فتح رابط مباشر زي /control-panel/):
      بيرجّع المستخدم لنفس الصفحة اللي كان فيها (أو للداشبورد لو مفيش) مع
      رسالة عبر Django messages framework، اللي أصلاً بتتعرض كـ toast في
      base.html.

    التسجيل: ضيف المسار الكامل بتاعه في MIDDLEWARE في settings.py، تحت
    MessageMiddleware عشان الـ messages framework يكون جاهز وقت المعالجة.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not isinstance(exception, PermissionDenied):
            return None

        message = str(exception) or DEFAULT_MESSAGE

        if request.headers.get("HX-Request") == "true":
            html = (
                '<div class="page-toast page-toast-error" '
                'style="position:static; margin:0 0 var(--space-4);">'
                f"{message}</div>"
            )
            return HttpResponse(html, status=200)

        messages.error(request, message)
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer or "operations:dashboard")
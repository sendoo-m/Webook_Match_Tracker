from ..models import EventActivityLog


def log_event_activity(event, action, description, user=None):
    EventActivityLog.objects.create(event=event, user=user, action=action, description=description)

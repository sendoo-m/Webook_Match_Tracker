from .models import EventChecklistItem, EventChecklistTemplateItem


def attach_default_checklist_items(event):
    """Bulk-create one EventChecklistItem per active EventChecklistTemplateItem
    for a newly created Event - the events-app equivalent of
    checklists/services.py:attach_default_checklist_items, kept independent
    per the events app's own checklist settings."""
    active_templates = EventChecklistTemplateItem.objects.filter(is_active=True)
    EventChecklistItem.objects.bulk_create(
        [
            EventChecklistItem(event=event, template_item=template)
            for template in active_templates
        ]
    )

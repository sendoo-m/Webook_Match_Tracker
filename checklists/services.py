from .models import ChecklistTemplateItem, MatchChecklistItem


def attach_default_checklist_items(match):
    """Bulk-create one MatchChecklistItem per active ChecklistTemplateItem for
    a newly created Match (or Other Event, which uses the same checklist
    system) - shared by the Control Panel create view and the bulk import."""
    active_templates = ChecklistTemplateItem.objects.filter(is_active=True)
    MatchChecklistItem.objects.bulk_create(
        [
            MatchChecklistItem(match=match, template_item=template)
            for template in active_templates
        ]
    )

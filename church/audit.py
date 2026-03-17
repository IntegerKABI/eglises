from .models import AuditLog


def log_audit(*, actor, church, action, instance=None, object_type=None, object_id=None, object_repr=None, metadata=None):
    if instance is not None:
        object_type = object_type or instance.__class__.__name__
        object_id = object_id or str(getattr(instance, 'pk', '') or '')
        object_repr = object_repr or str(instance)
    AuditLog.objects.create(
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        church=church,
        action=action,
        object_type=object_type or '',
        object_id=object_id or '',
        object_repr=object_repr or '',
        metadata=metadata or {},
    )

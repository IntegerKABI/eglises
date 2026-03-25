import logging

from .models import AuditLog

logger = logging.getLogger(__name__)


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


def log_audit_safely(*, error_message: str, **kwargs):
    """Record an audit entry and keep the caller free from repetitive error handling."""
    try:
        log_audit(**kwargs)
    except Exception:
        logger.error(error_message, exc_info=True)

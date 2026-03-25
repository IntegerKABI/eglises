"""Query builders for dashboard and management views."""

from django.db.models import Q
from django.utils import timezone

from .limits import filter_messages_for_retention, get_plan_usage
from .models import ChurchInvitation, ChurchMembership, ContactMessage
from .permissions import CAP_MANAGE_CHURCH_SETTINGS, CAP_MANAGE_MESSAGES, CAP_MANAGE_MEMBERS, CAP_MANAGE_PAGES
from .http_helpers import _get_choice_param, _get_text_param, _parse_bool_param


def build_dashboard_context(*, church, user, capabilities):
    """Build the dashboard context without keeping query assembly in the view."""
    can_manage_messages = user.is_superuser or CAP_MANAGE_MESSAGES in capabilities
    can_manage_members = user.is_superuser or CAP_MANAGE_MEMBERS in capabilities
    can_manage_pages = user.is_superuser or CAP_MANAGE_PAGES in capabilities
    can_manage_church_settings = user.is_superuser or CAP_MANAGE_CHURCH_SETTINGS in capabilities

    recent_messages = (
        filter_messages_for_retention(
            church.messages.filter(status=ContactMessage.Status.NEW).select_related('assigned_to', 'responded_by'),
            church,
        )
        if can_manage_messages
        else church.messages.none()
    )
    assigned_messages = (
        filter_messages_for_retention(
            church.messages.filter(assigned_to=user).select_related('assigned_to', 'responded_by'),
            church,
        )
        if can_manage_messages
        else church.messages.none()
    )

    return {
        'church': church,
        'show_plan_summary': can_manage_church_settings,
        'show_message_overview': can_manage_messages,
        'show_member_overview': can_manage_members,
        'show_page_overview': can_manage_pages,
        'total_members': church.members.filter(is_active=True).count(),
        'total_events': church.events.filter(is_active=True).count(),
        'total_sermons': church.sermons.filter(is_active=True).count(),
        'total_pages': church.pages.filter(is_active=True).count(),
        'plan_usage': get_plan_usage(church),
        'plan_member_limit': church.get_plan_limit('members'),
        'plan_event_limit': church.get_plan_limit('events'),
        'plan_sermon_limit': church.get_plan_limit('sermons'),
        'plan_page_limit': church.get_plan_limit('pages'),
        'plan_user_limit': church.get_plan_limit('users'),
        'plan_pending_invitation_limit': church.get_plan_limit('pending_invitations'),
        'plan_storage_limit_mb': church.get_plan_limit('storage_mb'),
        'plan_message_retention_days': church.get_plan_limit('message_retention_days'),
        'plan_notification_retention_days': church.get_plan_limit('notification_retention_days'),
        'plan_member_limit_display': church.get_plan_limit('members') if church.get_plan_limit('members') is not None else 'Illimite',
        'plan_event_limit_display': church.get_plan_limit('events') if church.get_plan_limit('events') is not None else 'Illimite',
        'plan_sermon_limit_display': church.get_plan_limit('sermons') if church.get_plan_limit('sermons') is not None else 'Illimite',
        'plan_page_limit_display': church.get_plan_limit('pages') if church.get_plan_limit('pages') is not None else 'Illimite',
        'plan_user_limit_display': church.get_plan_limit('users') if church.get_plan_limit('users') is not None else 'Illimite',
        'plan_pending_invitation_limit_display': church.get_plan_limit('pending_invitations') if church.get_plan_limit('pending_invitations') is not None else 'Illimite',
        'plan_storage_limit_display': (
            f"{church.get_plan_limit('storage_mb')} Mo"
            if church.get_plan_limit('storage_mb') is not None
            else 'Illimite'
        ),
        'upcoming_events': church.events.filter(
            is_active=True,
            event_date__gte=timezone.now().date()
        )[:5],
        'recent_messages': recent_messages[:5],
        'unread_messages_count': recent_messages.count(),
        'assigned_messages_count': assigned_messages.count(),
        'recent_sermons': church.sermons.filter(is_active=True).select_related('created_by').defer('description', 'video_url', 'audio_url').order_by('-created_at')[:5],
        'recent_pages': church.pages.filter(is_active=True).select_related('created_by').defer('content').order_by('sort_order', 'title')[:5],
        'recent_members': church.members.filter(is_active=True).defer('address', 'phone').order_by('-created_at')[:5],
        'draft_page_count': church.pages.filter(is_active=True, visibility='draft').count(),
        'draft_sermon_count': church.sermons.filter(is_active=True, visibility='draft').count(),
    }


def build_manage_events_queryset(*, request, church):
    """Build the dashboard event listing queryset from request filters."""
    events = church.events.select_related('created_by').defer('description').all()
    q = _get_text_param(request, 'q', 100)
    if q:
        events = events.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(location__icontains=q)
        )
    status = _get_choice_param(request, 'status', {'active', 'inactive'})
    if status == 'active':
        events = events.filter(is_active=True)
    elif status == 'inactive':
        events = events.filter(is_active=False)
    visibility = _get_choice_param(request, 'visibility', {'public', 'private', 'draft'})
    if visibility:
        events = events.filter(visibility=visibility)
    featured = _parse_bool_param(request.GET.get('featured'))
    if featured is True:
        events = events.filter(is_featured=True)
    elif featured is False:
        events = events.filter(is_featured=False)
    when = _get_choice_param(request, 'when', {'upcoming', 'past'})
    today = timezone.now().date()
    if when == 'upcoming':
        events = events.filter(event_date__gte=today)
    elif when == 'past':
        events = events.filter(event_date__lt=today)
    return events


def build_manage_sermons_queryset(*, request, church):
    """Build the dashboard sermon listing queryset from request filters."""
    sermons = church.sermons.select_related('created_by').defer('description').all()
    q = _get_text_param(request, 'q', 100)
    if q:
        sermons = sermons.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(preacher__icontains=q) |
            Q(bible_reference__icontains=q)
        )
    status = _get_choice_param(request, 'status', {'active', 'inactive'})
    if status == 'active':
        sermons = sermons.filter(is_active=True)
    elif status == 'inactive':
        sermons = sermons.filter(is_active=False)
    visibility = _get_choice_param(request, 'visibility', {'public', 'private', 'draft'})
    if visibility:
        sermons = sermons.filter(visibility=visibility)
    featured = _parse_bool_param(request.GET.get('featured'))
    if featured is True:
        sermons = sermons.filter(is_featured=True)
    elif featured is False:
        sermons = sermons.filter(is_featured=False)
    return sermons


def build_manage_members_queryset(*, request, church):
    """Build the dashboard member listing queryset from request filters."""
    members = church.members.defer('address').all()
    q = _get_text_param(request, 'q', 100)
    if q:
        members = members.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q)
        )
    status = _get_choice_param(request, 'status', {'active', 'inactive'})
    if status == 'active':
        members = members.filter(is_active=True)
    elif status == 'inactive':
        members = members.filter(is_active=False)
    gender = _get_choice_param(request, 'gender', {'M', 'F'})
    if gender in ('M', 'F'):
        members = members.filter(gender=gender)
    department = _get_text_param(request, 'department', 100)
    if department:
        members = members.filter(department__icontains=department)
    consent = _get_choice_param(request, 'consent', {'yes', 'no'})
    if consent == 'yes':
        members = members.filter(directory_consent=True)
    elif consent == 'no':
        members = members.filter(directory_consent=False)
    return members


def build_manage_pages_queryset(*, request, church):
    """Build the dashboard page listing queryset from request filters."""
    pages = church.pages.select_related('created_by').defer('content').all()
    q = _get_text_param(request, 'q', 100)
    if q:
        pages = pages.filter(
            Q(title__icontains=q) |
            Q(slug__icontains=q)
        )
    status = _get_choice_param(request, 'status', {'active', 'inactive'})
    if status == 'active':
        pages = pages.filter(is_active=True)
    elif status == 'inactive':
        pages = pages.filter(is_active=False)
    visibility = _get_choice_param(request, 'visibility', {'public', 'private', 'draft'})
    if visibility:
        pages = pages.filter(visibility=visibility)
    in_menu = _parse_bool_param(request.GET.get('in_menu'))
    if in_menu is True:
        pages = pages.filter(is_in_menu=True)
    elif in_menu is False:
        pages = pages.filter(is_in_menu=False)
    return pages


def build_manage_messages_queryset(*, request, church):
    """Build the dashboard message listing queryset from request filters."""
    contact_messages = filter_messages_for_retention(
        church.messages.select_related('assigned_to'),
        church,
    )
    q = _get_text_param(request, 'q', 200)
    if q:
        contact_messages = contact_messages.filter(
            Q(sender_name__icontains=q) |
            Q(sender_email__icontains=q) |
            Q(subject__icontains=q) |
            Q(message__icontains=q)
        )
    status = _get_choice_param(request, 'status', {c for c, _ in ContactMessage.Status.choices})
    if status:
        contact_messages = contact_messages.filter(status=status)
    assigned = _get_choice_param(request, 'assigned', {'me', 'unassigned'})
    if assigned == 'me':
        contact_messages = contact_messages.filter(assigned_to=request.user)
    elif assigned == 'unassigned':
        contact_messages = contact_messages.filter(assigned_to__isnull=True)
    return contact_messages


def build_manage_users_querysets(*, request, church):
    """Build the dashboard user listing querysets from request filters."""
    memberships = ChurchMembership.objects.filter(church=church).select_related('user')
    pending_invites = ChurchInvitation.objects.actionable().filter(
        church=church,
    ).select_related('invited_by', 'accepted_by').order_by('-created_at')
    q = _get_text_param(request, 'q', 100)
    if q:
        memberships = memberships.filter(
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q)
        )
    role = _get_choice_param(request, 'role', {r for r, _ in ChurchMembership.Role.choices})
    if role:
        memberships = memberships.filter(role=role)
    status = _get_choice_param(request, 'status', {'active', 'inactive'})
    if status == 'active':
        memberships = memberships.filter(is_active=True)
    elif status == 'inactive':
        memberships = memberships.filter(is_active=False)
    return memberships, pending_invites

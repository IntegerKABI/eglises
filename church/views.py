"""
=================================================================
VUES — Logique de chaque page
=================================================================
Chaque fonction ici correspond à une page du site.

COMMENT ÇA MARCHE :
1. L'utilisateur tape une URL (ex: /eglise/demo/)
2. Django cherche quelle vue correspond à cette URL (dans urls.py)
3. La vue récupère les données depuis la base de données
4. La vue envoie ces données à un template HTML
5. Le template génère la page HTML finale

Il y a 2 sections :
- VUES PUBLIQUES : ce que les visiteurs voient
- VUES DASHBOARD : l'interface d'administration pour le pasteur
=================================================================
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import Church, Event, Sermon, Member, Page, ContactMessage, SiteSettings
from .forms import ChurchForm, EventForm, SermonForm, MemberForm, PageForm, ContactForm, SiteSettingsForm
from .tenancy import get_accessible_churches, get_selected_church


def is_ajax(request):
    """Vérifie si la requête est AJAX."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _querystring_without_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


def _parse_bool_param(value):
    if value in ('1', 'true', 'yes', 'on'):
        return True
    if value in ('0', 'false', 'no', 'off'):
        return False
    return None


def _get_text_param(request, key, max_len=200):
    value = request.GET.get(key, '')
    if value is None:
        return ''
    value = value.strip()
    if len(value) > max_len:
        value = value[:max_len]
    return value


def _get_choice_param(request, key, allowed):
    value = request.GET.get(key)
    return value if value in allowed else ''


def _require_church(request):
    church = get_selected_church(request)
    if not church:
        messages.warning(request, "Sélectionnez une église pour continuer.")
    return church


# =============================================================
#  VUES PUBLIQUES — Site visible par tous
# =============================================================

def home(request):
    """Page d'accueil — liste toutes les églises disponibles."""
    churches = Church.objects.filter(is_active=True)
    q = _get_text_param(request, 'q', 100)
    if q:
        churches = churches.filter(
            Q(name__icontains=q) |
            Q(city__icontains=q) |
            Q(country__icontains=q)
        )
    paginator = Paginator(churches, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'church/home.html', {
        'churches': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


def church_home(request, church_slug):
    """
    Page d'accueil d'une église spécifique.
    Ex: /eglise/demo/ → affiche l'église avec le slug "demo"
    """
    church = get_object_or_404(Church, slug=church_slug, is_active=True)
    upcoming_events = church.events.filter(
        is_active=True,
        event_date__gte=timezone.now().date()
    )[:3]
    latest_sermons = church.sermons.filter(is_active=True)[:3]
    custom_pages = church.pages.filter(is_active=True, is_in_menu=True)

    return render(request, 'church/church_home.html', {
        'church': church,
        'upcoming_events': upcoming_events,
        'latest_sermons': latest_sermons,
        'custom_pages': custom_pages,
    })


def church_events(request, church_slug):
    """Liste de tous les événements d'une église."""
    church = get_object_or_404(Church, slug=church_slug, is_active=True)
    events = church.events.filter(is_active=True)
    q = _get_text_param(request, 'q', 100)
    if q:
        events = events.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(location__icontains=q)
        )
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
    paginator = Paginator(events, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'church/events.html', {
        'church': church,
        'events': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


def church_sermons(request, church_slug):
    """Liste de toutes les prédications d'une église."""
    church = get_object_or_404(Church, slug=church_slug, is_active=True)
    sermons = church.sermons.filter(is_active=True)
    q = _get_text_param(request, 'q', 100)
    if q:
        sermons = sermons.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(preacher__icontains=q) |
            Q(bible_reference__icontains=q)
        )
    featured = _parse_bool_param(request.GET.get('featured'))
    if featured is True:
        sermons = sermons.filter(is_featured=True)
    elif featured is False:
        sermons = sermons.filter(is_featured=False)
    paginator = Paginator(sermons, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'church/sermons.html', {
        'church': church,
        'sermons': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


def church_page(request, church_slug, page_slug):
    """Affiche une page dynamique personnalisée."""
    church = get_object_or_404(Church, slug=church_slug, is_active=True)
    page = get_object_or_404(Page, church=church, slug=page_slug, is_active=True)
    return render(request, 'church/custom_page.html', {
        'church': church,
        'page': page,
    })


def church_contact(request, church_slug):
    """Formulaire de contact d'une église."""
    church = get_object_or_404(Church, slug=church_slug, is_active=True)

    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.church = church
            message.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Votre message a été envoyé avec succès !'})
            messages.success(request, 'Votre message a été envoyé avec succès !')
            return redirect('church_contact', church_slug=church_slug)
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = ContactForm()

    return render(request, 'church/contact.html', {
        'church': church,
        'form': form,
    })


@login_required
def select_church(request):
    churches = get_accessible_churches(request.user)
    if not churches.exists():
        messages.warning(request, "Aucune église associée à votre compte.")
        return redirect('home')

    if churches.count() == 1:
        church = churches.first()
        request.session['active_church_id'] = church.id
        return redirect('dashboard')

    if request.method == 'POST':
        church_id = request.POST.get('church_id')
        church = churches.filter(id=church_id).first()
        if not church:
            messages.error(request, "Sélection d'église invalide.")
        else:
            request.session['active_church_id'] = church.id
            return redirect('dashboard')

    return render(request, 'admin_dashboard/select_church.html', {
        'churches': churches,
    })


# =============================================================
#  VUES DASHBOARD — Interface d'administration (pasteur/admin)
# =============================================================

@login_required
def dashboard(request):
    """
    Tableau de bord principal.
    Affiche les statistiques de l'église de l'utilisateur connecté.
    """
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    context = {
        'church': church,
        'total_members': church.members.filter(is_active=True).count(),
        'total_events': church.events.filter(is_active=True).count(),
        'total_sermons': church.sermons.filter(is_active=True).count(),
        'upcoming_events': church.events.filter(
            is_active=True,
            event_date__gte=timezone.now().date()
        )[:5],
        'recent_messages': church.messages.filter(is_read=False)[:5],
        'unread_messages_count': church.messages.filter(is_read=False).count(),
    }
    return render(request, 'admin_dashboard/dashboard.html', context)


@login_required
def church_settings(request):
    """Paramètres de l'église (nom, logo, couleurs, etc.)."""
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    if request.method == 'POST':
        form = ChurchForm(request.POST, request.FILES, instance=church)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Paramètres mis à jour avec succès !'})
            messages.success(request, 'Paramètres mis à jour avec succès !')
            return redirect('church_settings')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = ChurchForm(instance=church)

    return render(request, 'admin_dashboard/church_settings.html', {
        'church': church,
        'form': form,
    })


# --- CRUD Événements ---

@login_required
def manage_events(request):
    """Liste des événements (dashboard)."""
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    events = church.events.all()
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
    paginator = Paginator(events, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_events.html', {
        'church': church,
        'events': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
def add_event(request):
    """Ajouter un événement."""
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.church = church
            event.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Événement ajouté !', 'redirect': reverse('manage_events')})
            messages.success(request, 'Événement ajouté !')
            return redirect('manage_events')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = EventForm()

    return render(request, 'admin_dashboard/event_form.html', {
        'church': church,
        'form': form,
        'title': 'Ajouter un événement',
    })


@login_required
def edit_event(request, pk):
    """Modifier un événement."""
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    event = get_object_or_404(Event, pk=pk, church=church)

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Événement modifié !', 'redirect': reverse('manage_events')})
            messages.success(request, 'Événement modifié !')
            return redirect('manage_events')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = EventForm(instance=event)

    return render(request, 'admin_dashboard/event_form.html', {
        'church': church,
        'form': form,
        'title': 'Modifier l\'événement',
    })


@login_required
def delete_event(request, pk):
    """Supprimer un événement."""
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    event = get_object_or_404(Event, pk=pk, church=church)
    if request.method == 'POST':
        event.delete()
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': 'Événement supprimé !'})
        messages.success(request, 'Événement supprimé !')
    return redirect('manage_events')


# --- CRUD Prédications ---

@login_required
def manage_sermons(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    sermons = church.sermons.all()
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
    featured = _parse_bool_param(request.GET.get('featured'))
    if featured is True:
        sermons = sermons.filter(is_featured=True)
    elif featured is False:
        sermons = sermons.filter(is_featured=False)
    paginator = Paginator(sermons, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_sermons.html', {
        'church': church,
        'sermons': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
def add_sermon(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    if request.method == 'POST':
        form = SermonForm(request.POST, request.FILES)
        if form.is_valid():
            sermon = form.save(commit=False)
            sermon.church = church
            sermon.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Prédication ajoutée !', 'redirect': reverse('manage_sermons')})
            messages.success(request, 'Prédication ajoutée !')
            return redirect('manage_sermons')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = SermonForm()

    return render(request, 'admin_dashboard/sermon_form.html', {
        'church': church,
        'form': form,
        'title': 'Ajouter une prédication',
    })


@login_required
def edit_sermon(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    sermon = get_object_or_404(Sermon, pk=pk, church=church)

    if request.method == 'POST':
        form = SermonForm(request.POST, request.FILES, instance=sermon)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Prédication modifiée !', 'redirect': reverse('manage_sermons')})
            messages.success(request, 'Prédication modifiée !')
            return redirect('manage_sermons')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = SermonForm(instance=sermon)

    return render(request, 'admin_dashboard/sermon_form.html', {
        'church': church,
        'form': form,
        'title': 'Modifier la prédication',
    })


@login_required
def delete_sermon(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    sermon = get_object_or_404(Sermon, pk=pk, church=church)
    if request.method == 'POST':
        sermon.delete()
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': 'Prédication supprimée !'})
        messages.success(request, 'Prédication supprimée !')
    return redirect('manage_sermons')


# --- CRUD Membres ---

@login_required
def manage_members(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    members = church.members.all()
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
    paginator = Paginator(members, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_members.html', {
        'church': church,
        'members': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
def add_member(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    if request.method == 'POST':
        form = MemberForm(request.POST, request.FILES)
        if form.is_valid():
            member = form.save(commit=False)
            member.church = church
            member.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Membre ajouté !', 'redirect': reverse('manage_members')})
            messages.success(request, 'Membre ajouté !')
            return redirect('manage_members')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = MemberForm()

    return render(request, 'admin_dashboard/member_form.html', {
        'church': church,
        'form': form,
        'title': 'Ajouter un membre',
    })


@login_required
def edit_member(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    member = get_object_or_404(Member, pk=pk, church=church)

    if request.method == 'POST':
        form = MemberForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Membre modifié !', 'redirect': reverse('manage_members')})
            messages.success(request, 'Membre modifié !')
            return redirect('manage_members')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = MemberForm(instance=member)

    return render(request, 'admin_dashboard/member_form.html', {
        'church': church,
        'form': form,
        'title': 'Modifier le membre',
    })


@login_required
def delete_member(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    member = get_object_or_404(Member, pk=pk, church=church)
    if request.method == 'POST':
        member.delete()
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': 'Membre supprimé !'})
        messages.success(request, 'Membre supprimé !')
    return redirect('manage_members')


# --- CRUD Pages ---

@login_required
def manage_pages(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    pages = church.pages.all()
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
    in_menu = _parse_bool_param(request.GET.get('in_menu'))
    if in_menu is True:
        pages = pages.filter(is_in_menu=True)
    elif in_menu is False:
        pages = pages.filter(is_in_menu=False)
    paginator = Paginator(pages, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_pages.html', {
        'church': church,
        'pages': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
def add_page(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')

    if request.method == 'POST':
        form = PageForm(request.POST, request.FILES)
        if form.is_valid():
            page = form.save(commit=False)
            page.church = church
            page.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Page ajoutÃ©e !', 'redirect': reverse('manage_pages')})
            messages.success(request, 'Page ajoutÃ©e !')
            return redirect('manage_pages')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = PageForm()

    return render(request, 'admin_dashboard/page_form.html', {
        'church': church,
        'form': form,
        'title': 'Ajouter une page',
    })


@login_required
def edit_page(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    page = get_object_or_404(Page, pk=pk, church=church)

    if request.method == 'POST':
        form = PageForm(request.POST, request.FILES, instance=page)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Page modifiÃ©e !', 'redirect': reverse('manage_pages')})
            messages.success(request, 'Page modifiÃ©e !')
            return redirect('manage_pages')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = PageForm(instance=page)

    return render(request, 'admin_dashboard/page_form.html', {
        'church': church,
        'form': form,
        'title': 'Modifier la page',
        'page': page,
    })


@login_required
def delete_page(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    page = get_object_or_404(Page, pk=pk, church=church)
    if request.method == 'POST':
        page.delete()
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': 'Page supprimÃ©e !'})
        messages.success(request, 'Page supprimÃ©e !')
    return redirect('manage_pages')


# --- Messages de contact ---

@login_required
def manage_messages(request):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    contact_messages = church.messages.all()
    q = _get_text_param(request, 'q', 200)
    if q:
        contact_messages = contact_messages.filter(
            Q(sender_name__icontains=q) |
            Q(sender_email__icontains=q) |
            Q(subject__icontains=q) |
            Q(message__icontains=q)
        )
    read = _get_choice_param(request, 'read', {'read', 'unread'})
    if read == 'read':
        contact_messages = contact_messages.filter(is_read=True)
    elif read == 'unread':
        contact_messages = contact_messages.filter(is_read=False)
    paginator = Paginator(contact_messages, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_messages.html', {
        'church': church,
        'contact_messages': page_obj,
        'page_obj': page_obj,
        'querystring': _querystring_without_page(request),
    })


@login_required
def read_message(request, pk):
    church = _require_church(request)
    if not church:
        return redirect('select_church')
    msg = get_object_or_404(ContactMessage, pk=pk, church=church)
    if request.method == 'POST':
        if not msg.is_read:
            msg.is_read = True
            msg.save(update_fields=['is_read'])
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': 'Message marquÃ© comme lu.'})
        messages.success(request, 'Message marquÃ© comme lu.')
        return redirect('read_message', pk=pk)
    return render(request, 'admin_dashboard/read_message.html', {
        'church': church,
        'msg': msg,
    })


# --- Paramètres globaux (super-admin uniquement) ---

@login_required
def site_settings(request):
    """Paramètres globaux de la plateforme (nom, slogan, etc.)."""
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé au super-administrateur.")
        return redirect('dashboard')

    settings_obj = SiteSettings.get()
    church = get_selected_church(request)

    if request.method == 'POST':
        form = SiteSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Paramètres de la plateforme mis à jour !'})
            messages.success(request, 'Paramètres de la plateforme mis à jour !')
            return redirect('site_settings')
        elif is_ajax(request):
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = SiteSettingsForm(instance=settings_obj)

    return render(request, 'admin_dashboard/site_settings.html', {
        'church': church,
        'form': form,
        'site_settings': settings_obj,
    })

/* =================================================================
   APP.JS — Skeleton loading + AJAX forms
   ================================================================= */

document.addEventListener('DOMContentLoaded', () => {
    initSkeleton();
    initAjaxForms();
    initAjaxDeleteForms();
});

/* ===== SKELETON MANAGEMENT ===== */
function initSkeleton() {
    // Petit délai pour l'effet visuel du skeleton
    setTimeout(() => {
        document.querySelectorAll('.skeleton-container').forEach(el => {
            el.classList.add('skeleton-hidden');
        });
        document.querySelectorAll('.page-content').forEach(el => {
            el.classList.add('content-loaded');
        });
    }, 400);
}

/* ===== TOAST NOTIFICATIONS ===== */
function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container-custom';
        document.body.appendChild(container);
    }

    const icons = {
        success: 'bi-check-circle-fill',
        error: 'bi-exclamation-triangle-fill',
        warning: 'bi-exclamation-circle-fill',
        info: 'bi-info-circle-fill',
    };

    const toast = document.createElement('div');
    toast.className = `toast-custom toast-${type}`;
    toast.innerHTML = `<i class="bi ${icons[type] || icons.info}"></i> ${message}`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-out');
        toast.addEventListener('animationend', () => toast.remove());
    }, 3500);
}

/* ===== AJAX FORM SUBMISSIONS ===== */
function initAjaxForms() {
    document.querySelectorAll('form[data-ajax]').forEach(form => {
        form.addEventListener('submit', handleAjaxSubmit);
    });
}

function handleAjaxSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const formCard = form.closest('.card-body') || form;

    // État loading
    if (submitBtn) {
        submitBtn.classList.add('btn-loading');
        submitBtn.innerHTML = `<span class="btn-text">${submitBtn.innerHTML}</span>`;
    }
    formCard.classList.add('form-loading');

    // Nettoyer les erreurs précédentes
    form.querySelectorAll('.invalid-feedback, .ajax-error').forEach(el => el.remove());
    form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

    const formData = new FormData(form);

    fetch(form.action || window.location.href, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            if (data.redirect) {
                setTimeout(() => { window.location.href = data.redirect; }, 600);
            }
            // Réinitialiser le formulaire si pas de redirection (ex: contact)
            if (!data.redirect && form.dataset.ajaxReset !== 'false') {
                form.reset();
            }
        } else {
            showToast(data.message || 'Veuillez corriger les erreurs.', 'error');
            // Afficher les erreurs de champ
            if (data.errors) {
                displayFormErrors(form, data.errors);
            }
        }
    })
    .catch(() => {
        showToast('Une erreur réseau est survenue.', 'error');
    })
    .finally(() => {
        formCard.classList.remove('form-loading');
        if (submitBtn) {
            submitBtn.classList.remove('btn-loading');
            const btnText = submitBtn.querySelector('.btn-text');
            if (btnText) submitBtn.innerHTML = btnText.innerHTML;
        }
    });
}

function displayFormErrors(form, errors) {
    for (const [field, msgs] of Object.entries(errors)) {
        if (field === '__all__') {
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-danger ajax-error';
            alertDiv.textContent = msgs.join(' ');
            form.prepend(alertDiv);
            continue;
        }
        const input = form.querySelector(`[name="${field}"]`);
        if (input) {
            input.classList.add('is-invalid');
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback ajax-error';
            feedback.textContent = Array.isArray(msgs) ? msgs.join(' ') : msgs;
            input.parentNode.appendChild(feedback);
        }
    }
}

/* ===== AJAX DELETE ===== */
function initAjaxDeleteForms() {
    document.querySelectorAll('form[data-ajax-delete]').forEach(form => {
        form.addEventListener('submit', handleAjaxDelete);
    });
}

function handleAjaxDelete(e) {
    e.preventDefault();
    const form = e.target;
    const confirmMsg = form.dataset.confirmMessage || 'Êtes-vous sûr de vouloir supprimer ?';

    if (!confirm(confirmMsg)) return;

    const row = form.closest('tr') || form.closest('.col-md-6, .col-lg-4, .col-md-4');
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.classList.add('btn-loading');

    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            if (row) {
                row.classList.add('row-removing');
                setTimeout(() => row.remove(), 400);
            }
        } else {
            showToast(data.message || 'Erreur lors de la suppression.', 'error');
        }
    })
    .catch(() => {
        showToast('Une erreur réseau est survenue.', 'error');
    })
    .finally(() => {
        if (submitBtn) submitBtn.classList.remove('btn-loading');
    });
}

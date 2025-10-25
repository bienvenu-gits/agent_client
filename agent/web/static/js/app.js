/**
 * JavaScript principal pour l'interface web de l'Agent d'Inventaire
 *
 * Ce fichier contient toutes les fonctions JavaScript communes
 * utilisées dans l'interface web de l'agent.
 */

// Configuration globale
const APP_CONFIG = {
    refreshInterval: 10000, // 10 secondes
    apiTimeout: 30000, // 30 secondes
    maxRetries: 3,
    debugMode: false
};

// État global de l'application
let appState = {
    isOnline: navigator.onLine,
    lastUpdate: null,
    activeRequests: new Set(),
    notifications: []
};

// Initialisation de l'application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

/**
 * Initialise l'application web
 */
function initializeApp() {
    console.log('🚀 Initialisation de l\'Agent d\'Inventaire');

    // Vérifier la connectivité
    setupConnectivityMonitoring();

    // Configurer les gestionnaires d'événements globaux
    setupGlobalEventHandlers();

    // Initialiser les tooltips Bootstrap
    initializeTooltips();

    // Configurer les modals Bootstrap
    initializeModals();

    // Démarrer la surveillance des erreurs
    setupErrorHandling();

    // Marquer comme initialisé
    document.body.classList.add('app-initialized');

    console.log('✅ Application initialisée avec succès');
}

/**
 * Configure la surveillance de la connectivité
 */
function setupConnectivityMonitoring() {
    window.addEventListener('online', function() {
        appState.isOnline = true;
        showNotification('Connexion rétablie', 'success');
        updateConnectivityStatus(true);
    });

    window.addEventListener('offline', function() {
        appState.isOnline = false;
        showNotification('Connexion perdue', 'warning');
        updateConnectivityStatus(false);
    });

    // Vérification périodique de la connectivité
    setInterval(checkConnectivity, 30000);
}

/**
 * Met à jour l'indicateur de connectivité
 */
function updateConnectivityStatus(isOnline) {
    const indicators = document.querySelectorAll('.connectivity-indicator');
    indicators.forEach(indicator => {
        if (isOnline) {
            indicator.className = 'connectivity-indicator text-success';
            indicator.innerHTML = '<i class="fas fa-wifi"></i>';
            indicator.title = 'En ligne';
        } else {
            indicator.className = 'connectivity-indicator text-danger';
            indicator.innerHTML = '<i class="fas fa-wifi-slash"></i>';
            indicator.title = 'Hors ligne';
        }
    });
}

/**
 * Vérifie la connectivité avec le serveur
 */
async function checkConnectivity() {
    try {
        const response = await fetch('/api/status', {
            method: 'GET',
            timeout: 5000
        });

        if (response.ok) {
            if (!appState.isOnline) {
                appState.isOnline = true;
                showNotification('Connexion au serveur rétablie', 'success');
            }
        } else {
            throw new Error('Réponse serveur invalide');
        }
    } catch (error) {
        if (appState.isOnline) {
            appState.isOnline = false;
            showNotification('Problème de connexion serveur', 'warning');
        }
    }

    updateConnectivityStatus(appState.isOnline);
}

/**
 * Configure les gestionnaires d'événements globaux
 */
function setupGlobalEventHandlers() {
    // Gestionnaire pour les raccourcis clavier
    document.addEventListener('keydown', function(event) {
        // Ctrl+R ou F5 - Actualiser les données
        if ((event.ctrlKey && event.key === 'r') || event.key === 'F5') {
            event.preventDefault();
            refreshCurrentPage();
        }

        // Échap - Fermer les modals/toasts
        if (event.key === 'Escape') {
            closeAllModals();
            closeAllToasts();
        }
    });

    // Gestionnaire pour les clics sur les liens API
    document.addEventListener('click', function(event) {
        const target = event.target.closest('[data-api-action]');
        if (target) {
            event.preventDefault();
            handleApiAction(target);
        }
    });

    // Gestionnaire pour la soumission de formulaires
    document.addEventListener('submit', function(event) {
        const form = event.target;
        if (form.classList.contains('api-form')) {
            event.preventDefault();
            handleFormSubmission(form);
        }
    });
}

/**
 * Gère les actions API depuis les attributs data
 */
async function handleApiAction(element) {
    const action = element.dataset.apiAction;
    const method = element.dataset.apiMethod || 'POST';
    const endpoint = element.dataset.apiEndpoint;

    if (!endpoint) {
        console.error('Endpoint API manquant');
        return;
    }

    // Désactiver l'élément pendant la requête
    element.disabled = true;
    const originalContent = element.innerHTML;

    if (element.dataset.loadingText) {
        element.innerHTML = element.dataset.loadingText;
    }

    try {
        const result = await makeApiCall(endpoint, method);

        if (result.success) {
            showNotification(result.message || 'Opération réussie', 'success');

            // Callback personnalisé si défini
            if (element.dataset.successCallback) {
                const callback = window[element.dataset.successCallback];
                if (typeof callback === 'function') {
                    callback(result);
                }
            }
        } else {
            showNotification(result.message || 'Opération échouée', 'error');
        }
    } catch (error) {
        showNotification('Erreur: ' + error.message, 'error');
        console.error('Erreur API:', error);
    } finally {
        element.disabled = false;
        element.innerHTML = originalContent;
    }
}

/**
 * Gère la soumission des formulaires API
 */
async function handleFormSubmission(form) {
    const formData = new FormData(form);
    const endpoint = form.action || form.dataset.apiEndpoint;
    const method = form.method || 'POST';

    // Convertir FormData en objet
    const data = {};
    for (const [key, value] of formData.entries()) {
        // Gérer les checkboxes
        if (form.querySelector(`input[name="${key}"][type="checkbox"]`)) {
            data[key] = form.querySelector(`input[name="${key}"]`).checked;
        } else {
            data[key] = value;
        }
    }

    try {
        const result = await makeApiCall(endpoint, method, data);

        if (result.success) {
            showNotification(result.message || 'Sauvegarde réussie', 'success');

            // Réinitialiser le formulaire si demandé
            if (form.dataset.resetOnSuccess === 'true') {
                form.reset();
            }
        } else {
            showNotification(result.message || 'Erreur de sauvegarde', 'error');
        }
    } catch (error) {
        showNotification('Erreur: ' + error.message, 'error');
        console.error('Erreur soumission formulaire:', error);
    }
}

/**
 * Effectue un appel API avec gestion d'erreurs améliorée
 */
async function makeApiCall(endpoint, method = 'GET', data = null, options = {}) {
    const requestId = Date.now() + Math.random();
    appState.activeRequests.add(requestId);

    try {
        const config = {
            method: method.toUpperCase(),
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            timeout: options.timeout || APP_CONFIG.apiTimeout,
            ...options
        };

        if (data && method.toUpperCase() !== 'GET') {
            config.body = JSON.stringify(data);
        }

        console.log(`📡 API ${method.toUpperCase()} ${endpoint}`, data || '');

        const response = await fetch(endpoint, config);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();

        console.log(`✅ API ${method.toUpperCase()} ${endpoint} - Succès`, result);

        return result;

    } catch (error) {
        console.error(`❌ API ${method.toUpperCase()} ${endpoint} - Erreur:`, error);

        // Gestion spécifique des erreurs
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            throw new Error('Impossible de contacter le serveur');
        } else if (error.name === 'AbortError') {
            throw new Error('Requête interrompue (timeout)');
        } else {
            throw error;
        }
    } finally {
        appState.activeRequests.delete(requestId);
    }
}

/**
 * Affiche une notification toast
 */
function showNotification(message, type = 'info', duration = 5000) {
    const notification = {
        id: Date.now(),
        message,
        type,
        timestamp: new Date()
    };

    appState.notifications.push(notification);

    // Créer l'élément toast
    const toast = createToastElement(notification);

    // Ajouter au container
    const container = document.querySelector('.toast-container') || createToastContainer();
    container.appendChild(toast);

    // Initialiser et afficher le toast Bootstrap
    const bsToast = new bootstrap.Toast(toast, {
        delay: duration
    });

    bsToast.show();

    // Nettoyer après fermeture
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
        const index = appState.notifications.findIndex(n => n.id === notification.id);
        if (index > -1) {
            appState.notifications.splice(index, 1);
        }
    });

    return notification.id;
}

/**
 * Crée un élément toast
 */
function createToastElement(notification) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.setAttribute('role', 'alert');

    const typeIcon = {
        success: 'fa-check-circle text-success',
        error: 'fa-exclamation-circle text-danger',
        warning: 'fa-exclamation-triangle text-warning',
        info: 'fa-info-circle text-info'
    };

    const icon = typeIcon[notification.type] || typeIcon.info;

    toast.innerHTML = `
        <div class="toast-header">
            <i class="fas ${icon} me-2"></i>
            <strong class="me-auto">Agent d'Inventaire</strong>
            <small class="text-muted">${formatTime(notification.timestamp)}</small>
            <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
            ${notification.message}
        </div>
    `;

    return toast;
}

/**
 * Crée le container de toasts s'il n'existe pas
 */
function createToastContainer() {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(container);
    }
    return container;
}

/**
 * Initialise les tooltips Bootstrap
 */
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Initialise les modals Bootstrap
 */
function initializeModals() {
    const modalElements = document.querySelectorAll('.modal');
    modalElements.forEach(modalElement => {
        modalElement.addEventListener('shown.bs.modal', function() {
            // Focus automatique sur le premier input
            const firstInput = modalElement.querySelector('input, textarea, select');
            if (firstInput) {
                firstInput.focus();
            }
        });
    });
}

/**
 * Configure la gestion d'erreurs globale
 */
function setupErrorHandling() {
    window.addEventListener('error', function(event) {
        console.error('Erreur JavaScript globale:', event.error);

        if (APP_CONFIG.debugMode) {
            showNotification(`Erreur: ${event.error.message}`, 'error');
        }
    });

    window.addEventListener('unhandledrejection', function(event) {
        console.error('Promise rejetée non gérée:', event.reason);

        if (APP_CONFIG.debugMode) {
            showNotification(`Erreur async: ${event.reason}`, 'error');
        }
    });
}

/**
 * Actualise la page courante
 */
function refreshCurrentPage() {
    if (typeof updateStatus === 'function') {
        updateStatus();
        showNotification('Données actualisées', 'info', 2000);
    } else {
        window.location.reload();
    }
}

/**
 * Ferme tous les modals ouverts
 */
function closeAllModals() {
    const modals = document.querySelectorAll('.modal.show');
    modals.forEach(modal => {
        const bsModal = bootstrap.Modal.getInstance(modal);
        if (bsModal) {
            bsModal.hide();
        }
    });
}

/**
 * Ferme tous les toasts ouverts
 */
function closeAllToasts() {
    const toasts = document.querySelectorAll('.toast.show');
    toasts.forEach(toast => {
        const bsToast = bootstrap.Toast.getInstance(toast);
        if (bsToast) {
            bsToast.hide();
        }
    });
}

/**
 * Formate une date/heure de manière lisible
 */
function formatTime(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }

    const now = new Date();
    const diff = now - date;

    if (diff < 60000) { // Moins d'une minute
        return 'À l\'instant';
    } else if (diff < 3600000) { // Moins d'une heure
        const minutes = Math.floor(diff / 60000);
        return `Il y a ${minutes} min`;
    } else if (diff < 86400000) { // Moins d'un jour
        const hours = Math.floor(diff / 3600000);
        return `Il y a ${hours}h`;
    } else {
        return date.toLocaleString('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

/**
 * Formate une taille en bytes
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 B';

    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];

    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Debounce une fonction
 */
function debounce(func, wait, immediate = false) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}

/**
 * Throttle une fonction
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Copie un texte dans le presse-papier
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Copié dans le presse-papier', 'success', 2000);
        return true;
    } catch (error) {
        console.error('Erreur copie presse-papier:', error);
        // Fallback pour les navigateurs plus anciens
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();

        try {
            document.execCommand('copy');
            showNotification('Copié dans le presse-papier', 'success', 2000);
            return true;
        } catch (err) {
            showNotification('Impossible de copier', 'error');
            return false;
        } finally {
            document.body.removeChild(textArea);
        }
    }
}

/**
 * Valide une URL
 */
function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
}

/**
 * Valide une adresse email
 */
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Exporte les données en JSON
 */
function exportToJson(data, filename = 'export.json') {
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });

    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(link.href);
    showNotification(`Fichier ${filename} téléchargé`, 'success');
}

/**
 * Utilitaire pour les animations CSS
 */
function animateElement(element, animationClass, duration = 1000) {
    return new Promise((resolve) => {
        element.classList.add(animationClass);

        setTimeout(() => {
            element.classList.remove(animationClass);
            resolve();
        }, duration);
    });
}

/**
 * Détecte si l'utilisateur est sur mobile
 */
function isMobile() {
    return window.innerWidth <= 768;
}

/**
 * Active/désactive le mode debug
 */
function setDebugMode(enabled) {
    APP_CONFIG.debugMode = enabled;
    localStorage.setItem('debugMode', enabled);

    if (enabled) {
        console.log('🐛 Mode debug activé');
        document.body.classList.add('debug-mode');
    } else {
        console.log('✅ Mode debug désactivé');
        document.body.classList.remove('debug-mode');
    }
}

// Charger le mode debug depuis localStorage
if (localStorage.getItem('debugMode') === 'true') {
    setDebugMode(true);
}

// Exposer les fonctions utiles globalement
window.InventoryAgent = {
    showNotification,
    makeApiCall,
    copyToClipboard,
    formatBytes,
    formatTime,
    exportToJson,
    setDebugMode,
    refreshCurrentPage
};

console.log('📋 Agent d\'Inventaire - JavaScript chargé');
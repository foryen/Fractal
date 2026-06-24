// auth-guard.js — Gestion centralisée de l'auth Firebase (version compat)
// À inclure dans toutes les pages via <script src="auth-guard.js"></script>

// Configuration Firebase (la même que login.html)
const firebaseConfig = {
  apiKey: "AIzaSyBSlXOeyDxVKUFBBkPTMbsS_oY6kADkbMg",
  authDomain: "fractal-86f1f.firebaseapp.com",
  projectId: "fractal-86f1f",
  storageBucket: "fractal-86f1f.firebasestorage.app",
  messagingSenderId: "954198010037",
  appId: "1:954198010037:web:3548437da32d3a34d7b6fc"
};

// Initialise Firebase (une seule fois)
if (!firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}
firebase.auth().languageCode = 'fr';

// État global
let currentUser = null;
let authReady = false;

/**
 * Vérifie l'état de connexion
 * @param {boolean} requireAuth - Si true, redirige vers login.html si non connecté
 * @returns {Promise<object|null>} - L'utilisateur ou null
 */
function checkAuth(requireAuth = false) {
  return new Promise((resolve) => {
    firebase.auth().onAuthStateChanged((user) => {
      currentUser = user;
      authReady = true;
      
      if (requireAuth && !user) {
        window.location.href = 'login.html';
      }
      resolve(user);
    });
  });
}

/**
 * Déconnexion
 */
async function logout() {
  await firebase.auth().signOut();
  window.location.href = 'login.html';
}

/**
 * Met à jour l'UI du header selon l'état de connexion
 * @param {string} containerId - ID du conteneur où injecter l'UI
 */
function renderAuthUI(containerId = 'auth-section') {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (currentUser) {
    const displayName = currentUser.displayName || currentUser.email.split('@')[0];
    const initial = displayName[0].toUpperCase();

    container.innerHTML = `
      <div style="display:flex;align-items:center;gap:0.5rem;">
        <a href="compte.html" class="auth-user-badge">
          <div class="auth-avatar">${initial}</div>
          <span class="auth-username">${displayName}</span>
        </a>
        <button id="logoutBtn" class="logout-btn" title="Se déconnecter">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24">
            <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12h-9.5m7.5 3 3-3-3-3m-5-2V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5a2 2 0 0 0 2-2v-1"/>
          </svg>
        </button>
      </div>
    `;

    const logoutButton = document.getElementById('logoutBtn');
    if (logoutButton) {
      logoutButton.addEventListener('click', logout);
    }
  } else {
    container.innerHTML = `
      <a href="login.html" class="btn-primary" style="padding:0.5rem 1.25rem;font-size:0.875rem;">
        Se connecter
      </a>
    `;
  }
}

// Export global
window.FractalAuth = {
  checkAuth,
  logout,
  renderAuthUI,
  getUser: () => currentUser,
  isReady: () => authReady
};
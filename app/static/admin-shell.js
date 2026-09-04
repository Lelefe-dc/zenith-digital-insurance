/* Responsive shell behaviour for the Zenith management portal. */
(function () {
  const body = document.body;
  const sidebar = document.getElementById('sidebar');
  const openBtn = document.getElementById('sidebarToggle');
  const closeBtn = document.getElementById('sidebarClose');
  const overlay = document.getElementById('sidebarOverlay');
  const nav = document.getElementById('navMenu');

  function closeSidebar() {
    body.classList.remove('sidebar-open');
    overlay?.setAttribute('aria-hidden', 'true');
  }

  function openSidebar() {
    body.classList.add('sidebar-open');
    overlay?.setAttribute('aria-hidden', 'false');
  }

  openBtn?.addEventListener('click', openSidebar);
  closeBtn?.addEventListener('click', closeSidebar);
  overlay?.addEventListener('click', closeSidebar);
  nav?.addEventListener('click', event => {
    if (event.target.closest('button[data-page]') && window.innerWidth <= 900) closeSidebar();
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 900) closeSidebar();
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeSidebar();
  });

  if (sidebar) sidebar.setAttribute('aria-label', 'Management navigation');
})();

/**
 * BugFlow Enterprise Shell — Responsive Mobile & Desktop Adaptive Navigation
 * Provides responsive drawer navigation, backdrop dismissal, touch friendly interactions,
 * and seamless adaptability between mobile phones, tablets, and desktop workstations.
 */
(function () {
  function initBugFlowResponsiveShell() {
    // 1. Identify primary sidebar & header elements
    // Prioritize fixed/sticky navigation bar; never select content cards
    const sidebar = document.querySelector(
      'aside.sidebar, aside.bf-sidebar, .sidebar, aside[class*="w-60"], aside[class*="w-64"], aside[class*="fixed"], aside'
    );
    const header = document.querySelector(
      'header.topbar, header.bf-topbar, .topbar, .bf-topbar, ' +
      'header[class*="fixed"], header[class*="sticky"], ' +
      'header:not(.page-header-card)'
    );

    if (!sidebar || !header) return;

    // 2. Ensure Mobile Backdrop exists
    let backdrop = document.getElementById('bfMobileBackdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'bfMobileBackdrop';
      backdrop.className = 'bf-mobile-backdrop';
      document.body.appendChild(backdrop);
    }

    // 3. Ensure Mobile Hamburger Toggle Button exists in header
    let menuBtn = document.getElementById('bfMobileMenuBtn');
    if (!menuBtn) {
      menuBtn = document.createElement('button');
      menuBtn.id = 'bfMobileMenuBtn';
      menuBtn.type = 'button';
      menuBtn.className = 'bf-mobile-menu-btn';
      menuBtn.setAttribute('aria-label', 'Toggle Mobile Navigation');
      menuBtn.title = 'Navigation Menu';
      menuBtn.innerHTML = `
        <svg class="bf-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      `;

      // Insert at the front of header or first child
      if (header.firstChild) {
        header.insertBefore(menuBtn, header.firstChild);
      } else {
        header.appendChild(menuBtn);
      }
    }

    // 4. Toggle functions
    function openSidebar() {
      sidebar.classList.add('bf-mobile-open');
      backdrop.classList.add('bf-backdrop-visible');
      document.body.classList.add('bf-nav-locked');
    }

    function closeSidebar() {
      sidebar.classList.remove('bf-mobile-open');
      backdrop.classList.remove('bf-backdrop-visible');
      document.body.classList.remove('bf-nav-locked');
    }

    function toggleSidebar(e) {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      if (sidebar.classList.contains('bf-mobile-open')) {
        closeSidebar();
      } else {
        openSidebar();
      }
    }

    menuBtn.onclick = toggleSidebar;
    backdrop.onclick = closeSidebar;

    // 5. Close sidebar on navigation item click (mobile)
    sidebar.querySelectorAll('a, button[data-role]').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 1024) {
          closeSidebar();
        }
      });
    });

    // 6. Handle viewport resize (if expanded to desktop, clean up mobile classes)
    window.addEventListener('resize', () => {
      if (window.innerWidth > 1024) {
        closeSidebar();
      }
    });

    // 7. Make all data tables horizontally scrollable if not already wrapped
    document.querySelectorAll('table').forEach(table => {
      const parent = table.parentElement;
      if (parent && !parent.classList.contains('table-responsive') && !parent.classList.contains('bf-table-container')) {
        parent.style.overflowX = 'auto';
        parent.style.webkitOverflowScrolling = 'touch';
      }
    });
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBugFlowResponsiveShell);
  } else {
    initBugFlowResponsiveShell();
  }
})();

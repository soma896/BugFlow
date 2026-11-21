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

    // 8. Initialize Notification Center
    initBugFlowNotificationCenter();
  }

  // =========================================================================
  // BUGFLOW REAL-TIME NOTIFICATION CENTER (In-App Bell, Dropdown, & Live Toast)
  // =========================================================================
  function initBugFlowNotificationCenter() {
    const path = window.location.pathname.toLowerCase();
    if (path === "/" || path === "/index.html" || path.endsWith("/login")) return;

    // Detect user role
    function getRole() {
      const stored = localStorage.getItem("bugflow_workspace_role");
      if (stored) return stored.toLowerCase().trim();
      if (path.includes("senior")) return "senior_dev";
      if (path.includes("developer")) return "developer";
      if (path.includes("tester")) return "tester";
      if (path.includes("user")) return "user";
      if (path.includes("admin")) return "admin";
      return "admin";
    }

    const currentRole = getRole();

    // 1. Inject Styles
    if (!document.getElementById("bfNotifStyles")) {
      const style = document.createElement("style");
      style.id = "bfNotifStyles";
      style.textContent = `
        .bf-notif-wrapper {
          position: relative;
          display: inline-flex;
          align-items: center;
          margin-right: 10px;
          z-index: 999;
        }
        .bf-notif-bell-btn {
          position: relative;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 38px;
          height: 38px;
          border-radius: 9px;
          border: 1px solid #e2e8f0;
          background: #ffffff;
          color: #475569;
          cursor: pointer;
          transition: all 0.18s ease;
        }
        .bf-notif-bell-btn:hover {
          background: #f8fafc;
          border-color: #cbd5e1;
          color: #2563eb;
        }
        .bf-notif-badge {
          position: absolute;
          top: -4px;
          right: -4px;
          background: #ef4444;
          color: #ffffff;
          font-size: 10px;
          font-weight: 800;
          padding: 1px 5px;
          border-radius: 10px;
          border: 2px solid #ffffff;
          min-width: 17px;
          text-align: center;
          line-height: 14px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }
        .bf-notif-dropdown {
          position: absolute;
          top: calc(100% + 8px);
          right: 0;
          width: 360px;
          max-width: 90vw;
          background: #ffffff;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1);
          z-index: 10000;
          display: none;
          flex-direction: column;
          overflow: hidden;
        }
        .bf-notif-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 16px;
          background: #f8fafc;
          border-bottom: 1px solid #e2e8f0;
        }
        .bf-notif-header-title {
          font-weight: 700;
          font-size: 14px;
          color: #0f172a;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .bf-notif-header-badge {
          font-size: 11px;
          font-weight: 600;
          background: #eff6ff;
          color: #2563eb;
          padding: 2px 7px;
          border-radius: 6px;
        }
        .bf-notif-mark-read {
          background: transparent;
          border: none;
          color: #2563eb;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
        }
        .bf-notif-mark-read:hover {
          text-decoration: underline;
        }
        .bf-notif-list {
          max-height: 380px;
          overflow-y: auto;
        }
        .bf-notif-item {
          display: flex;
          gap: 12px;
          padding: 12px 16px;
          border-bottom: 1px solid #f1f5f9;
          cursor: pointer;
          transition: background 0.15s ease;
          text-decoration: none;
          color: inherit;
        }
        .bf-notif-item:hover {
          background: #f8fafc;
        }
        .bf-notif-item.unread {
          background: #eff6ff;
        }
        .bf-notif-item.unread:hover {
          background: #dbeafe;
        }
        .bf-notif-icon-box {
          width: 32px;
          height: 32px;
          border-radius: 8px;
          display: grid;
          place-items: center;
          flex-shrink: 0;
          font-size: 16px;
        }
        .bf-notif-icon-box.defect {
          background: #fee2e2;
          color: #dc2626;
        }
        .bf-notif-icon-box.assign {
          background: #e0e7ff;
          color: #4f46e5;
        }
        .bf-notif-item-body {
          flex: 1;
          min-width: 0;
        }
        .bf-notif-item-title {
          font-size: 13px;
          font-weight: 700;
          color: #0f172a;
          margin-bottom: 2px;
          line-height: 1.3;
        }
        .bf-notif-item-msg {
          font-size: 12px;
          color: #475569;
          line-height: 1.4;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
        .bf-notif-item-time {
          font-size: 11px;
          color: #94a3b8;
          margin-top: 4px;
        }
        .bf-notif-empty {
          padding: 32px 16px;
          text-align: center;
          color: #94a3b8;
          font-size: 13px;
        }
        /* Floating Real-Time Toast */
        .bf-notif-toast {
          position: fixed;
          top: 24px;
          right: 24px;
          background: #ffffff;
          border: 1px solid #e2e8f0;
          border-left: 4px solid #2563eb;
          border-radius: 10px;
          box-shadow: 0 10px 25px -5px rgba(0,0,0,0.15);
          padding: 12px 16px;
          display: none;
          align-items: flex-start;
          gap: 12px;
          max-width: 380px;
          z-index: 99999;
          animation: bfToastIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
          cursor: pointer;
        }
        @keyframes bfToastIn {
          from { opacity: 0; transform: translateY(-12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `;
      document.head.appendChild(style);
    }

    // 2. Find anchor container in header
    let container = document.querySelector(".top-actions");
    if (!container) container = document.querySelector(".header-right");
    if (!container) container = document.querySelector(".switcher-container");
    if (!container) container = document.querySelector(".header-actions");
    if (!container) container = document.querySelector(".topbar");
    if (!container) container = document.querySelector("header.top, header.topbar, header");
    if (!container) return;

    if (document.getElementById("bfNotifBellWrapper")) return;

    // 3. Mount Bell & Dropdown
    const wrapper = document.createElement("div");
    wrapper.id = "bfNotifBellWrapper";
    wrapper.className = "bf-notif-wrapper";
    wrapper.innerHTML = `
      <button id="bfNotifBellBtn" class="bf-notif-bell-btn" type="button" aria-label="Notifications" title="Notifications">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
        </svg>
        <span id="bfNotifBadge" class="bf-notif-badge" style="display:none;">0</span>
      </button>
      <div id="bfNotifDropdown" class="bf-notif-dropdown">
        <div class="bf-notif-header">
          <div class="bf-notif-header-title">
            <span>Notifications</span>
            <span id="bfNotifHeaderBadge" class="bf-notif-header-badge">0 new</span>
          </div>
          <button id="bfNotifMarkAllBtn" type="button" class="bf-notif-mark-read">Mark all as read</button>
        </div>
        <div id="bfNotifList" class="bf-notif-list">
          <div class="bf-notif-empty">Loading notifications...</div>
        </div>
      </div>
    `;

    // 4. Mount Floating Toast in body
    let toast = document.getElementById("bfNotifToast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "bfNotifToast";
      toast.className = "bf-notif-toast";
      toast.innerHTML = `
        <div style="font-size:20px; line-height:1;">🔔</div>
        <div style="flex:1; min-width:0;">
          <div id="bfToastTitle" style="font-weight:700; font-size:13px; color:#0f172a; margin-bottom:2px;"></div>
          <div id="bfToastMsg" style="font-size:12px; color:#475569; line-height:1.35;"></div>
        </div>
        <button id="bfToastClose" type="button" style="background:transparent; border:none; font-size:18px; color:#94a3b8; cursor:pointer; line-height:1; padding:0 4px;">&times;</button>
      `;
      document.body.appendChild(toast);
    }

    // Insert wrapper into container cleanly
    const profileWidget = container.querySelector(".user-profile-widget") || container.querySelector(".profile") || null;
    if (profileWidget) {
      container.insertBefore(wrapper, profileWidget);
    } else if (container.firstChild) {
      container.insertBefore(wrapper, container.firstChild);
    } else {
      container.appendChild(wrapper);
    }

    // 5. Logic & Polling
    const bellBtn = document.getElementById("bfNotifBellBtn");
    const dropdown = document.getElementById("bfNotifDropdown");
    const badge = document.getElementById("bfNotifBadge");
    const headerBadge = document.getElementById("bfNotifHeaderBadge");
    const notifList = document.getElementById("bfNotifList");
    const markAllBtn = document.getElementById("bfNotifMarkAllBtn");
    const toastClose = document.getElementById("bfToastClose");

    let knownNotifIds = new Set();
    let initialLoad = true;

    bellBtn.onclick = function (e) {
      e.stopPropagation();
      dropdown.style.display = dropdown.style.display === "flex" ? "none" : "flex";
    };

    document.addEventListener("click", function (e) {
      if (!wrapper.contains(e.target)) {
        dropdown.style.display = "none";
      }
    });

    if (toastClose) {
      toastClose.onclick = function (e) {
        e.stopPropagation();
        toast.style.display = "none";
      };
    }

    if (markAllBtn) {
      markAllBtn.onclick = async function () {
        try {
          await fetch("/api/v1/notifications/read", { method: "POST" });
          badge.style.display = "none";
          badge.textContent = "0";
          headerBadge.textContent = "0 new";
          document.querySelectorAll(".bf-notif-item.unread").forEach(el => el.classList.remove("unread"));
        } catch (e) {
          console.error("[BugFlow Notification] Mark read failed:", e);
        }
      };
    }

    function timeAgo(dateString) {
      const now = new Date();
      const past = new Date(dateString);
      const diffMs = now - past;
      const diffSec = Math.floor(diffMs / 1000);
      if (diffSec < 60) return "Just now";
      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) return diffMin + "m ago";
      const diffHr = Math.floor(diffMin / 60);
      if (diffHr < 24) return diffHr + "h ago";
      return Math.floor(diffHr / 24) + "d ago";
    }

    function escapeHtml(str) {
      if (!str) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    function extractDefectId(item) {
      if (item && item.defect_id) return item.defect_id;
      const text = `${item?.title || ""} ${item?.message || ""} ${item?.link || ""}`;
      const match = text.match(/#(\d+)/) || text.match(/[?&]defect_id=(\d+)/i) || text.match(/[?&]id=(\d+)/i);
      return match ? match[1] : null;
    }

    function openNotificationDefect(link, defectId) {
      const curPath = window.location.pathname.toLowerCase();
      const targetPath = (link || "").split("?")[0].toLowerCase();

      // If openDetails exists on current page AND current page is a defects page or matches destination:
      if (defectId && typeof window.openDetails === "function" && (curPath === targetPath || curPath.includes("defect") || curPath.includes("user"))) {
        if (dropdown) dropdown.style.display = "none";
        window.openDetails(defectId);
        try {
          const u = new URL(window.location.href);
          u.searchParams.set("defect_id", defectId);
          window.history.pushState({}, "", u.toString());
        } catch (e) {}
        return;
      }

      // Otherwise navigate to the target defect link (which includes ?defect_id=...)
      if (link) {
        window.location.href = link;
      } else if (defectId) {
        window.location.href = `/all-defects-ui?defect_id=${defectId}`;
      }
    }

    // Auto-open defect if ?defect_id=... is present in the URL query string
    function checkAndAutoOpenDefect() {
      const urlParams = new URLSearchParams(window.location.search);
      const targetId = urlParams.get("defect_id") || urlParams.get("id");
      if (!targetId) return;

      let attempts = 0;
      const interval = setInterval(() => {
        attempts++;
        if (typeof window.openDetails === "function") {
          window.openDetails(targetId);
          clearInterval(interval);
        } else if (attempts >= 30) {
          clearInterval(interval);
        }
      }, 150);
    }
    checkAndAutoOpenDefect();

    function showToast(item) {
      const toastTitle = document.getElementById("bfToastTitle");
      const toastMsg = document.getElementById("bfToastMsg");
      if (!toastTitle || !toastMsg) return;

      toastTitle.textContent = item.title;
      toastMsg.textContent = item.message;
      toast.style.display = "flex";

      toast.onclick = async function () {
        toast.style.display = "none";
        try {
          await fetch(`/api/v1/notifications/read?notification_id=${item.id}`, { method: "POST" });
        } catch (e) {}
        const defectId = extractDefectId(item);
        openNotificationDefect(item.link, defectId);
      };

      setTimeout(() => {
        toast.style.display = "none";
      }, 7000);
    }

    async function fetchNotifications() {
      try {
        const res = await fetch(`/api/v1/notifications?role=${encodeURIComponent(currentRole)}&limit=15`);
        if (!res.ok) return;
        const data = await res.json();
        const unread = data.unread_count || 0;
        const items = data.items || [];

        // Badge display
        if (unread > 0) {
          badge.textContent = unread > 99 ? "99+" : unread;
          badge.style.display = "block";
          headerBadge.textContent = `${unread} new`;
        } else {
          badge.style.display = "none";
          headerBadge.textContent = "0 new";
        }

        // Check for new items to show floating toast
        if (!initialLoad && items.length > 0) {
          for (const item of items) {
            if (!knownNotifIds.has(item.id) && !item.is_read) {
              showToast(item);
              break;
            }
          }
        }

        // Update known IDs
        items.forEach(it => knownNotifIds.add(it.id));
        initialLoad = false;

        // Render List
        if (items.length === 0) {
          notifList.innerHTML = `<div class="bf-notif-empty">No notifications yet.</div>`;
        } else {
          notifList.innerHTML = items.map(item => {
            const isDefect = (item.category || "").toUpperCase().includes("DEFECT");
            const iconClass = isDefect ? "defect" : "assign";
            const iconSymbol = isDefect ? "🐞" : "📥";
            const unreadClass = item.is_read ? "" : "unread";
            const targetLink = item.link || (currentRole === "admin" ? "/all-defects-ui" : "/developer-defects-ui");
            const defectId = extractDefectId(item) || "";

            return `
              <div class="bf-notif-item ${unreadClass}" data-id="${item.id}" data-link="${targetLink}" data-defect-id="${defectId}">
                <div class="bf-notif-icon-box ${iconClass}">${iconSymbol}</div>
                <div class="bf-notif-item-body">
                  <div class="bf-notif-item-title">${escapeHtml(item.title)}</div>
                  <div class="bf-notif-item-msg">${escapeHtml(item.message)}</div>
                  <div class="bf-notif-item-time">${timeAgo(item.created_at)}</div>
                </div>
              </div>
            `;
          }).join("");

          // Click handler on notification items
          notifList.querySelectorAll(".bf-notif-item").forEach(itemEl => {
            itemEl.addEventListener("click", async () => {
              const notifId = itemEl.getAttribute("data-id");
              const link = itemEl.getAttribute("data-link");
              const defectId = itemEl.getAttribute("data-defect-id");
              try {
                await fetch(`/api/v1/notifications/read?notification_id=${notifId}`, { method: "POST" });
              } catch (e) {}
              openNotificationDefect(link, defectId);
            });
          });
        }
      } catch (err) {
        console.warn("[BugFlow Notifications] Fetch notice:", err);
      }
    }

    // Initial fetch and poll every 12 seconds
    fetchNotifications();
    setInterval(fetchNotifications, 12000);
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBugFlowResponsiveShell);
  } else {
    initBugFlowResponsiveShell();
  }
})();

/* Shared nav + Gödel keyboard navigation — the ONE place this lives.
   Loads on every page. Add/rename a tab here; no page rebuilds needed. */
(function () {
  const TABS = [
    { key: "1", href: "index.html",       label: "Open tenders",     code: "OPEN" },
    { key: "2", href: "expiry.html",      label: "Expiry radar",     code: "EXP"  },
    { key: "3", href: "accounts.html",    label: "Account map",      code: "ACC"  },
    { key: "4", href: "changes.html",     label: "What changed",     code: "CHG"  },
    { key: "5", href: "regulation.html",  label: "Regulatory radar", code: "REG"  },
    { key: "6", href: "contractors.html", label: "Contractors",      code: "CON"  },
    { key: "7", href: "news.html",        label: "Νέα",              code: "NEWS" },
  ];

  const here = () => (location.pathname.split("/").pop() || "index.html").toLowerCase();

  function renderNav() {
    const slot = document.getElementById("nav");
    if (!slot) return;
    const cur = here();
    slot.className = "nav";
    slot.innerHTML = TABS.map(t => {
      const on = t.href.toLowerCase() === cur ? ' class="on"' : "";
      return `<a href="${t.href}"${on}><span class="kbd">${t.key}</span>${t.label}</a>`;
    }).join("") + `<span class="nav-hint">? για βοήθεια</span>`;
  }

  function ensureCmdBar() {
    if (document.getElementById("cmdbar")) return;
    const bar = document.createElement("div");
    bar.id = "cmdbar";
    bar.innerHTML =
      '<div class="cmdbox">' +
      '<div class="cmdrow">' +
      '<span class="cmdprompt">&gt;</span>' +
      '<input id="cmdinput" autocomplete="off" spellcheck="false" ' +
      'placeholder="tab (open/exp/acc/chg/reg/con) or search...">' +
      '</div>' +
      '<div class="cmdlist" id="cmdlist"></div>' +
      '</div>';
    document.body.appendChild(bar);
    const input = document.getElementById("cmdinput");
    input.addEventListener("input", () => renderSuggestions(input.value.trim()));
    input.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Escape") { closeCmd(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); moveSel(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); moveSel(-1); }
      else if (e.key === "Enter") { runSelected(input.value.trim()); }
    });
    bar.addEventListener("click", (e) => { if (e.target === bar) closeCmd(); });
  }

  let suggestions = [], selIdx = 0;

  function computeSuggestions(v) {
    const low = v.toLowerCase();
    const out = [];
    // matching tabs first
    TABS.forEach(t => {
      if (!low || t.code.toLowerCase().startsWith(low) ||
          t.label.toLowerCase().includes(low) || t.key === low) {
        out.push({ type: "tab", label: t.label, code: t.code,
                   key: t.key, href: t.href });
      }
    });
    // a search action if there's a query that isn't just a tab code
    if (low) {
      out.push({ type: "search", label: 'Αναζήτηση: "' + v + '"',
                 code: "→ Contractors", href: "contractors.html?q=" + encodeURIComponent(v) });
    }
    return out;
  }

  function renderSuggestions(v) {
    suggestions = computeSuggestions(v);
    selIdx = 0;
    const list = document.getElementById("cmdlist");
    if (!suggestions.length) { list.innerHTML = ""; return; }
    list.innerHTML = suggestions.map((s, i) =>
      '<div class="cmditem' + (i === 0 ? ' sel' : '') + '" data-i="' + i + '">' +
      (s.type === "tab" ? '<span class="ci-key">' + s.key + '</span>' :
                          '<span class="ci-key ci-search">⌕</span>') +
      '<span class="ci-label">' + s.label + '</span>' +
      '<span class="ci-code">' + s.code + '</span>' +
      '<span class="ci-enter">Enter ⏎</span></div>'
    ).join("");
    Array.from(list.querySelectorAll(".cmditem")).forEach(el => {
      el.addEventListener("click", () => {
        selIdx = parseInt(el.dataset.i, 10);
        runSelected(document.getElementById("cmdinput").value.trim());
      });
    });
  }

  function moveSel(d) {
    if (!suggestions.length) return;
    selIdx = (selIdx + d + suggestions.length) % suggestions.length;
    const items = document.querySelectorAll("#cmdlist .cmditem");
    items.forEach((el, i) => el.classList.toggle("sel", i === selIdx));
  }

  function runSelected(v) {
    if (suggestions.length && suggestions[selIdx]) {
      location.href = suggestions[selIdx].href;
      return;
    }
    runCmd(v);
  }

  function openCmd() {
    ensureCmdBar();
    document.getElementById("cmdbar").classList.add("show");
    const i = document.getElementById("cmdinput");
    i.value = ""; i.focus();
    renderSuggestions("");
  }
  function closeCmd() {
    const b = document.getElementById("cmdbar");
    if (b) b.classList.remove("show");
  }

  function runCmd(v) {
    if (!v) { closeCmd(); return; }
    const low = v.toLowerCase();
    const hit = TABS.find(t => t.code.toLowerCase() === low)
             || TABS.find(t => t.code.toLowerCase().startsWith(low))
             || TABS.find(t => t.label.toLowerCase().startsWith(low));
    if (hit) { location.href = hit.href; return; }
    location.href = "contractors.html?q=" + encodeURIComponent(v);
  }

  function ensureHelp() {
    if (document.getElementById("kbhelp")) return;
    const rows = TABS.map(t =>
      `<tr><td class="k">${t.key}</td><td>${t.label}</td></tr>`).join("");
    const el = document.createElement("div");
    el.id = "kbhelp";
    el.innerHTML =
      '<div class="kbbox"><div class="kbtitle">Συντομεύσεις πληκτρολογίου</div>' +
      '<table>' + rows +
      '<tr><td class="k">/</td><td>Εστίαση στην αναζήτηση</td></tr>' +
      '<tr><td class="k">:</td><td>Γραμμή εντολών (tab ή αναζήτηση)</td></tr>' +
      '<tr><td class="k">g</td><td>Γραμμή εντολών (ίδιο με :)</td></tr>' +
      '<tr><td class="k">?</td><td>Αυτή η βοήθεια</td></tr>' +
      '<tr><td class="k">Esc</td><td>Κλείσιμο</td></tr>' +
      '</table><div class="kbfoot">Πάτα Esc για κλείσιμο</div></div>';
    document.body.appendChild(el);
    el.addEventListener("click", (e) => { if (e.target === el) el.classList.remove("show"); });
  }
  function toggleHelp() {
    ensureHelp();
    document.getElementById("kbhelp").classList.toggle("show");
  }

  function isTyping(e) {
    const t = e.target;
    return t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" ||
                 t.tagName === "SELECT" || t.isContentEditable);
  }

  function onKey(e) {
    const cmdOpen = document.getElementById("cmdbar")?.classList.contains("show");
    if (cmdOpen) return;
    if (isTyping(e)) {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const tab = TABS.find(t => t.key === e.key);
    if (tab) { location.href = tab.href; return; }
    if (e.key === "/") {
      const s = document.querySelector('input[type="search"], #q');
      if (s) { e.preventDefault(); s.focus(); }
    } else if (e.key === ":" || e.key === "g") {
      e.preventDefault(); openCmd();
    } else if (e.key === "?") {
      e.preventDefault(); toggleHelp();
    } else if (e.key === "Escape") {
      document.getElementById("kbhelp")?.classList.remove("show");
    }
  }

  function init() {
    renderNav();
    document.addEventListener("keydown", onKey);
    const q = new URLSearchParams(location.search).get("q");
    if (q) {
      const s = document.querySelector('input[type="search"], #q');
      if (s) { s.value = q; s.dispatchEvent(new Event("input", { bubbles: true })); }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

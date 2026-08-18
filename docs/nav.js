/* Shared nav — the ONE place tabs live.
   Add or rename a tab here; no page rebuilds needed. */
(function () {
  const TABS = [
    { href: "index.html",       label: "Open tenders" },
    { href: "expiry.html",      label: "Expiry radar" },
    { href: "accounts.html",    label: "Account map" },
    { href: "changes.html",     label: "What changed" },
    { href: "regulation.html",  label: "Regulatory radar" },
    { href: "contractors.html", label: "Contractors" },
  ];

  function render() {
    const slot = document.getElementById("nav");
    if (!slot) return;
    const here = (location.pathname.split("/").pop() || "index.html").toLowerCase();
    slot.className = "nav";
    slot.innerHTML = TABS.map(t => {
      const on = t.href.toLowerCase() === here ? ' class="on"' : "";
      return `<a href="${t.href}"${on}>${t.label}</a>`;
    }).join("");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();

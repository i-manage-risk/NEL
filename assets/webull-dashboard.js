const API = "http://127.0.0.1:8765";
const byId = id => document.getElementById(id);
const valueClass = ok => ok ? "green" : "red";
const percent = value => Number.isFinite(value) ? `${value}%` : "—";

function showNotice(message) {
  const notice = byId("notice");
  notice.style.display = message ? "block" : "none";
  notice.innerHTML = message || "";
}

async function loadDashboard() {
  try {
    const response = await fetch(`${API}/api/data`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Local service returned HTTP ${response.status}`);
    const data = await response.json();

    byId("env").textContent = `${(data.environment || "local").toUpperCase()} · LOCAL SERVICE`;
    byId("updated").textContent = data.updatedAt
      ? `Updated ${new Date(data.updatedAt).toLocaleTimeString()}`
      : "—";
    showNotice(data.error || "");

    const body = byId("body");
    if (!data.rows?.length) {
      body.innerHTML = '<tr><td colspan="8" class="empty">No valid rows yet</td></tr>';
      return;
    }

    body.innerHTML = data.rows.map(row => `
      <tr>
        <td class="symbol ${row.qualifies ? "qualified" : ""}">${row.symbol}</td>
        <td class="${valueClass(row.rvol > 30)}">${percent(row.rvol)}</td>
        <td class="${valueClass(row.lod < 68)}">${percent(row.lod)}</td>
        <td class="${valueClass(row.range < 68)}">${percent(row.range)}</td>
        <td class="${valueClass(row.pdh)}">${row.pdh ? "YES" : "NO"}</td>
        <td>${String(row.or).padStart(2, "0")}</td>
        <td class="${row.aboveOrh === null ? "cream" : valueClass(row.aboveOrh)}">${row.aboveOrh === null ? "—" : row.aboveOrh ? "YES" : "NO"}</td>
        <td class="${row.delay < 3 ? "green" : "cream"}">${row.delay}m</td>
      </tr>`).join("");

    if (document.activeElement !== byId("symbols")) {
      byId("symbols").value = data.rows.map(row => row.symbol).join(", ");
    }
  } catch (error) {
    byId("updated").textContent = "Local service offline";
    showNotice(
      "Start <code>app.py</code> on this computer, then allow this page to access the local network if your browser asks. " +
      "Your Webull credentials never leave the local service."
    );
  }
}

async function saveWatchlist() {
  const symbols = byId("symbols").value.split(/[\s,]+/).filter(Boolean);
  try {
    const response = await fetch(`${API}/api/watchlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbols })
    });
    if (!response.ok) throw new Error(`Local service returned HTTP ${response.status}`);
    await loadDashboard();
  } catch (error) {
    showNotice("Could not update the watchlist because the local Webull service is unavailable.");
  }
}

byId("updateButton").addEventListener("click", saveWatchlist);
byId("symbols").addEventListener("keydown", event => {
  if (event.key === "Enter") saveWatchlist();
});

loadDashboard();
setInterval(loadDashboard, 10000);

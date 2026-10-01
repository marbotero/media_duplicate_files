"use strict";

const state = {
  grupos: [],        // grupos del reporte (con _key/_local por archivo)
  filtrados: [],     // grupos tras aplicar filtros
  selIndex: null,    // índice (en filtrados) del grupo seleccionado
  seleccion: new Set(), // keys de archivos marcados para cuarentena
  porKey: {},        // _key -> archivo (para contar tamaños aunque cambies de grupo)
};

const TIPOS = {
  exact: "Duplicado exacto",
  image_similar: "Imágenes similares",
  video_similar: "Videos similares",
};
const PROVEEDORES = {
  google_drive: "Google Drive", onedrive: "OneDrive", whatsapp_local: "WhatsApp",
  google_photos: "Google Photos", local_folder: "Carpeta local", google_takeout: "Google Takeout",
};

function $(sel) { return document.querySelector(sel); }
function fmtSize(b) {
  const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0; b = b || 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return `${b.toFixed(1)} ${u[i]}`;
}
function fmtFecha(v) {
  if (v === null || v === undefined || v === "") return "";
  // EXIF usa "YYYY:MM:DD HH:MM:SS"; normalizar los dos primeros ':' a '-'.
  if (typeof v === "string" && /^\d{4}:\d{2}:\d{2}/.test(v)) {
    return v.slice(0, 10).replace(/:/g, "-");
  }
  // Puede venir como ISO string o como epoch (segundos, float) según el proveedor.
  const num = Number(v);
  const d = Number.isFinite(num) && String(v).trim() !== "" && !isNaN(num)
    ? new Date(num * 1000) : new Date(v);
  return isNaN(d.getTime()) ? String(v).slice(0, 10) : d.toISOString().slice(0, 10);
}

// ── Contador de selección ──────────────────────────────────────────────
function actualizarContador() {
  let total = 0;
  for (const k of state.seleccion) {
    const f = state.porKey[k];
    if (f) total += f.size || 0;
  }
  const n = state.seleccion.size;
  $("#sel-count").textContent = n;
  $("#sel-size").textContent = fmtSize(total);
  const btnSidebar = $("#btn-cuarentena-sidebar");
  btnSidebar.disabled = n === 0;
  btnSidebar.textContent = n ? `Enviar ${n} a cuarentena` : "Enviar a cuarentena";
  const btnDetalle = $("#btn-cuarentena");
  if (btnDetalle) {
    btnDetalle.disabled = n === 0;
    btnDetalle.textContent = n ? `Enviar ${n} seleccionados a cuarentena` : "Enviar seleccionados a cuarentena";
  }
}

// ── Navegación entre vistas ────────────────────────────────────────────
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    tab.classList.add("active");
    $(`#view-${tab.dataset.view}`).classList.add("active");
  });
});

// ── Carga del reporte ──────────────────────────────────────────────────
async function cargarReporte() {
  try {
    const resp = await fetch("/api/report");
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      $("#resumen").textContent = err.error || "No se pudo cargar el reporte.";
      state.grupos = []; aplicarFiltros(); return;
    }
    const data = await resp.json();
    state.grupos = data.groups || [];
    // Índice key -> archivo y limpieza de selección a lo que existe en el reporte.
    state.porKey = {};
    state.grupos.forEach(g => (g.files || []).forEach(f => { state.porKey[f._key] = f; }));
    for (const k of [...state.seleccion]) if (!state.porKey[k]) state.seleccion.delete(k);
    const rec = fmtSize(data.total_recoverable_size || 0);
    $("#resumen").textContent = `${state.grupos.length} grupos · ${rec} recuperables` +
      (data.scan_status === "partial" ? " · ⚠ escaneo parcial" : "");
    poblarProveedores();
    aplicarFiltros();
    actualizarContador();
  } catch (e) {
    $("#resumen").textContent = "Error: " + e;
  }
}

function poblarProveedores() {
  const set = new Set();
  state.grupos.forEach(g => (g.files || []).forEach(f => set.add(f.source)));
  const sel = $("#f-proveedor");
  sel.innerHTML = '<option value="">Todos</option>';
  [...set].sort().forEach(s => {
    const o = document.createElement("option");
    o.value = s; o.textContent = PROVEEDORES[s] || s; sel.appendChild(o);
  });
}

// ── Filtros ────────────────────────────────────────────────────────────
function aplicarFiltros() {
  const umbral = Number($("#f-umbral").value);
  const tipo = $("#f-tipo").value;
  const prov = $("#f-proveedor").value;
  state.filtrados = state.grupos.filter(g => {
    if (tipo && g.group_type !== tipo) return false;
    const score = g.group_type === "exact" ? 100 : (g.score || 0);
    if (score < umbral) return false;
    if (prov && !(g.files || []).some(f => f.source === prov)) return false;
    return true;
  });
  renderLista();
  // Mantener selección si sigue presente; si no, limpiar detalle.
  if (state.selIndex === null || state.selIndex >= state.filtrados.length) {
    state.selIndex = null;
    $("#detalle-placeholder").hidden = false;
    $("#detalle-header").hidden = true;
    $("#comparativa").innerHTML = "";
  }
}

$("#f-umbral").addEventListener("input", e => {
  $("#umbral-val").textContent = e.target.value; aplicarFiltros();
});
$("#f-tipo").addEventListener("change", aplicarFiltros);
$("#f-proveedor").addEventListener("change", aplicarFiltros);
$("#btn-recargar").addEventListener("click", cargarReporte);

// ── Lista de grupos (barra lateral scrollable) ─────────────────────────
function renderLista() {
  const ul = $("#lista-grupos");
  ul.innerHTML = "";
  if (!state.filtrados.length) {
    ul.innerHTML = '<li class="grupo-item">Sin grupos que mostrar.</li>';
    return;
  }
  state.filtrados.forEach((g, i) => {
    const score = g.group_type === "exact" ? "exacto" : `${(g.score || 0).toFixed(1)}%`;
    const li = document.createElement("li");
    li.className = "grupo-item" + (i === state.selIndex ? " sel" : "");
    li.innerHTML = `
      <div class="linea1">
        <span>Grupo ${i + 1}</span>
        <span class="pill ${g.group_type}">${TIPOS[g.group_type] || g.group_type}</span>
      </div>
      <div class="linea2">${(g.files || []).length} archivos · ${score} · ${fmtSize(g.recoverable_size)} recuperables</div>`;
    li.addEventListener("click", () => seleccionarGrupo(i));
    ul.appendChild(li);
  });
}

// ── Comparativa lado a lado ────────────────────────────────────────────
function seleccionarGrupo(i) {
  state.selIndex = i;
  renderLista();
  const g = state.filtrados[i];
  const archivos = [...(g.files || [])].sort(
    (a, b) => ((b.width || 0) * (b.height || 0)) - ((a.width || 0) * (a.height || 0))
  );
  $("#detalle-placeholder").hidden = true;
  $("#detalle-header").hidden = false;
  $("#detalle-titulo").textContent =
    `${TIPOS[g.group_type] || g.group_type} — ${archivos.length} archivos`;

  const campos = camposDelGrupo(archivos);
  const cont = $("#comparativa");
  cont.innerHTML = "";
  archivos.forEach((f, idx) => cont.appendChild(crearTarjeta(f, idx === 0, campos)));
  actualizarContador();
}

function meta(f) { return (f.extra && f.extra.metadata) || {}; }

function resolucion(f) {
  if (f.width && f.height) return `${f.width}×${f.height} px`;
  const r = meta(f).resolution;
  if (r && r.width && r.height) return `${r.width}×${r.height} px`;
  return null;
}

function duracion(f) {
  let seg = f.duration_ms ? f.duration_ms / 1000 : Number(meta(f).duration_seconds);
  if (!seg || isNaN(seg)) return null;
  const m = Math.floor(seg / 60), s = Math.floor(seg % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function corto(h) { return h ? h.slice(0, 16) + "…" : null; }
function vacio(v) { return v === null || v === undefined || v === ""; }

// Campos de metadatos en orden canónico. Cada uno extrae su valor de un archivo
// (null si no lo tiene) y opcionalmente un enlace. Se renderizan SIEMPRE en este
// mismo orden en todas las tarjetas del grupo para poder compararlos fila a fila.
const CAMPOS = [
  { label: "Ruta", get: f => f.path },
  { label: "Resolución", get: resolucion },
  { label: "Duración", get: f => (f.mime_type || "").startsWith("video") ? duracion(f) : null },
  { label: "Tipo", get: f => f.mime_type },
  { label: "Formato", get: f => meta(f).format },
  { label: "Color", get: f => meta(f).color_mode },
  { label: "Cámara", get: f => [meta(f).camera_make, meta(f).camera_model].filter(Boolean).join(" ") || null },
  { label: "Lente", get: f => meta(f).lens_model },
  { label: "Fecha captura", get: f => meta(f).date_taken ? fmtFecha(meta(f).date_taken) : null },
  { label: "ISO", get: f => meta(f).iso },
  { label: "Apertura", get: f => meta(f).aperture ? `ƒ/${meta(f).aperture}` : null },
  { label: "Exposición", get: f => meta(f).exposure_time },
  { label: "Focal", get: f => meta(f).focal_length },
  { label: "Orientación", get: f => meta(f).orientation },
  { label: "Códec video", get: f => meta(f).video_codec },
  { label: "FPS", get: f => meta(f).fps },
  { label: "Códec audio", get: f => meta(f).audio_codec },
  { label: "Software", get: f => meta(f).software },
  {
    label: "GPS",
    get: f => { const g = meta(f).gps; if (!g) return null; return g.latitude_decimal != null ? `${g.latitude_decimal}, ${g.longitude_decimal}` : "ver mapa"; },
    href: f => { const g = meta(f).gps; return g && g.google_maps_url; },
  },
  { label: "Tamaño", get: f => fmtSize(f.size) },
  { label: "Modificado", get: f => f.modified_time ? fmtFecha(f.modified_time) : null },
  { label: "Origen", get: f => PROVEEDORES[f.source] || f.source },
  { label: "MD5", get: f => corto(f.md5) },
  { label: "SHA-256", get: f => corto(f.sha256) },
];

// Campos que tiene al menos un archivo del grupo (los demás se omiten para todos).
function camposDelGrupo(archivos) {
  return CAMPOS.filter(c => archivos.some(f => !vacio(c.get(f))));
}

function crearTarjeta(f, esMejor, campos) {
  const card = document.createElement("div");
  card.className = "tarjeta" + (esMejor ? " mejor" : "");

  const thumb = document.createElement("div");
  thumb.className = "thumb";
  if (f._local) {
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = `/api/thumbnail?key=${f._key}`;
    img.alt = f.name || "";
    img.onerror = () => { thumb.innerHTML = '<span class="noimg">🖼️</span>'; };
    thumb.appendChild(img);
    thumb.addEventListener("click", () => abrirLightbox(f._key));
  } else {
    thumb.innerHTML = '<span class="noimg">☁️</span>';
  }
  card.appendChild(thumb);

  const cuerpo = document.createElement("div");
  cuerpo.className = "cuerpo";

  const nombre = document.createElement("div");
  nombre.className = "nombre";
  nombre.textContent = f.name || "sin nombre";
  nombre.title = f.name || "";
  cuerpo.appendChild(nombre);

  const tabla = document.createElement("div");
  tabla.className = "meta-tabla";
  campos.forEach(c => {
    const value = c.get(f);
    const href = !vacio(value) && c.href ? c.href(f) : null;
    const row = document.createElement("div");
    row.className = "mrow" + (vacio(value) ? " ausente" : "");
    const k = document.createElement("span");
    k.className = "k"; k.textContent = c.label;
    const v = document.createElement("span");
    v.className = "v";
    if (vacio(value)) {
      v.textContent = "—";
    } else if (href) {
      const a = document.createElement("a");
      a.href = href; a.target = "_blank"; a.textContent = value; a.title = value;
      v.appendChild(a);
    } else {
      v.textContent = value; v.title = String(value);
    }
    row.appendChild(k); row.appendChild(v);
    tabla.appendChild(row);
  });
  cuerpo.appendChild(tabla);

  const filaSel = document.createElement("div");
  filaSel.className = "fila-sel";
  if (f._local) {
    const lbl = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = state.seleccion.has(f._key);
    cb.addEventListener("change", () => {
      if (cb.checked) state.seleccion.add(f._key); else state.seleccion.delete(f._key);
      actualizarContador();
    });
    lbl.appendChild(cb);
    lbl.appendChild(document.createTextNode(" eliminar"));
    filaSel.appendChild(lbl);
  } else if (f.web_url) {
    const a = document.createElement("a");
    a.className = "abrir"; a.href = f.web_url; a.target = "_blank"; a.textContent = "Abrir en la nube ↗";
    filaSel.appendChild(a);
  }
  if (esMejor) {
    const b = document.createElement("span");
    b.className = "badge-mejor"; b.textContent = "⭐ MEJOR";
    filaSel.appendChild(b);
  }
  cuerpo.appendChild(filaSel);
  card.appendChild(cuerpo);
  return card;
}

function escapeHtml(s) {
  const d = document.createElement("div"); d.textContent = s; return d.innerHTML;
}

// ── Lightbox ───────────────────────────────────────────────────────────
function abrirLightbox(key) {
  $("#lightbox-img").src = `/api/file?key=${key}`;
  $("#lightbox").hidden = false;
}
$("#lightbox").addEventListener("click", () => { $("#lightbox").hidden = true; });

// ── Cuarentena ─────────────────────────────────────────────────────────
async function enviarCuarentena() {
  const keys = [...state.seleccion];
  if (!keys.length) { alert("No hay archivos locales seleccionados."); return; }
  const total = fmtSize(keys.reduce((s, k) => s + ((state.porKey[k] && state.porKey[k].size) || 0), 0));
  if (!confirm(`Mover ${keys.length} archivo(s) a cuarentena? Se liberarán ${total}.`)) return;
  const resp = await fetch("/api/quarantine", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keys }),
  });
  const r = await resp.json();
  let msg = `Movidos: ${r.moved}` + (r.session ? ` (sesión ${r.session})` : "");
  if (r.errors && r.errors.length) msg += "\nErrores:\n" + r.errors.join("\n");
  alert(msg);
  state.seleccion.clear();
  await cargarReporte();
}
$("#btn-cuarentena").addEventListener("click", enviarCuarentena);
$("#btn-cuarentena-sidebar").addEventListener("click", enviarCuarentena);

// ── Escaneo / Operación ────────────────────────────────────────────────
const log = $("#log");
function logLine(t) { log.textContent += t + "\n"; log.scrollTop = log.scrollHeight; }

function escucharStream() {
  const es = new EventSource("/api/scan/stream");
  es.onmessage = ev => {
    const linea = JSON.parse(ev.data);
    if (linea.startsWith("__FIN__")) {
      logLine("── Proceso finalizado ──");
      es.close(); finProceso(); cargarReporte();
    } else if (linea.startsWith("__ERROR__")) {
      logLine("ERROR: " + linea.slice(9)); es.close(); finProceso();
    } else { logLine(linea); }
  };
  es.onerror = () => { es.close(); finProceso(); };
}

function finProceso() {
  $("#btn-escanear").disabled = false;
  $("#btn-cancelar").disabled = true;
}

$("#btn-escanear").addEventListener("click", async () => {
  const cfg = {
    local_folders: $("#op-local").value.split("\n").map(s => s.trim()).filter(Boolean),
    hash_mode: $("#op-hash").value,
    image_threshold: Number($("#op-umbral-img").value),
    skip_similar: $("#op-skip").checked,
    report: $("#op-report").value.trim() || null,
  };
  if (!cfg.local_folders.length) { alert("Indica al menos una carpeta local."); return; }
  log.textContent = "";
  const resp = await fetch("/api/scan", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });
  const r = await resp.json();
  if (!r.ok) { alert(r.error || "No se pudo iniciar."); return; }
  logLine("$ " + r.command);
  $("#btn-escanear").disabled = true;
  $("#btn-cancelar").disabled = false;
  escucharStream();
});

$("#btn-cancelar").addEventListener("click", async () => {
  await fetch("/api/scan/cancel", { method: "POST" });
  logLine("── Cancelando… ──");
});

document.querySelectorAll(".btn-auth").forEach(btn => {
  btn.addEventListener("click", async () => {
    log.textContent = "";
    const resp = await fetch("/api/auth", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: btn.dataset.prov }),
    });
    const r = await resp.json();
    if (!r.ok) { alert(r.error || "No se pudo iniciar."); return; }
    logLine(`Autenticando ${btn.dataset.prov}…`);
    escucharStream();
  });
});

// Arranque
cargarReporte();

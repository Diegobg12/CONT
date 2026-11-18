// Utilidades compartidas para hablar con el backend (no cambia el diseño).
const API = {
  async get(url) {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error(await API.error(r));
    return r.json();
  },
  async post(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    if (!r.ok) throw new Error(await API.error(r));
    return r.json();
  },
  async error(r) {
    try { const j = await r.json(); return typeof j.detail === 'string' ? j.detail : (j.detail || []).map(e => e.mensaje).join('. '); }
    catch { return 'Error ' + r.status; }
  },
  descargaId() { return new URLSearchParams(location.search).get('d'); },
  // Si no hay descarga en la URL, se vuelve al paso 1.
  requerirDescarga() { const d = API.descargaId(); if (!d) location.replace('1-cliente-fechas.html'); return d; },
  fecha(iso) { const [y, m, d] = iso.split('-'); return `${d}/${m}/${y}`; },
  pesos(v) { return '$' + Math.round(Number(v)).toLocaleString('es-CO'); },
  millones(v) {
    const n = Number(v);
    return n >= 1e6 ? '$' + (n / 1e6).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' M' : API.pesos(n);
  },
  cufeCorto(c) { return c.length > 12 ? c.slice(0, 6) + '…' + c.slice(-4) : c; },
  eyebrow(desc) { return `Facturas DIAN · ${desc.cliente.razon_social} · ${API.fecha(desc.fecha_ini)} – ${API.fecha(desc.fecha_fin)}`; },
  esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
};

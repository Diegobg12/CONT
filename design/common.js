// Menú lateral y stepper compartidos por las 5 pantallas.
// Uso: <nav id="nav"></nav> y <ol class="steps" data-current="0"></ol>
(function () {
  const I = {
    panel: 'M4 19V9M10 19V5M16 19v-7M22 19H2',
    clientes: 'M9 4.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7M2.5 20c1-3.5 3.5-5 6.5-5s5.5 1.5 6.5 5M16 4.5a3.5 3.5 0 0 1 0 7',
    banco: 'M3 9 12 4l9 5M5 10v8M10 10v8M14 10v8M19 10v8M3 20h18',
    fact: 'M12 4v11M7 10l5 5 5-5M5 20h14',
    contr: 'M14 3H6v18h12V7zM14 3v4h4M9 13h6M9 17h4',
    nomina: 'M3 6h18v12H3zM3 10h18M7 15h4',
    imp: 'M6 3h12v18H6zM9 7h6M9 11h6M9 15h2',
    act: 'M3 4h18v16H3zM9 4v16M15 4v16',
    rep: 'm3 17 6-6 4 4 8-8M15 7h6v6',
    users: 'M10 4a4 4 0 1 0 0 8a4 4 0 1 0 0-8M3 21c1.3-3.8 4-6 7-6 1.4 0 2.7.4 3.8 1.2m2.2 2.8 2 2 4-4',
    conf: 'M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6M12 2v3M12 19v3M2 12h3M19 12h3'
  };
  // En la beta solo "Facturas DIAN" está activo; el resto queda como "próximamente".
  const items = [
    ['Panel', I.panel], ['Clientes', I.clientes], ['Conciliación bancaria', I.banco],
    ['Facturas DIAN', I.fact], ['Contratos', I.contr], ['Nómina', I.nomina], ['Impuestos', I.imp],
    ['Actividades', I.act], ['Reportes y estadísticas', I.rep], ['Usuarios', I.users], ['Configuración', I.conf]
  ];
  const nav = document.getElementById('nav');
  if (nav) {
    nav.className = 'nav';
    nav.setAttribute('aria-label', 'Módulos');
    nav.innerHTML = '<p class="label">MÓDULOS</p>' + items.map(([label, d]) => {
      const on = label === 'Facturas DIAN';
      const mt = label === 'Configuración' ? ' style="margin-top:auto"' : '';
      return `<a href="${on ? '1-cliente-fechas.html' : '#'}" class="${on ? 'on' : ''}"${mt}>` +
        `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>` +
        `<span>${label}</span></a>`;
    }).join('');
  }
  const steps = document.querySelector('.steps');
  if (steps) {
    const cur = Number(steps.dataset.current || 0);
    steps.setAttribute('aria-label', 'Pasos del proceso');
    steps.innerHTML = ['Cliente y fechas', 'Token DIAN', 'Descarga', 'Revisión', 'Subida a Siigo'].map((l, i) => {
      const cls = i < cur ? 'done' : (i === cur ? 'cur' : '');
      return `<li class="${cls}"><span class="dot">${i < cur ? '✓' : i + 1}</span>${l}</li>`;
    }).join('');
  }
})();

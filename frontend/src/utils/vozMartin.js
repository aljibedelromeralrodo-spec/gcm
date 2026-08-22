// Voz de Martín — selector estricto de voz en español (latino neutro primero)
export function elegirVozEspanol() {
  const voces = window.speechSynthesis?.getVoices() || [];
  const es = voces.filter(v => (v.lang || "").toLowerCase().startsWith("es"));
  if (!es.length) return null;
  const porNombre = es.find(v => /google.*espa|espa.*(latin|am[eé]rica|estados unidos|m[eé]xico)/i.test(v.name));
  if (porNombre) return porNombre;
  for (const p of ["es-419", "es-us", "es-mx", "es-cl", "es-ar", "es-es"]) {
    const v = es.find(x => x.lang.toLowerCase().startsWith(p));
    if (v) return v;
  }
  return es[0];
}

export function hablarMartin(texto) {
  try {
    const synth = window.speechSynthesis;
    if (!synth) return;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(texto);
    const v = elegirVozEspanol();
    if (v) { u.voice = v; u.lang = v.lang; }
    else u.lang = "es-419";
    u.rate = 1.0;
    u.pitch = 1.0;
    synth.speak(u);
  } catch {}
}

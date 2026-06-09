const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

type Source = { id: string; nombre: string; categoria: string; url: string };

const SOURCES: Source[] = [
  ["bora", "Boletin Oficial BORA", "sociedades", "https://www.boletinoficial.gob.ar/"],
  ["bora_segunda", "BORA Segunda Seccion", "sociedades", "https://www.boletinoficial.gob.ar/seccion/segunda"],
  ["timeline", "Timeline societario BORA", "sociedades", "https://timeline.boletinoficial.gob.ar/"],
  ["rns", "Registro Nacional de Sociedades", "sociedades", "https://www.argentina.gob.ar/justicia/registro-nacional-sociedades"],
  ["igj", "IGJ", "sociedades", "https://www.argentina.gob.ar/justicia/igj"],
  ["bcra", "BCRA Central de Deudores", "crediticia", "https://www.bcra.gob.ar/BCRAyVos/Situacion_Crediticia.asp"],
  ["arca", "ARCA", "fiscal", "https://www.arca.gob.ar/"],
  ["anses", "ANSES", "laboral", "https://www.anses.gob.ar/"],
  ["sssalud", "SSSalud", "laboral", "https://www.sssalud.gob.ar/"],
  ["srt", "SRT", "laboral", "https://www.srt.gob.ar/"],
  ["pjn", "PJN", "judicial", "https://www.pjn.gov.ar/"],
  ["csjn", "CSJN", "judicial", "https://www.csjn.gov.ar/"],
  ["compras", "Compras publicas", "licitaciones", "https://www.compras.gob.ar/"],
  ["diputados", "Diputados Nacionales", "legisladores", "https://www.diputados.gov.ar/diputados/"],
  ["senado", "Senado Nacional", "legisladores", "https://www.senado.gob.ar/senadores/listado/completo"],
  ["directorio", "Directorio Legislativo", "legisladores", "https://directoriodirecto.org/"],
  ["bo_pba", "Boletin Oficial Buenos Aires", "boletines_provinciales", "https://boletinoficial.gba.gob.ar/"],
  ["dppj_pba", "DPPJ Buenos Aires", "sociedades", "https://www.gba.gob.ar/dppj"],
  ["bo_caba", "Boletin Oficial CABA", "boletines_provinciales", "https://boletinoficial.buenosaires.gob.ar/"],
  ["bo_cordoba", "Boletin Oficial Cordoba", "boletines_provinciales", "https://boletinoficial.cba.gov.ar/"],
  ["bo_santafe", "Boletin Oficial Santa Fe", "boletines_provinciales", "https://www.santafe.gob.ar/boletinoficial/"],
  ["bo_mendoza", "Boletin Oficial Mendoza", "boletines_provinciales", "https://boletinoficial.mendoza.gov.ar/"],
  ["bo_tucuman", "Boletin Oficial Tucuman", "boletines_provinciales", "https://boletin.tucuman.gov.ar/"],
  ["clarin", "Clarin", "medios", "https://www.clarin.com/"],
  ["lanacion", "La Nacion", "medios", "https://www.lanacion.com.ar/"],
  ["infobae", "Infobae", "medios", "https://www.infobae.com/"],
  ["pagina12", "Pagina 12", "medios", "https://www.pagina12.com.ar/"],
  ["ambito", "Ambito", "medios", "https://www.ambito.com/"],
  ["perfil", "Perfil", "medios", "https://www.perfil.com/"],
  ["cronista", "El Cronista", "medios", "https://www.cronista.com/"],
].map(([id, nombre, categoria, url]) => ({ id, nombre, categoria, url }));

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const body = await req.json();
    const nombre = String(body.nombre || body.identificador || "").trim();
    const identificador = String(body.identificador || "").replace(/\D/g, "");
    if (!nombre && !identificador) return json({ error: "Ingrese nombre, DNI, CUIL o CUIT" }, 400);

    const normalizado = normalizeId(identificador);
    const cuiles = normalizado.cuils_derivados || [];
    const bcra = await Promise.all(cuiles.slice(0, 3).map(consultarBcra));
    const evidencias = [
      ...bcra.map((b) => ({
        fuente: "BCRA Central de Deudores",
        categoria: "crediticia",
        url: "https://api.bcra.gob.ar/CentralDeDeudores/v1.0",
        titulo: `Consulta BCRA ${b.identificacion}`,
        extracto: `Estado: ${b.estado}; deudas: ${b.deudas?.length || 0}; historico: ${b.historico?.length || 0}; cheques: ${b.cheques_rechazados?.length || 0}`,
        confianza: b.estado && !String(b.estado).startsWith("error") ? "alta" : "media",
        score: b.estado && !String(b.estado).startsWith("error") ? 95 : 55,
        coincidencia: "identificador oficial",
      })),
      ...await buildSearchEvidence(nombre || identificador),
    ];
    const verificadas = evidencias.filter((e) => e.confianza === "alta");
    const categorias = countBy(evidencias.map((e) => e.categoria));
    const riesgo = classifyBcra(bcra);
    const confiabilidad = verificadas.length ? "alta" : evidencias.length > 4 ? "media" : "baja";

    return json({
      target: { nombre, identificador, tipo: body.tipo || "indistinto", normalizado },
      resumen: {
        fecha: new Date().toISOString(),
        fuentes_consultadas: SOURCES.length + (cuiles.length ? 1 : 0),
        evidencias: evidencias.length,
        categorias,
        riesgo_crediticio: riesgo,
        evidencias_verificadas: verificadas.length,
        indicios: evidencias.length - verificadas.length,
        confiabilidad_global: confiabilidad,
      },
      hallazgos: [
        { titulo: "Identidad normalizada", valor: normalizado.formateado || identificador || nombre, confianza: cuiles.length ? "alta" : "media", detalle: `CUIL/CUIT derivados o informados: ${cuiles.length}` },
        { titulo: "Riesgo crediticio BCRA", valor: riesgo, confianza: cuiles.length ? "alta" : "baja", detalle: "Consulta directa contra API publica BCRA si hay CUIL/CUIT/DNI." },
        { titulo: "Cobertura OSINT", valor: `${evidencias.length} evidencias / ${SOURCES.length} fuentes`, confianza: confiabilidad, detalle: `Verificadas: ${verificadas.length}. Indicios: ${evidencias.length - verificadas.length}.` },
      ],
      fuentes: SOURCES.map((s) => ({ ...s, resultados: evidencias.filter((e) => e.fuente === s.nombre).length, estado: evidencias.some((e) => e.fuente === s.nombre) ? "con_hallazgos" : "consultada" })),
      evidencias,
      evidencias_verificadas: verificadas,
      indicios: evidencias.filter((e) => e.confianza !== "alta"),
      grafo: buildGraph(nombre || identificador, evidencias, cuiles, categorias),
      limitaciones: [
        "El sistema usa fuentes abiertas y no evade captchas, logins, paywalls ni controles de acceso.",
        "Alta confianza requiere identificador oficial o coincidencias fuertes en fuentes independientes.",
        "ARCA, ANSES, SSSalud, SRT e IGJ pueden requerir pasos manuales para datos completos.",
      ],
    });
  } catch (e) {
    return json({ error: String(e?.message || e) }, 500);
  }
});

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { ...cors, "Content-Type": "application/json" } });
}

async function buildSearchEvidence(q: string) {
  const quoted = `"${q}"`;
  const batches = await Promise.all(SOURCES.map(async (s) => {
    const host = new URL(s.url).hostname.replace(/^www\./, "");
    const query = `site:${host} ${quoted}`;
    const searchUrl = `https://duckduckgo.com/html/?q=${encodeURIComponent(query)}`;
    try {
      const r = await fetch(searchUrl, {
        headers: { "User-Agent": "Diagonales-Intelligence/1.0" },
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) return [];
      const html = await r.text();
      const matches = [...html.matchAll(/<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)<\/a>[\s\S]*?(?:<a[^>]+class="result__snippet"[^>]*>(.*?)<\/a>|<div[^>]+class="result__snippet"[^>]*>(.*?)<\/div>)?/g)].slice(0, 3);
      return matches.map((m) => {
        const title = cleanHtml(m[2]);
        const snippet = cleanHtml(m[3] || m[4] || "");
        const url = decodeDuckUrl(m[1]);
        const score = scoreEvidence(q, title, snippet, s.categoria);
        return {
          fuente: s.nombre,
          categoria: s.categoria,
          url,
          titulo: title || `Resultado en ${s.nombre}`,
          extracto: snippet || query,
          confianza: score >= 70 ? "alta" : score >= 35 ? "media" : "baja",
          score,
          coincidencia: score >= 70 ? "coincidencia fuerte en resultado indexado" : "coincidencia parcial en resultado indexado",
        };
      });
    } catch {
      return [];
    }
  }));
  return batches.flat();
}

function cleanHtml(s: string) {
  return s.replace(/<[^>]+>/g, " ").replace(/&quot;/g, "\"").replace(/&amp;/g, "&").replace(/&#x27;/g, "'").replace(/\s+/g, " ").trim();
}

function decodeDuckUrl(raw: string) {
  const value = raw.replace(/&amp;/g, "&");
  try {
    const url = new URL(value, "https://duckduckgo.com");
    const uddg = url.searchParams.get("uddg");
    return uddg ? decodeURIComponent(uddg) : value;
  } catch {
    return value;
  }
}

function scoreEvidence(q: string, title: string, snippet: string, categoria: string) {
  const hay = `${title} ${snippet}`.toLowerCase();
  const tokens = q.toLowerCase().split(/\s+/).filter((x) => x.length > 2);
  let score = tokens.filter((t) => hay.includes(t)).length * 18;
  if (hay.includes(q.toLowerCase())) score += 45;
  if (["sociedades", "crediticia", "judicial", "boletines_provinciales"].includes(categoria)) score += 8;
  if (/(cuit|cuil|dni|bolet[ií]n|sociedad|expediente|deudor|licitaci[oó]n)/i.test(hay)) score += 12;
  return Math.min(score, 100);
}

async function consultarBcra(id: string) {
  const base = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0";
  const out: any = { identificacion: id, estado: "sin_datos", deudas: [], historico: [], cheques_rechazados: [] };
  for (const [key, path] of [["deudas", "Deudas"], ["historico", "DeudasHistoricas"], ["cheques_rechazados", "ChequesRechazados"]] as const) {
    try {
      const r = await fetch(`${base}/${path}/${id}`, { headers: { Accept: "application/json" } });
      if (r.status === 404) { if (key === "deudas") out.estado = "sin_deudas"; continue; }
      if (!r.ok) continue;
      const data = await r.json();
      const periodos = data?.results?.periodos || [];
      if (key === "deudas") out.estado = periodos.length ? "con_deudas" : "sin_deudas";
      out[key] = periodos.flatMap((p: any) => (p.entidades || []).map((e: any) => ({ periodo: p.periodo, ...e })));
    } catch { out.estado = "error_api"; }
  }
  return out;
}

function normalizeId(raw: string) {
  if (!raw) return { tipo: "sin_identificador", cuils_derivados: [] };
  if (raw.length === 11) return { tipo: "cuil_cuit", valor_limpio: raw, formateado: `${raw.slice(0,2)}-${raw.slice(2,10)}-${raw.slice(10)}`, cuils_derivados: [raw] };
  if (raw.length >= 7 && raw.length <= 8) return { tipo: "dni", valor_limpio: raw, formateado: raw, cuils_derivados: deriveCuils(raw) };
  return { tipo: "desconocido", valor_limpio: raw, cuils_derivados: [] };
}

function deriveCuils(dniRaw: string) {
  const dni = dniRaw.padStart(8, "0");
  return ["20", "23", "24", "27", "30", "33", "34"].map((p) => {
    const base = p + dni;
    const weights = [5,4,3,2,7,6,5,4,3,2];
    const sum = base.split("").reduce((a, n, i) => a + Number(n) * weights[i], 0);
    const rest = sum % 11;
    const dv = rest === 0 ? 0 : rest === 1 ? null : 11 - rest;
    return dv === null ? null : `${base}${dv}`;
  }).filter(Boolean) as string[];
}

function classifyBcra(items: any[]) {
  const deudas = items.flatMap((x) => x.deudas || []);
  if (!items.length) return "indeterminado";
  if (!deudas.length) return "bajo";
  const max = Math.max(...deudas.map((d) => Number(d.situacion || 1)));
  return max >= 4 ? "alto" : max >= 2 ? "medio" : "bajo";
}

function countBy(items: string[]) {
  return items.reduce((acc: Record<string, number>, x) => ((acc[x] = (acc[x] || 0) + 1), acc), {});
}

function buildGraph(name: string, evidencias: any[], cuiles: string[], categorias: Record<string, number>) {
  const nodes: any[] = [{ id: "target", label: name, type: "target", score: 100 }];
  const edges: any[] = [];
  cuiles.slice(0, 3).forEach((c) => { nodes.push({ id: c, label: c, type: "identificador", score: 90 }); edges.push({ from: "target", to: c, label: "identificador", confidence: "alta" }); });
  Object.entries(categorias).forEach(([cat, n]) => { nodes.push({ id: `cat-${cat}`, label: `${cat} (${n})`, type: "categoria", score: 60 }); edges.push({ from: "target", to: `cat-${cat}`, label: "evidencia", confidence: "media" }); });
  evidencias.slice(0, 30).forEach((e, i) => { nodes.push({ id: `ev-${i}`, label: e.fuente, type: "fuente", score: e.score || 40 }); edges.push({ from: `cat-${e.categoria}`, to: `ev-${i}`, label: e.confianza, confidence: e.confianza }); });
  return { nodes, edges };
}

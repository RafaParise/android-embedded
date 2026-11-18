// Mensagens de status do Univo no Qwen Code do celular: ESPELHO de status_univo.py (mesma normalizacao, mesma
// classificacao, mesma selecao). 18/11/2026. Fonte das frases: frases-status.json (ao lado). Mudou a logica aqui?
// Mude la tambem: o teste test_status_univo.py roda os dois com os mesmos pedidos e exige a mesma categoria.
// Quem chama: o patch do `status_univo.py qwen-patch aplicar` no Qwen Code (envio do pedido e ciclador de frases).
"use strict";
const fs = require("node:fs");
const path = require("node:path");

const LIMITE_LONGO = 600;
const LIMITE_CURTO = 3;
const TTL_PENDENTE_MS = 120000;
const FIXAS = ["curto", "longo", "generico"];

function carregar(caminho) {
  return JSON.parse(fs.readFileSync(caminho || path.join(__dirname, "frases-status.json"), "utf8"));
}

function normalizar(texto) {
  return String(texto == null ? "" : texto).toLowerCase().normalize("NFD")
    .replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
}

function textoDoPedido(obj) {
  if (obj == null) return "";
  if (typeof obj === "string") return obj;
  if (Array.isArray(obj)) return obj.map(textoDoPedido).filter(Boolean).join(" ");
  if (typeof obj === "object") {
    for (const k of ["text", "content", "prompt"]) if (k in obj) return textoDoPedido(obj[k]);
  }
  return "";
}

function casa(t, palavra) {
  if (palavra.endsWith("*")) {
    const raiz = normalizar(palavra.slice(0, -1));
    return Boolean(raiz) && (" " + t).includes(" " + raiz);
  }
  const p = normalizar(palavra);
  return Boolean(p) && (" " + t + " ").includes(" " + p + " ");
}

function classificar(texto, cat) {
  const bruto = textoDoPedido(texto);
  const t = normalizar(bruto);
  let melhor = null, pontos = 0;
  for (const c of cat.contextual) {
    const n = c.palavras.filter((p) => casa(t, p)).length * (parseInt(c.peso, 10) || 1);
    if (n > pontos) { melhor = c.id; pontos = n; }
  }
  if (melhor) return melhor;
  if (bruto.trim().length > LIMITE_LONGO) return "longo";
  if (t && t.split(" ").length <= LIMITE_CURTO) return "curto";
  return "generico";
}

function frasesDaCategoria(id, cat) {
  if (FIXAS.includes(id)) return cat[id].slice();
  const c = cat.contextual.find((x) => x.id === id);
  return (c ? c.frases : cat.generico).slice();
}

function criar(cat, rng) {
  cat = cat || carregar();
  rng = rng || Math.random;
  const escolhe = (lista) => lista[Math.floor(rng() * lista.length)];
  let baralho = [], ultima = "", pendente = null;
  const ultimaCtx = {};
  const st = {
    catalogo: cat,
    intervaloMs: Math.round(1000 * (Number(cat.intervalo_s) || 8)),
    reticencias: "…",
    primeira(texto) {
      const id = classificar(texto, cat);
      const opcoes = frasesDaCategoria(id, cat);
      const sem = opcoes.filter((f) => f !== ultimaCtx[id]);
      const frase = escolhe(sem.length ? sem : opcoes);
      ultimaCtx[id] = frase; ultima = frase;
      return frase;
    },
    proximaCrua() {
      if (!baralho.length) {
        baralho = cat.rotacao.slice();
        for (let i = baralho.length - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); [baralho[i], baralho[j]] = [baralho[j], baralho[i]]; }
        if (baralho.length > 1 && baralho[baralho.length - 1] === ultima) baralho.unshift(baralho.pop());
      }
      ultima = baralho.pop();
      return ultima;
    },
    // as do spinner ja saem com reticencias (o Qwen Code mostra o texto como vem)
    proxima() { return st.proximaCrua() + st.reticencias; },
    registrarPedido(texto) {
      const bruto = textoDoPedido(texto).trim();
      if (!bruto || "/!".includes(bruto[0])) return null;
      const frase = st.primeira(bruto);
      pendente = { frase, quando: Date.now() };
      return frase;
    },
    tomarPendente() {
      const p = pendente; pendente = null;
      return p && Date.now() - p.quando <= TTL_PENDENTE_MS ? p.frase : null;
    },
    primeiraOuProxima() {
      const p = st.tomarPendente();
      return p ? p + st.reticencias : st.proxima();
    },
  };
  return st;
}

let unico = null;
function padrao() { return (unico = unico || criar()); }

module.exports = {
  carregar, normalizar, textoDoPedido, classificar, frasesDaCategoria, criar,
  // a instancia do Qwen Code (o patch chama estes direto no modulo)
  get intervaloMs() { return padrao().intervaloMs; },
  registrarPedido: (t) => padrao().registrarPedido(t),
  primeiraOuProxima: () => padrao().primeiraOuProxima(),
  proxima: () => padrao().proxima(),
};

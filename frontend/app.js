/* AgendaFácil - Frontend da PoC (JavaScript puro, sem dependências) */
const app = document.getElementById("app");
const estado = { token: localStorage.getItem("af_token"), usuario: null,
  aba: "agendar", passo: 1, profissional: null, servico: null, data: "", hora: "", ultimo: null };

/* ---------- utilidades ---------- */
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const moeda = (v) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const hojeISO = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
function dataBR(iso) {
  const [a, m, d] = iso.split("-").map(Number);
  const dt = new Date(a, m - 1, d);
  return dt.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" });
}
function aviso(msg, erro = false) {
  const el = document.getElementById("aviso");
  el.textContent = msg; el.className = "aviso" + (erro ? " erro" : ""); el.hidden = false;
  clearTimeout(aviso.t); aviso.t = setTimeout(() => (el.hidden = true), 3500);
}
async function api(caminho, opcoes = {}) {
  const resp = await fetch("/api" + caminho, {
    method: opcoes.metodo || "GET",
    headers: { "Content-Type": "application/json", ...(estado.token ? { Authorization: "Bearer " + estado.token } : {}) },
    body: opcoes.corpo ? JSON.stringify(opcoes.corpo) : undefined,
  });
  const dados = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    if (resp.status === 401 && estado.token) sair(false);
    throw new Error(dados.erro || "Erro inesperado.");
  }
  return dados;
}
function sair(chamarApi = true) {
  if (chamarApi && estado.token) api("/logout", { metodo: "POST" }).catch(() => {});
  localStorage.removeItem("af_token");
  Object.assign(estado, { token: null, usuario: null, aba: "agendar", passo: 1, profissional: null, servico: null, data: "", hora: "" });
  render();
}
document.getElementById("btn-sair").addEventListener("click", () => sair());

/* ---------- autenticação ---------- */
function telaAuth(modo = "login") {
  const cad = modo === "cadastro";
  app.innerHTML = `
    <div class="card">
      <div class="abas">
        <button class="aba ${cad ? "" : "ativa"}" data-modo="login">Entrar</button>
        <button class="aba ${cad ? "ativa" : ""}" data-modo="cadastro">Criar conta</button>
      </div>
      <form id="form-auth" novalidate>
        ${cad ? `<label for="nome">Nome completo</label><input id="nome" autocomplete="name" required>
          <label for="perfil">Eu sou</label>
          <select id="perfil"><option value="cliente">Cliente</option><option value="profissional">Profissional</option></select>
          <div id="box-esp" hidden><label for="esp">Especialidade (ex.: Barbeiro)</label><input id="esp"></div>` : ""}
        <label for="email">E-mail</label><input id="email" type="email" autocomplete="email" required>
        <label for="senha">Senha</label><input id="senha" type="password" autocomplete="${cad ? "new-password" : "current-password"}" required>
        <div class="erro-campo" id="erro-auth"></div>
        <button class="btn" type="submit">${cad ? "Criar conta" : "Entrar"}</button>
      </form>
      ${cad ? "" : `<p class="suave" style="margin-top:14px">Contas de demonstração (senha <b>123456</b>):<br>
        Cliente: mariana@agendafacil.com<br>Profissional: carlos@agendafacil.com</p>`}
    </div>`;
  app.querySelectorAll(".aba").forEach((b) => b.addEventListener("click", () => telaAuth(b.dataset.modo)));
  if (cad) document.getElementById("perfil").addEventListener("change", (e) => (document.getElementById("box-esp").hidden = e.target.value !== "profissional"));
  document.getElementById("form-auth").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const v = (id) => document.getElementById(id).value;
    const corpo = { email: v("email"), senha: v("senha") };
    if (cad) { corpo.nome = v("nome"); corpo.perfil = v("perfil"); corpo.especialidade = v("esp"); }
    try {
      const r = await api(cad ? "/cadastro" : "/login", { metodo: "POST", corpo });
      estado.token = r.token; estado.usuario = r.usuario; localStorage.setItem("af_token", r.token);
      estado.aba = r.usuario.perfil === "cliente" ? "agendar" : "agenda"; estado.passo = 1;
      render();
    } catch (e) { document.getElementById("erro-auth").textContent = e.message; }
  });
}

/* ---------- CLIENTE: jornada de agendamento ---------- */
function abas(lista) {
  return `<div class="abas">${lista.map(([id, rot]) => `<button class="aba ${estado.aba === id ? "ativa" : ""}" data-aba="${id}">${rot}</button>`).join("")}</div>`;
}
function ligarAbas() {
  app.querySelectorAll("[data-aba]").forEach((b) => b.addEventListener("click", () => { estado.aba = b.dataset.aba; estado.passo = 1; render(); }));
}
function cabecalhoPasso(n, titulo) {
  return `<div class="passo">Passo ${n} de 4</div><div class="barra"><div style="width:${n * 25}%"></div></div><h2>${titulo}</h2>`;
}
function voltarBtn() { return `<button class="btn btn-sec" id="voltar">Voltar</button>`; }

async function telaCliente() {
  app.innerHTML = abas([["agendar", "Agendar"], ["meus", "Meus agendamentos"]]) + `<div id="conteudo"></div>`;
  ligarAbas();
  if (estado.aba === "meus") return meusAgendamentos();
  const box = document.getElementById("conteudo");
  try {
    if (estado.passo === 1) {
      const profs = await api("/profissionais");
      box.innerHTML = cabecalhoPasso(1, "Escolha o profissional") + profs.map((p) =>
        `<button class="opcao" data-id="${p.id}"><h3>${esc(p.nome)}</h3><span class="suave">${esc(p.especialidade || "Profissional")}</span></button>`).join("");
      box.querySelectorAll(".opcao").forEach((b) => b.addEventListener("click", () => {
        estado.profissional = profs.find((p) => p.id == b.dataset.id); estado.passo = 2; render();
      }));
    } else if (estado.passo === 2) {
      const servs = await api(`/profissionais/${estado.profissional.id}/servicos`);
      box.innerHTML = cabecalhoPasso(2, `Serviços de ${esc(estado.profissional.nome)}`) +
        (servs.length ? servs.map((s) => `<button class="opcao" data-id="${s.id}"><div class="linha"><h3>${esc(s.nome)}</h3><b>${moeda(s.preco)}</b></div>
          <span class="suave">Duração: ${s.duracao_min} min</span></button>`).join("") : `<p class="suave">Este profissional ainda não cadastrou serviços.</p>`) + voltarBtn();
      box.querySelectorAll(".opcao").forEach((b) => b.addEventListener("click", () => {
        estado.servico = servs.find((s) => s.id == b.dataset.id); estado.data = ""; estado.hora = ""; estado.passo = 3; render();
      }));
      document.getElementById("voltar").onclick = () => { estado.passo = 1; render(); };
    } else if (estado.passo === 3) {
      box.innerHTML = cabecalhoPasso(3, "Escolha data e horário") + `
        <div class="card"><label for="data">Data</label><input type="date" id="data" min="${hojeISO()}" value="${estado.data}">
        <div id="horarios" class="suave" style="margin-top:10px">Selecione uma data para ver os horários livres.</div></div>` + voltarBtn();
      document.getElementById("voltar").onclick = () => { estado.passo = 2; render(); };
      const carregar = async () => {
        const alvo = document.getElementById("horarios");
        if (!estado.data) return;
        const livres = await api(`/horarios?servico_id=${estado.servico.id}&data=${estado.data}`);
        alvo.className = "";
        alvo.innerHTML = livres.length ? `<div class="suave">Horários disponíveis em ${dataBR(estado.data)}:</div><div class="horarios">${livres.map((h) => `<button class="chip" data-h="${h}">${h}</button>`).join("")}</div>`
          : `<p class="suave">Nenhum horário livre nesta data. Tente outro dia.</p>`;
        alvo.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => { estado.hora = c.dataset.h; estado.passo = 4; render(); }));
      };
      document.getElementById("data").addEventListener("change", (e) => { estado.data = e.target.value; carregar().catch((er) => aviso(er.message, true)); });
      if (estado.data) carregar();
    } else if (estado.passo === 4) {
      box.innerHTML = cabecalhoPasso(4, "Confirme o agendamento") + `<div class="card"><dl class="resumo">
        <dt>Profissional</dt><dd>${esc(estado.profissional.nome)}</dd>
        <dt>Serviço</dt><dd>${esc(estado.servico.nome)} (${estado.servico.duracao_min} min)</dd>
        <dt>Valor</dt><dd>${moeda(estado.servico.preco)}</dd>
        <dt>Data</dt><dd>${dataBR(estado.data)}</dd><dt>Horário</dt><dd>${estado.hora}</dd></dl>
        <button class="btn" id="confirmar">Confirmar agendamento</button>${voltarBtn()}</div>`;
      document.getElementById("voltar").onclick = () => { estado.passo = 3; render(); };
      document.getElementById("confirmar").onclick = async (ev) => {
        ev.target.disabled = true;
        try {
          estado.ultimo = await api("/agendamentos", { metodo: "POST", corpo: { servico_id: estado.servico.id, data: estado.data, hora: estado.hora } });
          estado.passo = 5; render();
        } catch (e) { aviso(e.message, true); ev.target.disabled = false; if (/dispon/.test(e.message)) { estado.passo = 3; render(); } }
      };
    } else {
      const a = estado.ultimo;
      box.innerHTML = `<div class="card sucesso"><div class="icone">✅</div><h2>Agendamento confirmado!</h2>
        <dl class="resumo"><dt>Profissional</dt><dd>${esc(a.profissional)}</dd><dt>Serviço</dt><dd>${esc(a.servico)}</dd>
        <dt>Data</dt><dd>${dataBR(a.data)}</dd><dt>Horário</dt><dd>${a.hora}</dd></dl>
        <button class="btn" id="novo">Fazer novo agendamento</button>
        <button class="btn btn-sec" id="ver">Ver meus agendamentos</button></div>`;
      document.getElementById("novo").onclick = () => { estado.passo = 1; render(); };
      document.getElementById("ver").onclick = () => { estado.aba = "meus"; render(); };
    }
  } catch (e) { aviso(e.message, true); }
}

function cartaoAgendamento(a, mostrarCliente) {
  return `<div class="card"><div class="linha"><h3>${esc(a.servico)} • ${a.hora}</h3><span class="selo ${a.status}">${a.status}</span></div>
    <div class="suave">${mostrarCliente ? "Cliente: " + esc(a.cliente) : "Profissional: " + esc(a.profissional)}<br>
    ${dataBR(a.data)} • ${a.duracao_min} min • ${moeda(a.preco)}</div>
    ${a.status === "confirmado" ? `<button class="btn-perigo" data-cancelar="${a.id}">Cancelar</button>` : ""}</div>`;
}
async function carregarAgendamentos(mostrarCliente, vazio) {
  const box = document.getElementById("conteudo");
  const lista = await api("/agendamentos");
  const hoje = hojeISO();
  const proximos = lista.filter((a) => a.status === "confirmado" && a.data >= hoje);
  const historico = lista.filter((a) => !(a.status === "confirmado" && a.data >= hoje)).reverse();
  box.innerHTML = `<h2>Próximos atendimentos</h2>` +
    (proximos.length ? proximos.map((a) => cartaoAgendamento(a, mostrarCliente)).join("") : `<p class="suave">${vazio}</p>`) +
    (historico.length ? `<h2 style="margin-top:20px">Histórico</h2>` + historico.map((a) => cartaoAgendamento(a, mostrarCliente)).join("") : "");
  box.querySelectorAll("[data-cancelar]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("Deseja realmente cancelar este agendamento?")) return;
    try { await api("/agendamentos/" + b.dataset.cancelar, { metodo: "DELETE" }); aviso("Agendamento cancelado."); carregarAgendamentos(mostrarCliente, vazio); }
    catch (e) { aviso(e.message, true); }
  }));
}
const meusAgendamentos = () => carregarAgendamentos(false, "Você ainda não tem agendamentos.").catch((e) => aviso(e.message, true));

/* ---------- PROFISSIONAL: agenda e serviços ---------- */
async function telaProfissional() {
  app.innerHTML = abas([["agenda", "Minha agenda"], ["servicos", "Meus serviços"]]) + `<div id="conteudo"></div>`;
  ligarAbas();
  const box = document.getElementById("conteudo");
  try {
    if (estado.aba === "agenda") return await carregarAgendamentos(true, "Nenhum atendimento agendado.");
    const servs = await api(`/profissionais/${estado.usuario.id}/servicos`);
    box.innerHTML = `<h2>Cadastrar serviço</h2><form class="card" id="form-serv" novalidate>
      <label for="s-nome">Nome do serviço</label><input id="s-nome" required>
      <div class="linha-form"><div style="flex:1"><label for="s-preco">Preço (R$)</label><input id="s-preco" type="number" min="0" step="0.01" required></div>
      <div style="flex:1"><label for="s-dur">Duração (min)</label><input id="s-dur" type="number" min="5" step="5" required></div></div>
      <button class="btn" type="submit">Adicionar serviço</button></form>
      <h2>Serviços cadastrados</h2>` + (servs.length ? servs.map((s) => `<div class="card linha"><div><h3>${esc(s.nome)}</h3>
      <span class="suave">${moeda(s.preco)} • ${s.duracao_min} min</span></div><button class="btn-perigo" data-rm="${s.id}">Remover</button></div>`).join("") : `<p class="suave">Nenhum serviço cadastrado.</p>`);
    document.getElementById("form-serv").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        await api("/servicos", { metodo: "POST", corpo: { nome: document.getElementById("s-nome").value, preco: document.getElementById("s-preco").value, duracao_min: document.getElementById("s-dur").value } });
        aviso("Serviço cadastrado!"); telaProfissional();
      } catch (e) { aviso(e.message, true); }
    });
    box.querySelectorAll("[data-rm]").forEach((b) => b.addEventListener("click", async () => {
      try { await api("/servicos/" + b.dataset.rm, { metodo: "DELETE" }); telaProfissional(); } catch (e) { aviso(e.message, true); }
    }));
  } catch (e) { aviso(e.message, true); }
}

/* ---------- inicialização ---------- */
async function render() {
  const topo = document.getElementById("usuario-topo");
  if (!estado.token) { topo.hidden = true; return telaAuth(); }
  if (!estado.usuario) {
    try { estado.usuario = await api("/me"); estado.aba = estado.usuario.perfil === "cliente" ? "agendar" : "agenda"; }
    catch { return telaAuth(); }
  }
  document.getElementById("nome-topo").textContent = estado.usuario.nome.split(" ")[0];
  topo.hidden = false;
  estado.usuario.perfil === "cliente" ? telaCliente() : telaProfissional();
}
render();

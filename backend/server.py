"""
AgendaFácil - Backend da Prova de Conceito (PoC)
API REST em Python puro (biblioteca padrão) + SQLite.
Não requer instalação de dependências.

Executar:  python backend/server.py
Acessar:   http://localhost:8000
"""
import hashlib
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("AGENDAFACIL_DB", os.path.join(BASE_DIR, "database", "agendafacil.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
FRONT_DIR = os.path.join(BASE_DIR, "frontend")
PORT = int(os.environ.get("PORT", "8000"))
PASSO_MIN = 30  # intervalo entre horários oferecidos (minutos)
lock_agendamento = threading.Lock()


# ---------------------------------------------------------------- Banco ----
def conectar():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def gerar_hash(senha, salt):
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), 120_000).hex()


def criar_usuario(db, nome, email, senha, perfil, especialidade=None):
    salt = secrets.token_hex(16)
    cur = db.execute(
        "INSERT INTO usuarios (nome, email, senha_hash, salt, perfil, especialidade) VALUES (?,?,?,?,?,?)",
        (nome, email.lower(), gerar_hash(senha, salt), salt, perfil, especialidade),
    )
    return cur.lastrowid


def iniciar_banco():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = conectar()
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        db.executescript(f.read())
    if db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
        popular_dados_iniciais(db)
    db.commit()
    db.close()


def popular_dados_iniciais(db):
    """Dados de demonstração baseados nas personas do projeto."""
    criar_usuario(db, "Mariana Souza", "mariana@agendafacil.com", "123456", "cliente")
    carlos = criar_usuario(db, "Carlos Mendes", "carlos@agendafacil.com", "123456", "profissional", "Barbeiro")
    ana = criar_usuario(db, "Ana Paula Lima", "ana@agendafacil.com", "123456", "profissional", "Manicure")
    servicos = [
        (carlos, "Corte de cabelo", 40.0, 30), (carlos, "Barba", 25.0, 30), (carlos, "Corte + Barba", 60.0, 60),
        (ana, "Manicure", 35.0, 60), (ana, "Pedicure", 40.0, 60),
    ]
    db.executemany("INSERT INTO servicos (profissional_id, nome, preco, duracao_min) VALUES (?,?,?,?)", servicos)
    for prof in (carlos, ana):
        for dia in range(0, 6):  # segunda a sábado
            fim = "17:00" if dia == 5 else "18:00"
            db.execute(
                "INSERT INTO disponibilidade (profissional_id, dia_semana, hora_inicio, hora_fim) VALUES (?,?,?,?)",
                (prof, dia, "09:00", fim),
            )


# ------------------------------------------------------------- Regras ----
def para_min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def para_hhmm(minutos):
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


class ApiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status, self.msg = status, msg


def validar_data(texto):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        raise ApiError(400, "Data inválida. Use o formato AAAA-MM-DD.")


def calcular_horarios(db, servico_id, data_txt):
    """Horários livres: dentro da disponibilidade, sem sobrepor outros
    agendamentos (considerando a duração do serviço) e sem passar do fim do expediente."""
    servico = db.execute("SELECT * FROM servicos WHERE id=? AND ativo=1", (servico_id,)).fetchone()
    if not servico:
        raise ApiError(404, "Serviço não encontrado.")
    dia = validar_data(data_txt)
    hoje = date.today()
    if dia < hoje:
        return []
    duracao = servico["duracao_min"]
    prof_id = servico["profissional_id"]
    janelas = db.execute(
        "SELECT hora_inicio, hora_fim FROM disponibilidade WHERE profissional_id=? AND dia_semana=?",
        (prof_id, dia.weekday()),
    ).fetchall()
    ocupados = [
        (para_min(r["hora"]), para_min(r["hora"]) + r["duracao_min"])
        for r in db.execute(
            """SELECT a.hora, s.duracao_min FROM agendamentos a
               JOIN servicos s ON s.id = a.servico_id
               WHERE a.profissional_id=? AND a.data=? AND a.status='confirmado'""",
            (prof_id, data_txt),
        )
    ]
    agora = datetime.now()
    minuto_atual = agora.hour * 60 + agora.minute
    livres = []
    for j in janelas:
        t, fim = para_min(j["hora_inicio"]), para_min(j["hora_fim"])
        while t + duracao <= fim:
            conflito = any(t < b_fim and t + duracao > b_ini for b_ini, b_fim in ocupados)
            passou = dia == hoje and t <= minuto_atual
            if not conflito and not passou:
                livres.append(para_hhmm(t))
            t += PASSO_MIN
    return livres


def agendamento_json(r):
    return {
        "id": r["id"], "data": r["data"], "hora": r["hora"], "status": r["status"],
        "servico": r["servico_nome"], "preco": r["preco"], "duracao_min": r["duracao_min"],
        "profissional": r["prof_nome"], "cliente": r["cli_nome"],
    }


SQL_AGENDAMENTO = """
    SELECT a.id, a.data, a.hora, a.status, s.nome AS servico_nome, s.preco, s.duracao_min,
           p.nome AS prof_nome, c.nome AS cli_nome
    FROM agendamentos a
    JOIN servicos s ON s.id = a.servico_id
    JOIN usuarios p ON p.id = a.profissional_id
    JOIN usuarios c ON c.id = a.cliente_id
"""


# --------------------------------------------------------------- Rotas ----
def exigir_usuario(handler, db, perfil=None):
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise ApiError(401, "Faça login para continuar.")
    usuario = db.execute(
        "SELECT u.* FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id WHERE s.token=?", (auth[7:],)
    ).fetchone()
    if not usuario:
        raise ApiError(401, "Sessão inválida ou expirada.")
    if perfil and usuario["perfil"] != perfil:
        raise ApiError(403, f"Ação permitida apenas para {perfil}.")
    return usuario


def abrir_sessao(db, usuario_id):
    token = secrets.token_hex(24)
    db.execute("INSERT INTO sessoes (token, usuario_id, criado_em) VALUES (?,?,?)",
               (token, usuario_id, datetime.now().isoformat(timespec="seconds")))
    db.commit()
    return token


def usuario_json(u):
    return {"id": u["id"], "nome": u["nome"], "email": u["email"], "perfil": u["perfil"],
            "especialidade": u["especialidade"]}


def rotear(h, db, metodo, caminho, query, corpo):
    if metodo == "POST" and caminho == "/api/cadastro":
        nome = (corpo.get("nome") or "").strip()
        email = (corpo.get("email") or "").strip().lower()
        senha = corpo.get("senha") or ""
        perfil = corpo.get("perfil")
        if len(nome) < 3:
            raise ApiError(400, "Informe o nome completo.")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ApiError(400, "E-mail inválido.")
        if len(senha) < 6:
            raise ApiError(400, "A senha deve ter pelo menos 6 caracteres.")
        if perfil not in ("cliente", "profissional"):
            raise ApiError(400, "Perfil inválido.")
        if db.execute("SELECT 1 FROM usuarios WHERE email=?", (email,)).fetchone():
            raise ApiError(409, "Este e-mail já está cadastrado.")
        especialidade = (corpo.get("especialidade") or "").strip() or None
        uid = criar_usuario(db, nome, email, senha, perfil, especialidade if perfil == "profissional" else None)
        if perfil == "profissional":  # horário padrão: segunda a sexta, 09h às 18h
            for dia in range(0, 5):
                db.execute("INSERT INTO disponibilidade (profissional_id, dia_semana, hora_inicio, hora_fim) "
                           "VALUES (?,?,?,?)", (uid, dia, "09:00", "18:00"))
        db.commit()
        u = db.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        return 201, {"token": abrir_sessao(db, uid), "usuario": usuario_json(u)}

    if metodo == "POST" and caminho == "/api/login":
        email = (corpo.get("email") or "").strip().lower()
        u = db.execute("SELECT * FROM usuarios WHERE email=?", (email,)).fetchone()
        if not u or not secrets.compare_digest(u["senha_hash"], gerar_hash(corpo.get("senha") or "", u["salt"])):
            raise ApiError(401, "E-mail ou senha incorretos.")
        return 200, {"token": abrir_sessao(db, u["id"]), "usuario": usuario_json(u)}

    if metodo == "POST" and caminho == "/api/logout":
        auth = h.headers.get("Authorization", "")[7:]
        db.execute("DELETE FROM sessoes WHERE token=?", (auth,))
        db.commit()
        return 200, {"ok": True}

    if metodo == "GET" and caminho == "/api/me":
        return 200, usuario_json(exigir_usuario(h, db))

    if metodo == "GET" and caminho == "/api/profissionais":
        exigir_usuario(h, db)
        rows = db.execute("SELECT * FROM usuarios WHERE perfil='profissional' ORDER BY nome").fetchall()
        return 200, [usuario_json(r) for r in rows]

    m = re.fullmatch(r"/api/profissionais/(\d+)/servicos", caminho)
    if metodo == "GET" and m:
        exigir_usuario(h, db)
        rows = db.execute("SELECT id, nome, preco, duracao_min FROM servicos "
                          "WHERE profissional_id=? AND ativo=1 ORDER BY nome", (int(m.group(1)),)).fetchall()
        return 200, [dict(r) for r in rows]

    if metodo == "POST" and caminho == "/api/servicos":
        prof = exigir_usuario(h, db, "profissional")
        nome = (corpo.get("nome") or "").strip()
        try:
            preco, duracao = float(corpo.get("preco")), int(corpo.get("duracao_min"))
        except (TypeError, ValueError):
            raise ApiError(400, "Preço e duração devem ser numéricos.")
        if not nome or preco < 0 or duracao <= 0 or duracao > 480:
            raise ApiError(400, "Dados do serviço inválidos.")
        cur = db.execute("INSERT INTO servicos (profissional_id, nome, preco, duracao_min) VALUES (?,?,?,?)",
                         (prof["id"], nome, preco, duracao))
        db.commit()
        return 201, {"id": cur.lastrowid, "nome": nome, "preco": preco, "duracao_min": duracao}

    m = re.fullmatch(r"/api/servicos/(\d+)", caminho)
    if metodo == "DELETE" and m:
        prof = exigir_usuario(h, db, "profissional")
        cur = db.execute("UPDATE servicos SET ativo=0 WHERE id=? AND profissional_id=?", (int(m.group(1)), prof["id"]))
        db.commit()
        if cur.rowcount == 0:
            raise ApiError(404, "Serviço não encontrado.")
        return 200, {"ok": True}

    if metodo == "GET" and caminho == "/api/horarios":
        exigir_usuario(h, db)
        try:
            servico_id = int(query.get("servico_id", [""])[0])
        except ValueError:
            raise ApiError(400, "Informe servico_id.")
        return 200, calcular_horarios(db, servico_id, query.get("data", [""])[0])

    if metodo == "POST" and caminho == "/api/agendamentos":
        cliente = exigir_usuario(h, db, "cliente")
        try:
            servico_id = int(corpo.get("servico_id"))
        except (TypeError, ValueError):
            raise ApiError(400, "Informe o serviço.")
        data_txt, hora = corpo.get("data"), corpo.get("hora")
        with lock_agendamento:  # evita duas reservas simultâneas do mesmo horário
            livres = calcular_horarios(db, servico_id, data_txt)
            if hora not in livres:
                raise ApiError(409, "Este horário não está mais disponível. Escolha outro.")
            serv = db.execute("SELECT profissional_id FROM servicos WHERE id=?", (servico_id,)).fetchone()
            try:
                cur = db.execute(
                    "INSERT INTO agendamentos (cliente_id, profissional_id, servico_id, data, hora, criado_em) "
                    "VALUES (?,?,?,?,?,?)",
                    (cliente["id"], serv["profissional_id"], servico_id, data_txt, hora,
                     datetime.now().isoformat(timespec="seconds")),
                )
                db.commit()
            except sqlite3.IntegrityError:
                raise ApiError(409, "Este horário não está mais disponível. Escolha outro.")
        r = db.execute(SQL_AGENDAMENTO + " WHERE a.id=?", (cur.lastrowid,)).fetchone()
        return 201, agendamento_json(r)

    if metodo == "GET" and caminho == "/api/agendamentos":
        u = exigir_usuario(h, db)
        campo = "a.cliente_id" if u["perfil"] == "cliente" else "a.profissional_id"
        rows = db.execute(SQL_AGENDAMENTO + f" WHERE {campo}=? ORDER BY a.data, a.hora", (u["id"],)).fetchall()
        return 200, [agendamento_json(r) for r in rows]

    m = re.fullmatch(r"/api/agendamentos/(\d+)", caminho)
    if metodo == "DELETE" and m:
        u = exigir_usuario(h, db)
        campo = "cliente_id" if u["perfil"] == "cliente" else "profissional_id"
        cur = db.execute(f"UPDATE agendamentos SET status='cancelado' WHERE id=? AND {campo}=? "
                         "AND status='confirmado'", (int(m.group(1)), u["id"]))
        db.commit()
        if cur.rowcount == 0:
            raise ApiError(404, "Agendamento não encontrado.")
        return 200, {"ok": True}

    raise ApiError(404, "Rota não encontrada.")


# ------------------------------------------------------------- Servidor ----
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{datetime.now():%H:%M:%S}] {self.address_string()} {fmt % args}")

    def _json(self, status, payload):
        corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _estatico(self, caminho):
        if caminho in ("", "/"):
            caminho = "/index.html"
        alvo = os.path.normpath(os.path.join(FRONT_DIR, caminho.lstrip("/")))
        if not alvo.startswith(FRONT_DIR) or not os.path.isfile(alvo):
            return self._json(404, {"erro": "Página não encontrada."})
        tipo = mimetypes.guess_type(alvo)[0] or "application/octet-stream"
        with open(alvo, "rb") as f:
            dados = f.read()
        self.send_response(200)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8" if tipo.startswith("text") or "javascript" in tipo else tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _tratar(self, metodo):
        url = urlparse(self.path)
        if not url.path.startswith("/api/"):
            if metodo == "GET":
                return self._estatico(url.path)
            return self._json(405, {"erro": "Método não permitido."})
        db = conectar()
        try:
            corpo = {}
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho:
                try:
                    corpo = json.loads(self.rfile.read(tamanho))
                except json.JSONDecodeError:
                    raise ApiError(400, "JSON inválido.")
            status, payload = rotear(self, db, metodo, url.path, parse_qs(url.query), corpo)
            self._json(status, payload)
        except ApiError as e:
            self._json(e.status, {"erro": e.msg})
        except Exception as e:  # noqa
            print("ERRO:", repr(e))
            self._json(500, {"erro": "Erro interno do servidor."})
        finally:
            db.close()

    def do_GET(self): self._tratar("GET")
    def do_POST(self): self._tratar("POST")
    def do_DELETE(self): self._tratar("DELETE")


if __name__ == "__main__":
    iniciar_banco()
    print(f"AgendaFácil rodando em http://localhost:{PORT}  (Ctrl+C para parar)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

-- AgendaFácil - Modelagem de dados (SQLite)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    senha_hash    TEXT NOT NULL,
    salt          TEXT NOT NULL,
    perfil        TEXT NOT NULL CHECK (perfil IN ('cliente', 'profissional')),
    especialidade TEXT
);

CREATE TABLE IF NOT EXISTS sessoes (
    token      TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    criado_em  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS servicos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    profissional_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nome            TEXT NOT NULL,
    preco           REAL NOT NULL CHECK (preco >= 0),
    duracao_min     INTEGER NOT NULL CHECK (duracao_min > 0),
    ativo           INTEGER NOT NULL DEFAULT 1
);

-- dia_semana segue a convenção do Python: 0 = segunda ... 6 = domingo
CREATE TABLE IF NOT EXISTS disponibilidade (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    profissional_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    dia_semana      INTEGER NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),
    hora_inicio     TEXT NOT NULL,
    hora_fim        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agendamentos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id      INTEGER NOT NULL REFERENCES usuarios(id),
    profissional_id INTEGER NOT NULL REFERENCES usuarios(id),
    servico_id      INTEGER NOT NULL REFERENCES servicos(id),
    data            TEXT NOT NULL,   -- AAAA-MM-DD
    hora            TEXT NOT NULL,   -- HH:MM
    status          TEXT NOT NULL DEFAULT 'confirmado' CHECK (status IN ('confirmado', 'cancelado')),
    criado_em       TEXT NOT NULL
);

-- Garante no banco que dois clientes não ocupem o mesmo início de horário
CREATE UNIQUE INDEX IF NOT EXISTS ux_agendamento_horario
    ON agendamentos (profissional_id, data, hora) WHERE status = 'confirmado';

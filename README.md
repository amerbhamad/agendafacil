# 📅 AgendaFácil — Prova de Conceito (PoC)

Sistema Web responsivo de agendamento para profissionais autônomos e pequenos prestadores de serviços.

**Projeto Integrador – SENAC EAD – Análise e Desenvolvimento de Sistemas – 2ª Entrega**
**Professor:** Anderson Clayton Garcia Lopes · **Grupo 48**

## 👥 Integrantes

| Nome |
|---|
| Luis Antonio Souza dos Santos |
| Matheus Oliveira da Hora |
| Marcus Vinicius Almeida Francisco de Souza |
| João Vitor Alves Maia |
| Amer Wael Bintencourt Hamad |
| Dilan Yuri Rosa Estevão |

## 🎯 Jornada escolhida para a PoC

**"Cliente agenda um serviço com um profissional"** (jornada da persona Mariana Souza, definida na 1ª entrega) e
**"Profissional acompanha sua agenda"** (persona Carlos Mendes).

| Etapa da jornada (1ª entrega) | Onde está na PoC |
|---|---|
| 2–3. Acesso e identificação | Tela de login / cadastro |
| 4. Seleciona o profissional | Passo 1 do agendamento |
| 5. Seleciona o serviço (valor e duração) | Passo 2 |
| 6–7. Data e horário (somente horários livres) | Passo 3 |
| 8. Confirmação | Passo 4 |
| 9. Finalização (resumo do agendamento) | Tela de sucesso + "Meus agendamentos" |
| Resultado: Carlos recebe o compromisso | Aba "Minha agenda" do profissional |

**Risco técnico validado:** impedir conflitos de horário respeitando a **duração de cada serviço**
(ex.: um serviço de 60 min às 10h bloqueia também 10h30 para um serviço de 30 min).

## 🧱 Stack tecnológica

| Camada | Tecnologia | Motivo |
|---|---|---|
| Frontend | HTML5 + CSS3 + JavaScript (puro), mobile-first | Responsivo, sem build, roda direto no navegador |
| Backend | Python 3.10+ (biblioteca padrão), API REST em JSON | Zero dependências: facilita executar e avaliar |
| Banco de dados | SQLite | Relacional, embarcado, modelo em `database/schema.sql` |
| Testes | `unittest` (Python) | 8 testes automatizados da API |
| Versionamento | Git + GitHub | Histórico de contribuição de cada membro |

## 🗂️ Estrutura do repositório

```
AgendaFacil/
├── backend/server.py        # API REST + servidor dos arquivos estáticos
├── frontend/                # index.html, style.css, app.js
├── database/schema.sql      # Modelagem de dados (o .db é criado automaticamente)
├── tests/test_api.py        # Testes automatizados
├── docs/                    # Relatório da 2ª entrega e roteiro do vídeo
└── README.md
```

## ▶️ Como executar (passo a passo)

**Pré-requisito:** Python 3.10 ou superior (`python --version`). Nenhuma biblioteca extra é necessária.

```bash
# 1. Clonar o repositório
git clone https://github.com/<usuario>/AgendaFacil.git
cd AgendaFacil

# 2. Subir o servidor (cria o banco e carrega os dados de demonstração na 1ª execução)
python backend/server.py          # no Linux/Mac, se necessário: python3 backend/server.py

# 3. Abrir no navegador
http://localhost:8000
```

Para trocar a porta: `PORT=9000 python backend/server.py` (Windows PowerShell: `$env:PORT=9000; python backend/server.py`).
Para recriar os dados de demonstração, apague o arquivo `database/agendafacil.db` e inicie o servidor novamente.

### Contas de demonstração (senha `123456`)

| Perfil | E-mail |
|---|---|
| Cliente (Mariana) | `mariana@agendafacil.com` |
| Profissional (Carlos, barbeiro) | `carlos@agendafacil.com` |
| Profissional (Ana, manicure) | `ana@agendafacil.com` |

### Roteiro rápido de teste
1. Entre como **Mariana** → Agendar → Carlos → "Corte de cabelo" → escolha um dia útil → horário **15:00** → Confirmar.
2. Tente agendar o mesmo horário de novo: ele não aparece mais na lista.
3. Saia e entre como **Carlos** → "Minha agenda": o atendimento da Mariana aparece.
4. Em "Meus serviços" cadastre um novo serviço; ele passa a aparecer para os clientes.

### Executar os testes
```bash
python tests/test_api.py
```

## 🔌 Endpoints da API

| Método | Rota | Descrição | Perfil |
|---|---|---|---|
| POST | `/api/cadastro` | Cria conta (cliente ou profissional) | público |
| POST | `/api/login` · `/api/logout` | Autenticação por token | público |
| GET | `/api/me` | Dados do usuário logado | logado |
| GET | `/api/profissionais` | Lista profissionais | logado |
| GET | `/api/profissionais/{id}/servicos` | Serviços do profissional | logado |
| POST / DELETE | `/api/servicos` · `/api/servicos/{id}` | Cadastra / remove serviço | profissional |
| GET | `/api/horarios?servico_id=&data=AAAA-MM-DD` | Horários livres | logado |
| POST | `/api/agendamentos` | Cria agendamento | cliente |
| GET | `/api/agendamentos` | Lista agendamentos (do cliente ou do profissional) | logado |
| DELETE | `/api/agendamentos/{id}` | Cancela agendamento | dono |

## 🗃️ Modelo de dados

`usuarios` 1—N `servicos` · `usuarios` 1—N `disponibilidade` · `usuarios` 1—N `agendamentos` · `servicos` 1—N `agendamentos` · `usuarios` 1—N `sessoes`.
Um índice único parcial impede dois agendamentos confirmados no mesmo início de horário para o mesmo profissional.
Detalhes em [`database/schema.sql`](database/schema.sql).

## 🔒 Segurança (nível PoC)
Senhas armazenadas com PBKDF2-SHA256 + salt; consultas SQL parametrizadas; escape de HTML no frontend; autorização por perfil nas rotas.

## 🚧 Escopo da PoC e próximos passos
**Fora da PoC (planejado):** tela de configuração de dias/horários do profissional (já existe no banco, com padrão seg–sáb),
confirmação por e-mail/WhatsApp, painel do administrador, suporte a estabelecimentos com vários profissionais, HTTPS e deploy em nuvem.

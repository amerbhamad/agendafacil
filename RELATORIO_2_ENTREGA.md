# AgendaFácil — Relatório da 2ª Entrega (Prova de Conceito)

> Use este texto para preencher o **template do Blackboard**. Troque `<link>` pelos links reais do GitHub e do vídeo.

**Curso:** Análise e Desenvolvimento de Sistemas · **Disciplina:** Projeto Integrador · **Professor:** Anderson Clayton Garcia Lopes
**Repositório GitHub:** `<link do repositório>` · **Vídeo (máx. 1 min):** `<link do vídeo>`

---

## 1. Definição da PoC (revisita do projeto) — 1,0 ponto

### 1.1 Revisita do projeto
Na 1ª entrega, o AgendaFácil foi descrito com onze funcionalidades previstas (cadastro e autenticação, cadastro de profissionais e serviços,
preço e duração, configuração de horários, consulta pelo cliente, agendamento e cancelamento, agenda do profissional, próximos atendimentos,
histórico e confirmação), além de stakeholders como administrador e pequenos estabelecimentos.
Ao revisitar o projeto, a equipe concluiu que construir tudo isso seria inviável no prazo e que **o maior risco técnico e de negócio não é o cadastro,
mas a regra central: oferecer ao cliente apenas horários realmente livres, sem gerar conflitos** — justamente a dor das personas (Carlos
"confunde horários" e Mariana "troca várias mensagens").

### 1.2 Melhorias justificadas em relação à 1ª entrega
| Ponto revisitado | Decisão | Justificativa |
|---|---|---|
| Escopo amplo (11 funcionalidades + administrador + estabelecimentos) | Reduzido a **uma jornada** | Exigência da PoC: provar o conceito, não entregar o produto completo |
| "Evitar conflitos de horário" (genérico) | Regra detalhada: o conflito considera a **duração do serviço** (sobreposição de intervalos) e o banco tem índice único contra reserva duplicada | Um corte de 30 min e um "corte + barba" de 60 min se sobrepõem mesmo com horários de início diferentes |
| Disponibilidade configurável | Modelada no banco, com padrão seg–sáb; tela de edição fica para a próxima fase | Não é necessária para validar a jornada |
| Confirmação do agendamento | Tela de confirmação com resumo + atualização imediata na agenda do profissional | Atende o "resultado da jornada" descrito na 1ª entrega |
| Notificações, administrador, estabelecimentos | Adiados | Não fazem parte do risco que a PoC precisa validar |

### 1.3 PoC definida
> **"Validar que um cliente consegue, pelo smartphone, agendar um serviço escolhendo apenas entre horários livres, e que o profissional
> visualiza o atendimento em sua agenda, sem conflitos de horário."**

**Jornada selecionada:** a da persona **Mariana Souza** (agendar) combinada ao resultado para **Carlos Mendes** (agenda).
**Critérios de sucesso:** (1) fluxo login → profissional → serviço → data/horário → confirmação funciona; (2) um horário reservado deixa de ser ofertado;
(3) conflitos por duração são bloqueados; (4) cancelamento libera o horário; (5) o profissional vê o agendamento.
Todos foram verificados por 8 testes automatizados (`python tests/test_api.py`) e pela demonstração em vídeo.

---

## 2. Preparação do ambiente — 2,0 pontos

### 2.1 Seleção da stack
| Camada | Escolha | Justificativa |
|---|---|---|
| Frontend | HTML, CSS e JavaScript puros, mobile-first | O projeto é Web responsiva com prioridade para smartphones; sem build, qualquer navegador executa |
| Backend | Python 3 (biblioteca padrão) com API REST/JSON | Linguagem conhecida pela equipe; zero dependências reduz erros de instalação |
| Banco | SQLite | Relacional, simples de versionar o esquema e suficiente para a PoC; migrável para PostgreSQL/MySQL |
| Controle de versão | Git/GitHub | Exigência da entrega e histórico por membro |

### 2.2 Arquitetura
Arquitetura cliente-servidor em 3 camadas: **Navegador (SPA)** → **API REST (Python)** → **SQLite**.
O frontend consome a API via `fetch` (JSON); a autenticação usa token enviado no cabeçalho `Authorization: Bearer`.
O mesmo servidor entrega os arquivos estáticos e a API (simplifica a execução).

### 2.3 Configuração da infraestrutura
- Repositório GitHub com estrutura de pastas `backend/`, `frontend/`, `database/`, `tests/`, `docs/`.
- Servidor de desenvolvimento: `python backend/server.py` (porta 8000, configurável por variável `PORT`).
- Banco criado automaticamente a partir de `database/schema.sql`, com dados de demonstração das personas.
- Todos os integrantes adicionados como colaboradores no GitHub.

---

## 3. Desenvolvimento do Frontend — 2,0 pontos
- Interface responsiva (mobile-first), com abas e barra de progresso de 4 passos que espelha a jornada documentada.
- Telas: login/cadastro; (cliente) escolha de profissional, serviço, data/horário, confirmação, sucesso e "Meus agendamentos" com cancelamento;
  (profissional) "Minha agenda" (próximos e histórico) e "Meus serviços" (cadastro/remoção).
- UX: só aparecem horários livres; mensagens de erro claras; confirmação antes de cancelar; foco visível e rótulos nos campos (acessibilidade);
  escape de HTML contra XSS.

## 4. Desenvolvimento do Backend — 2,0 pontos
- API REST com autenticação por token, autorização por perfil (cliente/profissional), validação de entradas e códigos HTTP adequados (400, 401, 403, 404, 409).
- Regra de negócio central em `calcular_horarios()`: gera horários dentro da disponibilidade, descarta sobreposições (considerando duração) e horários passados.
- Proteção contra corrida: trava (`Lock`) na criação + índice único parcial no banco.
- Senhas com PBKDF2-SHA256 + salt; SQL parametrizado.

### Modelagem de dados
Tabelas `usuarios`, `sessoes`, `servicos`, `disponibilidade` e `agendamentos` (ver `database/schema.sql`).

## 5. Testes e validação
| Teste | Resultado |
|---|---|
| Login inválido retorna 401 | ✔ |
| Rotas protegidas exigem autenticação | ✔ |
| Cadastro e bloqueio de e-mail duplicado (409) | ✔ |
| Jornada completa: agenda 15:00, horário some, 2ª tentativa 409, aparece na agenda do profissional, cancelamento libera | ✔ |
| Conflito por duração (60 min às 10:00 bloqueia 10:00 e 10:30) | ✔ |
| Data passada/inválida | ✔ |
| Perfis: profissional não agenda, cliente não cadastra serviço (403) | ✔ |
| Profissional cadastra serviço; dados inválidos retornam 400 | ✔ |

## 6. Vídeo de demonstração (máx. 1 minuto) — 1,0 ponto
Veja `docs/ROTEIRO_VIDEO.md`.

## 7. Repositório GitHub — 2,0 pontos
Código-fonte organizado, README com instruções de execução, todos os integrantes como membros e commits de cada um.

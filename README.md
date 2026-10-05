# 🏠 ImobiQ — Agente SDR Imobiliário com IA Generativa

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multiagente-1C3C3C)
![Claude](https://img.shields.io/badge/LLM-Claude%20(Anthropic)-D97757)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-bot-26A5E4?logo=telegram&logoColor=white)
![AWS](https://img.shields.io/badge/Deploy-AWS-FF9900?logo=amazonwebservices&logoColor=white)
![License](https://img.shields.io/badge/licen%C3%A7a-PolyForm%20Noncommercial%201.0.0-orange)

POC do **Hackathon FIAP — Pós Tech IA para Devs (Fase 5)** · Turma 8IADT · Grupo 65: um agente SDR para **imóveis comerciais** que atende empresas e investidores, conversa de forma humanizada, faz a qualificação B2B (atividade, espaço, orçamento, quem decide e prazo), sugere conjuntos, andares corporativos, lajes, prédios e galpões logísticos de uma base simulada (inspirada na carteira de uma imobiliária de real estate corporativo de São Paulo), agenda visitas com o corretor especialista, faz follow-up automático e envia resumos aos corretores. A base também tem alguns residenciais de alto padrão, e a Laris atende os dois segmentos.

> 🚧 Documentação completa (arquitetura, explicação da IA, demo e pitch) será finalizada ao longo do desenvolvimento.

---

## 🧱 Stack

| Camada | Tecnologia |
|---|---|
| 🧠 LLMs | Claude Sonnet 5 (conversa) · Claude Haiku 4.5 (roteamento, extração, resumo, follow-up) |
| 🕸️ Orquestração | LangGraph (supervisor + agentes especialistas, memória com checkpointer Postgres) |
| ⚙️ Backend | Python 3.12 · FastAPI · SQLAlchemy · Alembic |
| 🗄️ Dados | PostgreSQL 16 + pgvector |
| 🔎 RAG | Busca híbrida: embeddings locais (fastembed, MiniLM multilíngue) + full-text search em português, fundidos por RRF |
| 🖥️ Frontend | Next.js 16 · React 19 · TypeScript · Tailwind CSS 4 · lucide-react |
| 📈 Observabilidade | Langfuse |
| ☁️ Infra | Docker Compose · AWS |

## 🤖 Como o agente funciona

```mermaid
flowchart LR
    U([Mensagem do lead]) --> S[Supervisor<br/>Claude Haiku 4.5]
    S -->|extrai perfil, score e funil| CRM[(Postgres<br/>CRM + memória)]
    S -->|compra / aluguel| A1[Compra e Aluguel<br/>Claude Sonnet 5]
    S -->|investimento| A2[Investimentos<br/>Claude Sonnet 5]
    S -->|quer marcar| A3[Agendamento<br/>Claude Sonnet 5]
    A1 & A2 -->|tool use| T1[buscar_imoveis · detalhes_imovel<br/>RAG híbrido]
    A3 -->|tool use| T2[listar_horarios · agendar]
    A1 & A2 & A3 -.->|transferir_para_humano| H[Corretor + resumo]
    A3 -->|ao agendar| RES[Resumo para o corretor<br/>saída estruturada]
    J[[Job de follow-up<br/>APScheduler]] -->|lead sem resposta| F[Mensagem contextual<br/>cadência 2N, 4N...]
```

- **Supervisor (Haiku):** a cada mensagem, lê a conversa e devolve o perfil do lead em saída estruturada: segmento, empresa, cargo, se é o decisor, atividade, área ou nº de pessoas, requisitos, orçamento, região, urgência e perfil de investidor (no residencial, quartos). Regras determinísticas calculam campos faltantes (no comercial, seguindo o BANT: necessidade, orçamento, autoridade e prazo), score (0-100), temperatura e etapa do funil, e escolhem o agente que responde. O perfil registra só o que o cliente disse: a finalidade (compra, aluguel ou investimento) exige um trecho citado literalmente da mensagem do cliente, conferido pelo código, e a busca de imóveis fica travada até ela ser declarada. O telefone é obrigatório para confirmar uma visita: a ferramenta `agendar` recusa o horário enquanto ele não foi informado, e a Laris pede de novo. A visita só é agendada sem telefone se o cliente se recusar a informar (no Telegram, um botão envia o número com um toque).
- **Agentes (Sonnet):** persona humanizada ("Laris"), uma pergunta por vez, guiada pela lista de campos faltantes. *Locação e Compra* e *Investimentos* (imóveis locados, cap rate) qualificam e sugerem imóveis; *Agendamento* consulta a agenda do corretor especialista no tipo de imóvel (sedes corporativas, conjuntos, galpões, residenciais de alto padrão, ou o especialista em investimentos) e confirma visitas e reuniões. A busca entende a linguagem do cliente ("escritório", "sede", "andar", "CD", "Faria Lima", "JK", "Berrini", "Via Dutra") e filtra por atividade permitida, área, vagas, docas e pé-direito. Nos aluguéis, a Laris informa o custo mensal total (aluguel + condomínio + IPTU).
- **Resumo inteligente:** ao agendar ou encaminhar, o corretor recebe um briefing estruturado (perfil, necessidades, imóveis de interesse, objeções, próximos passos, abordagem sugerida) **por e-mail**, com o convite de calendário (.ics) da visita anexado. No modo demonstração, todos os e-mails vão para uma única caixa, com o corretor de destino no assunto.
- **Follow-up automático:** um job reserva leads sem resposta (`FOR UPDATE SKIP LOCKED`, seguro com várias instâncias) e envia mensagens com o contexto da conversa. Cada tentativa usa uma estratégia (retomar, agregar valor, encerrar), com cadência crescente; depois da última, o lead vai para *perdido*. Se ele voltar, a conversa continua de onde parou. O envio pode ser pausado, ter a cadência ajustada ou um horário de silêncio definido em tempo real na tela de configurações.
- **Memória:** o histórico completo (inclusive ferramentas e follow-ups) é o estado do grafo LangGraph, persistido no Postgres pelo checkpointer. A conversa continua mesmo após reiniciar a API.
- **Observabilidade:** com as chaves do Langfuse no `.env`, cada turno vira um trace agrupado por conversa, com os nós do grafo, cada chamada ao Claude (tokens, cache, latência) e cada ferramenta. A tela **Observabilidade** do ImobiQ não depende do Langfuse nem da cota da API dele: o app grava no próprio Postgres cada chamada ao Claude (agente, modelo, tokens por tipo, latência e custo pela tabela de preços da Anthropic), cada ferramenta e cada turno, e o painel lê de lá, convertendo para reais pela cotação do dia (PTAX do Banco Central): custo com IA, custo por conversa, **custo por visita agendada**, economia com prompt caching, tempo de resposta, custo por agente e por modelo, ferramentas usadas e tentativas de prompt injection. O detalhe fica no Langfuse: o menu e cada lead têm link direto para o projeto e para a sessão da conversa. Os testes gravam no banco de testes e no ambiente `test` do Langfuse, fora do painel.

### 💬 API

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/chat/sessions` | Inicia uma conversa (cria o lead) |
| `POST` | `/chat/{lead_id}/messages` | Envia mensagem; resposta via **SSE** (`analysis`, `agent`, `token`, `tool`, `properties`, `appointment`, `handoff`, `done`) |
| `GET` | `/chat/{lead_id}/messages` | Histórico da conversa (inclui follow-ups) |
| `GET` | `/leads` | Leads com score, temperatura e etapa do funil (filtros: `status`, `temperature`, `intent`) |
| `GET` | `/leads/{lead_id}` | Detalhe do lead: perfil, resumo, agendamentos e conversa |
| `POST` | `/leads/{lead_id}/summary` | Gera ou atualiza o resumo para o corretor |
| `POST` | `/leads/{lead_id}/summary/email` | Envia o resumo ao corretor por e-mail agora |
| `GET` | `/appointments` | Próximos agendamentos |
| `GET` | `/dashboard/metrics` | KPIs: funil, temperatura, intenção, agendamentos e follow-ups |
| `POST` | `/auth/login` | Troca a senha de administrador por um token de 12 horas (rotas `/config/*`, `/followups/run` e `/admin/*` exigem esse token quando há `ADMIN_PASSWORD`) |
| `GET` / `PUT` | `/config/ai` | Liga/desliga o uso das LLMs |
| `GET` / `PUT` | `/config/followup` | Lê/altera o follow-up em tempo real (liga/desliga, minutos, tentativas, horário de silêncio) |
| `GET` / `PUT` | `/config/email` | Lê/altera o envio de e-mails (liga/desliga, modo demonstração, caixa de demonstração) |
| `POST` | `/config/email/test` | Envia um e-mail de teste para validar o SMTP |
| `POST` | `/followups/run` | Dispara o ciclo de follow-up na hora, mesmo pausado (útil na demo) |
| `POST` | `/admin/demo/reset` | Apaga leads/conversas/agenda e recria os dados de demonstração |

## 🖥️ Telas

| Tela | O que mostra |
|---|---|
| 💬 **Chat do lead** (`/chat`) | Conversa no estilo WhatsApp com a Laris: resposta em streaming, indicador do que a IA está fazendo ("consultando imóveis…"), cards dos imóveis sugeridos, confirmação de agendamento e follow-ups que chegam sozinhos. Ao lado, o painel **"O que a IA está entendendo"** mostra em tempo real o agente ativo, score, temperatura, perfil extraído e as próximas perguntas da qualificação. |
| 📊 **Dashboard do corretor** (`/dashboard`) | Indicadores (leads, taxa de qualificação, quentes, agendamentos, follow-ups), funil por etapa, intenção dos leads, **canal de entrada** (chat ImobiQ, só site, só Telegram ou site → Telegram), próximos agendamentos e tabela de leads com filtros e o canal de cada lead. Atualiza sozinho a cada 10s. |
| 🗂️ **Detalhe do lead** (`/dashboard/leads/{id}`) | Resumo inteligente para o corretor (gerar/atualizar), status e histórico do e-mail ao corretor (com reenvio), perfil, agendamentos e a conversa completa (com a divisória "continuou no Telegram" no ponto em que o lead trocou de canal), com o agente que respondeu cada mensagem e os follow-ups marcados. |
| 🧩 **Chat no widget** (`/embed`) | Versão enxuta do chat usada dentro do iframe do widget, com a marca da imobiliária, saudação sobre o imóvel da página e botão de fechar. |
| 📈 **Observabilidade** (`/observability`) | Protegida pela senha de administrador. Visão sintética de 24h, 7 ou 30 dias: custo com IA (US$ e R$), custo por conversa e por visita agendada, economia com cache, tempo de resposta (mediana e p95), custo por dia, por modelo e por agente, ferramentas usadas e tentativas de prompt injection, com link para o Langfuse. |
| ⚙️ **Configurações** (`/configuration`) | Protegida pela senha de administrador (`ADMIN_PASSWORD`). **Liga/desliga do atendimento com IA**: pausado, nada chama o Claude (o chat, o widget e o Telegram respondem um recado fixo pedindo nome e telefone e guardam a mensagem; follow-ups e resumos param), para o site público não gastar tokens fora das demonstrações. Liga/desliga do follow-up com efeito imediato, minutos até a 1ª tentativa, máximo de tentativas, horário de silêncio e botão "rodar agora". Controla o e-mail aos corretores (liga/desliga, modo demonstração, e-mail de teste) e a cotação do dólar do painel de observabilidade (busca diária no Banco Central ligada/desligada e cotação fixa de reserva). Também reseta os dados de demonstração (8 leads em todas as etapas do funil, com conversas, resumos e agendamentos). |

A conversa fica salva no navegador (o lead é retomado ao recarregar); use **Nova conversa** para simular outro lead. Os atalhos iniciais do chat reproduzem os três cenários do enunciado.

## 🧩 Widget para sites de imobiliárias

A Laris pode ser instalada no site de qualquer imobiliária com uma linha, antes de `</body>`:

```html
<script src="https://SEU-APP/widget.js" data-brand="Nome da Imobiliária" data-property="IMV-007" defer></script>
```

- Uma bolha flutuante abre o chat num iframe (tela cheia no celular). O chat só carrega no primeiro clique, sem pesar no site, e o CSS fica isolado (Shadow DOM).
- A Laris se apresenta em nome da imobiliária (`data-brand`) e, na página de um imóvel (`data-property`), já abre falando dele e responde sobre "este imóvel".
- O dashboard mostra a origem do lead: site, página de entrada e campanha (UTM de primeiro toque).
- A conversa continua se o visitante recarregar ou mudar de página (a sessão fica guardada no domínio do site).
- Opcionais: `data-teaser-delay` (segundos até o convite aparecer; `0` desliga) e `data-position="left"`. API JavaScript: `ImobiQ.open()`, `ImobiQ.open({ message })` (abre o chat com a mensagem já digitada, para o visitante revisar e enviar), `ImobiQ.close()`, `ImobiQ.toggle()`.

O site fictício da **Imobiliária Exemplo** (`site-exemplo/`) é gerado a partir da mesma base de imóveis e serve de demonstração, com o visual de uma imobiliária de real estate corporativo: busca por pretensão (alugar, comprar, investir) e por código, cards com o código do imóvel, página do imóvel com pacote de locação e especificações técnicas, e o formulário "Fale com a imobiliária" e o "Encomende seu imóvel" abrindo a Laris com a mensagem pronta. Para produção, gere apontando para o widget publicado e suba a pasta `dist/` em qualquer hospedagem estática:

```bash
python site-exemplo/build.py --widget https://SEU-APP/widget.js
```

No WordPress, a linha do script pode ser colocada com um plugin de inserção de código no rodapé (ex.: WPCode).

## ✈️ Bot do Telegram

A mesma Laris atende pelo Telegram ([@imobiq_laris_bot](https://t.me/imobiq_laris_bot)), com a mesma memória, qualificação, busca e agenda do chat web:

- Cada conversa com o bot vira um lead com canal **Telegram** no dashboard; `/nova` recomeça o atendimento.
- "digitando…" enquanto ela pensa, respostas formatadas, imóveis citados com resumo, custo mensal total e link para o site, e **horários de visita como botões**.
- O follow-up de quem conversa pelo Telegram chega no próprio Telegram.
- **Continuar no Telegram:** o botão no chat (inclusive no widget do site) abre o bot já com a conversa, pelo link `t.me/<bot>?start=<token>` (token de uso único, válido por 30 minutos).
- Liga/desliga em tempo real e situação da conexão (com QR code para abrir o bot no celular) na tela de configurações.

Configuração: crie o bot no **@BotFather** e coloque o token em `TELEGRAM_BOT_TOKEN` no `.env`. Localmente a API usa **long polling** (não precisa de URL pública). Em produção, use `TELEGRAM_MODE=webhook` com `TELEGRAM_WEBHOOK_URL` (HTTPS) e `TELEGRAM_WEBHOOK_SECRET`: o Telegram passa a chamar `POST /webhooks/telegram`, e a API confere o segredo no cabeçalho de cada chamada. O token nunca aparece nos logs.

## 🔒 Segurança

- **Área de administração com senha** (`ADMIN_PASSWORD`): configurações e ações de demo exigem login; token assinado de 12 horas, invalidado ao trocar a senha.
- **Liga/desliga das LLMs:** fora das demonstrações, nada chama o Claude; o chat pede nome e telefone num formulário.
- **Limite de mensagens** (tela de configurações, em tempo real): por conversa, por IP, conversas novas por IP e um **teto diário** que funciona como trava de custo (acima dele, a Laris pausa a IA e pede o contato). Vale para o chat, o widget e o Telegram.
- **Domínios do widget** (tela de configurações): com a restrição ligada, o `widget.js` não mostra a bolha em sites fora da lista e o navegador bloqueia o chat embutido pela regra `frame-ancestors` do `/embed`; a API também recusa conversas vindas de outras páginas.
- **Prompt injection:** a mensagem do cliente é tratada como conversa, nunca como instrução; a Laris não revela o prompt, não sai do tema imobiliário e não promete condições fora da base. As ferramentas só consultam imóveis, a agenda e o próprio lead, então não há como chegar a dados de outros clientes. Tentativas típicas são detectadas, marcadas na mensagem e etiquetadas no Langfuse (`suspeita_injecao`).
- **Dados pessoais fora da observabilidade:** telefone, e-mail, CPF e CNPJ são mascarados antes de os traces irem para o Langfuse.
- **Segredos só no `.env`** (fora do Git); o token do Telegram nunca aparece nos logs.

## 📁 Estrutura

```
api/    FastAPI + agentes (app/), migrations (alembic/), seed (scripts/), testes (tests/)
web/    Next.js — chat do lead, dashboard do corretor, configurações e o widget (public/widget.js)
site-exemplo/  gerador do site fictício da "Imobiliária Exemplo", com o widget embutido
data/   base simulada: 76 imóveis (68 comerciais e 8 residenciais de alto padrão) em SP e região, com edifícios fictícios (gerador determinístico), corretores por especialidade e leads de demonstração
docs/   arquitetura, explicação da IA, deploy e pitch
deploy/ produção: docker-compose.prod.yml, Caddyfile, user data da EC2, políticas de IAM e script de deploy
.github/workflows/  CI (lint e testes) e deploy contínuo na AWS
```

## ☁️ Deploy na AWS

Push na `main` → **GitHub Actions** roda o CI (ruff, pytest com Postgres, eslint, next build) → publica as imagens no **Amazon ECR** → atualiza a **EC2** pelo **SSM Run Command** → teste de fumaça em `https://imobiq.arrtsoftware.com.br/api/health`.

- **Sem chaves da AWS no GitHub** (OIDC com credenciais temporárias) e **sem porta 22 aberta** (deploy pelo SSM, acesso pelo Session Manager).
- Na EC2, Docker Compose com **Caddy** (HTTPS automático): o app na raiz e a API em `/api`, no mesmo domínio.
- Segredos só no `.env` do servidor; migrations e seed automáticos a cada deploy.

Passo a passo completo (console da AWS, DNS na Hostinger, variáveis do GitHub, operação e custos): **[docs/deploy.md](docs/deploy.md)**.

## 🚀 Como rodar

Pré-requisitos: Docker Desktop. Para desenvolvimento local: Python 3.12 + [uv](https://docs.astral.sh/uv/) e Node 22.

```bash
cp .env.example .env              # preencha ANTHROPIC_API_KEY
python site-exemplo/build.py      # gera o site fictício (site-exemplo/dist)
docker compose up -d --build      # db + api + web + mailpit + site
docker compose exec api python -m scripts.seed --demo   # --demo: cria também os leads de exemplo
```

| Serviço | URL |
|---|---|
| 🖥️ Web | http://localhost:3001 |
| ⚙️ API (Swagger) | http://localhost:8001/docs |
| 📬 Mailpit (e-mails de teste) | http://localhost:8025 |
| 🏠 Site fictício com o widget | http://localhost:5500 |

> ℹ️ As portas 3000/8000 costumam estar ocupadas no Windows, por isso o padrão é 3001/8001 (configurável no `.env`).

### 🛠️ Desenvolvimento local (sem containerizar api/web)

```bash
docker compose up -d db
cd api && uv sync && uv run alembic upgrade head && uv run python -m scripts.seed
uv run uvicorn app.main:app --reload --port 8001
cd ../web && npm install && npm run dev
```

### ✅ Testes

```bash
cd api && uv run pytest     # requer o db rodando; usa um banco próprio (sdr_test), criado e semeado sozinho
RUN_LLM_TESTS=1 uv run pytest tests/test_agent_scenarios.py   # cenários do enunciado com o Claude (custa tokens)
uv run ruff check .
```

## 📄 Licença

Copyright © 2026 Rodrigo de Araujo Rosa. Distribuído sob a **[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)** (texto completo em [LICENSE](LICENSE)).

- ✅ **Permitido para fins não comerciais:** ler, rodar, estudar, avaliar e modificar o código, inclusive por instituições de ensino e pesquisa (ex.: avaliação do hackathon) e para uso pessoal.
- 🚫 **Não permitido sem autorização:** qualquer uso comercial, como oferecer o sistema ou partes dele como produto ou serviço, ou usá-lo na operação de uma empresa.
- 📌 Quem redistribuir o código precisa manter a licença e a linha `Required Notice` do arquivo [LICENSE](LICENSE).

Para licenciamento comercial, fale com o autor.

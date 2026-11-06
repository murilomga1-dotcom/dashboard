# Plano — App de cadastro automático de leilões no SIG

## Objetivo

App de desktop (.exe) que lê o edital, gera cabeçalho, datas e lotes com a API do Claude
e cadastra tudo sozinho no SIG (`sig.leiloesjudiciaisbrasil.com.br`).

## Entradas

- **Um ou mais editais** judiciais comuns (PDF, .docx ou .doc) — normalmente um por processo,
  todos da mesma sessão. **Um leilão no SIG = a sessão inteira** (confirmado).
- Planilha "Bens do Leilão" (colunas: Processo, Tipo do Bem, Nº Vistoria, ID Vistoria,
  Avaliação, Lance Mínimo, Descrição). Só entram as linhas com vistoria preenchida.

## Princípio central: a IA extrai, o código decide

| Quem | O quê |
|---|---|
| **IA (Claude)** | Ler o edital, extrair fatos (comarca, vara, leiloeiro, datas, venda direta, parcelamento…), escolher e redigir os blocos do cabeçalho, redigir as partes da descrição de cada lote, casar cada lote com a linha da planilha |
| **Código (regras fixas)** | Triagem do edital fora do padrão, leiloeiro conhecido/desconhecido, **cálculo dos ciclos** (dias úteis, feriados, recesso), **fuso** pela UF, **horário dos ciclos** por leiloeiro, **ordem dos lotes**, valores (vindos da planilha), limite de 56 caracteres do título, montagem do HTML com a formatação padrão, validações |

Motivo: datas e valores errados são o pior erro possível num leilão. Tudo o que é
algorítmico na skill `cadastrar-leilao-sig-completo` (references/datas-horarios.md e lotes.md)
virou código testado, e a IA não calcula nada disso.

## Regras (da skill `cadastrar-leilao-sig-completo` v4.3)

- Leiloeiros em `config/leiloeiros.json` (nome, apelidos, site, 0800, horário dos ciclos,
  venda direta sim/não). Joyce Ribeiro e Bruno Meireles: sem venda direta e sem ciclos.
  Leiloeiro desconhecido → o app para e avisa.
- Edital fora do padrão (Senad, Caixa, Alienações MS, Giordano, escaneado, Diário Oficial
  com vários editais) → avisa e não cadastra. Primeiro por palavras-chave (sem custo de API),
  depois confirmado pela IA.
- Imóvel sem Incra/CRI → só alerta.
- Calendário (feriados e recesso) em `config/calendario.json`. Data fora do calendário
  configurado → o app para e pede atualização (a skill manda "pedir a programação ao usuário").

## Execução no SIG (Fase 2/3)

- Chrome instalado na máquina, aberto pelo Playwright com perfil próprio salvo
  (`launch_persistent_context`). Sessão caiu (tela de login) → para e pede o login.
- Reaproveita os scripts JS da skill (`sig_scripts/*.js`) via `page.evaluate`, com a mesma
  restrição de telas permitidas.
- Erro por lote: pula só aquele e segue. Erro no cabeçalho ou nas datas: para tudo.
- Relatório na tela com processo, lote, o que faltou e o trecho do edital.
- Botão "tentar de novo" só nos lotes que falharam.

## Cuidados obrigatórios

- **Anti-duplicidade**: registro local SQLite com gravação em duas fases
  (`gravando` → `confirmado`). Estado `gravando` órfão (app caiu no meio) → "verificar no SIG",
  nunca regrava às cegas. Guarda o ID do leilão criado para continuar em vez de recriar.
- **Log**: uma pasta por execução com `execucao.log`, JSON da IA, relatório e prints de erro.
- Chave da API no Cofre de Credenciais do Windows (`keyring`), nunca em log.

## Fases

1. **Fase 1 — só leitura (feita):** ler edital e planilha, triagem, IA, ciclos/fuso/ordem,
   validações, HTML e tela de revisão. Não toca no SIG.
2. **Fase 2 — cabeçalho e datas (feita, testada num SIG falso local):** Chrome com perfil salvo,
   espera do login, scripts da skill via `page.evaluate`, correção dos interruptores iButton,
   ID do leilão pela URL, ciclos na aba Datas, registro em duas fases, retomada sem duplicar.
   **Falta validar no SIG real** os pontos que o SIG falso só imita: a classe do iButton
   (`ibutton-container`), a detecção da tela de login (campo de senha), o recarregamento da aba
   Datas depois de salvar e o redirecionamento para `edita-leilao/id/<ID>`. Primeira execução
   real: acompanhada, com um leilão que vá mesmo ser cadastrado.
3. **Fase 3:** lotes, erro por lote, relatório, "tentar de novo", anti-duplicidade.
4. **Fase 4:** .exe (PyInstaller), instalador, cofre da chave.

## Decisões provisórias (confirmar)

| Ponto | Padrão adotado | Onde mudar |
|---|---|---|
| Valores divergentes planilha × edital | Planilha vale; divergência vira alerta | `config/app.json` → `fonte_valores` |
| Tela de revisão antes de gravar | Obrigatória | `config/app.json` → `revisao_obrigatoria` |
| Vistoria com vários bens | Linhas com o mesmo processo + vistoria são **um lote só**, com avaliação e lance mínimo somados (confirmado no edital real: 3 equipamentos = 1 lote de R$ 26.000,00) | `planilha.agrupar` |
| Processo com várias vistorias | A IA casa lote ↔ vistoria pela descrição; o código confere que processo e vistoria existem e que nenhuma vistoria foi usada duas vezes | `lotes.cruzar` |
| Tipo do bem / aba no SIG | Vale a coluna "Tipo do Bem" da planilha (Imóveis / Veículos / Equipamentos); se a IA ler outro tipo, vira alerta | `planilha.TIPOS` |
| Formato do processo | Compara só os dígitos | `planilha.normalizar_processo` |

## O que o exemplo real mostrou (edital TJBA + bens_leilao_7817.xlsx)

- A planilha não tem coluna "ID Vistoria" (o app aceita sem ela) e o Nº Vistoria vem como texto.
- Uma vistoria reúne vários bens (até 10 linhas) e um processo pode ter duas vistorias de tipos
  diferentes (barco em "Veículos" + mesas em "Equipamentos").
- A planilha cobre uma sessão inteira ("JE Salvador/BA (Paulo) (tarde)", 16 processos), mas o
  processo do edital enviado (0056381-54.2016.8.05.0001) **não está nela**.

Com a planilha certa (bens_leilao_8268.xlsx, "JE Salvador/BA (Paulo) (manhã)") o processo do
edital está lá: vistoria 13816, 3 linhas, total R$ 26.000,00 / R$ 20.800,00 — igual ao edital.

## Sessão com vários editais

- Uma chamada à IA com todos os editais da sessão (cada um marcado pelo nome do arquivo).
  A IA monta **um** cabeçalho (blocos sem repetir; regra que vale só para alguns bens vira
  exceção citando o processo) e devolve também os fatos de cada edital.
- O código confere que todos os editais têm o mesmo leiloeiro, os mesmos encerramentos e a
  mesma venda direta (prazo e duração). Divergência → bloqueia (o SIG tem um cabeçalho e uma
  aba Datas por leilão).
- Um edital fora do padrão na sessão → bloqueia o leilão inteiro (conservador).
- Horário dos ciclos: padrão do leiloeiro (16:00), exceto os que já têm outro horário na tabela.

- Título com varas diferentes: todas as varas no título, na ordem dos editais, sem repetir
  (`JUSTIÇA ESTADUAL DE CIDADE/UF - 1ª VARA ... / 2ª VARA ...`), montado pelo código.
- SIG sem API nem importação: automação pela tela é o único caminho (confirmado).
- 1 computador: o registro anti-duplicidade fica local, em `registro.sqlite` (confirmado).
- Calendário 2027/2028: feriados e recesso além da tabela atual.

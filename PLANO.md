# Plano — App de cadastro automático de leilões no SIG

## Objetivo

App de desktop (.exe) que lê o edital, gera cabeçalho, datas e lotes com a API do Claude
e cadastra tudo sozinho no SIG (`sig.leiloesjudiciaisbrasil.com.br`).

## Entradas

- Edital judicial comum (PDF, .docx ou .doc)
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

1. **Fase 1 — só leitura (este commit):** ler edital e planilha, triagem, IA, ciclos/fuso/ordem,
   validações, HTML e tela de revisão. Não toca no SIG.
2. **Fase 2:** Playwright, login com perfil salvo, cadastro do cabeçalho e das datas.
3. **Fase 3:** lotes, erro por lote, relatório, "tentar de novo", anti-duplicidade.
4. **Fase 4:** .exe (PyInstaller), instalador, cofre da chave.

## Decisões provisórias (confirmar)

| Ponto | Padrão adotado | Onde mudar |
|---|---|---|
| Valores divergentes planilha × edital | Planilha vale; divergência vira alerta | `config/app.json` → `fonte_valores` |
| Tela de revisão antes de gravar | Obrigatória | `config/app.json` → `revisao_obrigatoria` |
| Processo com vários bens | A IA casa lote ↔ linha da planilha pela descrição; o código confere que processo e vistoria existem e que nenhuma linha foi usada duas vezes | `cruzamento.py` |
| Formato do processo | Compara só os dígitos | `planilha.normalizar_processo` |

## Pendências

- Exemplo real da planilha de vistorias (formato do nº do processo, mais de um bem por processo).
- O SIG tem API ou importação por planilha? (seria mais estável que automatizar a tela)
- Quantos PCs vão usar? (se mais de um, o registro anti-duplicidade precisa ser compartilhado)
- Calendário 2027/2028: feriados e recesso além da tabela atual.

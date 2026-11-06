# Leilão SIG

App de desktop que lê os editais de uma sessão de leilão judicial (um por processo) e a planilha "Bens do Leilão", prepara
cabeçalho, datas (ciclos da venda direta) e lotes com a API do Claude e — a partir da Fase 2 —
cadastra tudo no SIG. O plano completo está em [PLANO.md](PLANO.md).

**Estado atual: Fase 2.** O app prepara tudo para revisão e o botão **Gravar no SIG** cadastra o
cabeçalho e as datas (ciclos). Os lotes entram na Fase 3.

O cadastro usa o **Google Chrome instalado na máquina** (não precisa `playwright install`), com um
perfil próprio do app em `%LOCALAPPDATA%\LeilaoSIG\chrome-perfil`: o login do SIG é feito uma vez
nessa janela e fica salvo. Se a sessão cair, o app para e pede o login.

## Rodar (desenvolvimento)

```bash
pip install -e .[dev]          # no Windows: pip install -e .[dev,windows]
leilao-sig                     # abre a tela
python -m pytest               # testes (não usam a API; os do SIG usam um SIG falso local)
```

A chave da API do Claude fica no Cofre de Credenciais do Windows (botão **Chave da API…**).
Sem ela, o app usa a variável `ANTHROPIC_API_KEY`.

## Onde ficam as regras

| Arquivo | O que define |
|---|---|
| `src/leilao_sig/config/leiloeiros.json` | Leiloeiros conhecidos, site, 0800, horário dos ciclos, venda direta sim/não |
| `src/leilao_sig/config/calendario.json` | Feriados e tabela de recesso (atualizar todo ano) |
| `src/leilao_sig/config/triagem.json` | Termos que marcam edital fora do padrão |
| `src/leilao_sig/config/app.json` | Modelo, esforço, fonte dos valores (planilha/edital) |
| `src/leilao_sig/prompts/` | Instruções da IA e manuais de frases (vindos da skill `cadastrar-leilao-sig-completo`) |
| `src/leilao_sig/sig_scripts/` | Scripts JS da skill para preencher o SIG (Fase 2) |

Para mudar uma regra sem recompilar o .exe, copie o JSON para
`%LOCALAPPDATA%\LeilaoSIG\config\` e edite lá: essa cópia tem prioridade.

## Como funciona

1. Lê os editais da sessão (PDF, .docx; .doc via Word ou LibreOffice). PDF sem texto = escaneado → para.
2. Triagem por palavras-chave (Senad, Alienações MS, Giordano, vários editais) → para sem gastar API.
3. Lê a planilha; só entram linhas com Nº Vistoria. Linhas com o mesmo processo + vistoria são um lote só (valores somados). Processo comparado só pelos dígitos.
4. IA (Claude, saída JSON validada) extrai fatos, blocos do cabeçalho e textos dos lotes, e
   indica qual linha da planilha é cada lote.
5. O código valida e calcula: leiloeiro conhecido, editais da sessão com as mesmas datas/venda direta, datas, fuso, ciclos/recesso, horário dos
   ciclos, ordem dos lotes, valores (planilha), título ≤ 56, HTML com a formatação padrão.
6. Tela de revisão: relatório (erros/alertas com trecho do edital), cabeçalho, ciclos e lotes.

7. **Gravar no SIG** (depois de confirmar): preenche o formulário com os scripts da skill, corrige
   os interruptores, salva, anota o ID do leilão e cadastra os ciclos na aba Datas. Erro no
   cabeçalho ou nas datas para tudo (com print). O registro local (`registro.sqlite`) impede
   duplicar: rodar de novo continua de onde parou no mesmo leilão.

Cada execução grava `execucao.log`, a resposta da IA e a preparação em
`%LOCALAPPDATA%\LeilaoSIG\execucoes\<data_hora>\`.

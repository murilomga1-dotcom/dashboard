"""SIG falso para testar a automação sem tocar no SIG real.

Imita só o que os scripts da skill usam: nomes dos campos, interruptores iButton (clicar no
lado direito alterna), selects, modal "data contábil", TinyMCE (stub), aba Datas e login.
Começa com alguns interruptores fora do padrão para exercitar a correção.
"""

from __future__ import annotations

import html
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

JQUERY = (Path(__file__).parent / "jquery.min.js").read_bytes()

LIGADOS_INICIO = {"bn_exibeavaliacao", "bn_exibedesconto", "bn_finalizadonaodivulgado", "bn_exibeleilaovitrine",
                  "bn_fechamentoautomatico", "bn_destaque"}  # bn_segundoleilao desligado e bn_destaque ligado: fora do padrão
INTERRUPTORES = ["bn_segundoleilao", "bn_exibeavaliacao", "bn_exibedesconto", "bn_finalizadonaodivulgado",
                 "bn_exibeleilaovitrine", "bn_fechamentoautomatico", "bn_ocultaapelido", "bn_gravacao",
                 "bn_liberacaoonline", "bn_despesasadm", "bn_destaque", "bn_transmissaoaovivo"]

BASE_JS = """
<script src="/jquery.min.js"></script>
<script>
// TinyMCE falso: só o que leilao.js/lote.js usam
window.tinymce = { get: function (id) {
  var ta = document.getElementById(id), body = document.getElementById(id + '_body');
  if (!ta) return null;
  return {
    setContent: function (h) { body.innerHTML = h; },
    execCommand: function (c) { if (c === 'JustifyFull') body.querySelectorAll('p').forEach(function (p) { p.style.textAlign = 'justify'; }); },
    selection: { collapse: function () {} },
    save: function () { ta.value = body.innerHTML; },
    getContent: function () { return body.innerText; },
    getBody: function () { return body; }
  };
}};
// iButton falso: clique no lado direito alterna o checkbox
$(document).on('click', '.ibutton-container', function (ev) {
  var r = this.getBoundingClientRect();
  if (ev.clientX > r.left + r.width / 2) { var c = $(this).find('input[type=checkbox]'); c.prop('checked', !c.prop('checked')).trigger('change'); }
});
</script>
<style>.ibutton-container{display:inline-block;width:80px;height:24px;border:1px solid #888;margin:2px} .ui-dialog{border:2px solid red;padding:8px}</style>
"""


def _select(nome: str, opcoes: list[tuple[str, str]], valor: str = "") -> str:
    ops = "".join(f'<option value="{v}"{" selected" if v == valor else ""}>{html.escape(t)}</option>' for v, t in opcoes)
    return f'<select name="{nome}">{ops}</select>'


def pagina_formulario() -> str:
    chks = "".join(
        f'<label>{n}<div class="ibutton-container"><input type="hidden" name="{n}" value="0">'
        f'<input type="checkbox" name="{n}" value="1"{" checked" if n in LIGADOS_INICIO else ""}></div></label><br>'
        for n in INTERRUPTORES
    )
    cats = "".join(
        f'<div class="ibutton-container"><input type="checkbox" name="categorialeilao[]" value="{i}"{"" if i == 3 else " checked"}></div>'
        for i in range(1, 5)
    )
    st = [(str(i), f"Status {i}") for i in range(1, 12)]
    return f"""<!doctype html><html><head><meta charset="utf-8">{BASE_JS}</head><body>
<h1>Cadastro de Leilão</h1>
<form method="post" action="/montagem/salvar-leilao">
{_select("leiloeiro_id", [("", "Selecione"), ("11", "Álvaro Sérgio Fuzo - www.alvaroleiloes.com.br"), ("12", "Paulo Cézar Rocha Teixeira - www.leiloesjudiciaisbahia.com.br")])}
{_select("filial_id", [("", "Selecione"), ("1", "Campo Grande"), ("99", "OCULTO")])}
{_select("fuso_horario", [("0", "0 (Brasília)"), ("-1", "-1 (Amazonas, Mato Grosso...)"), ("-2", "-2 (Acre)"), ("1", "+1 (Fernando de Noronha)")])}
<input name="nm">
{_select("statusleilao_id", st)} {_select("tp_judicial_extrajudicial", st)} {_select("statusvendadireta", st + [("99", "Não")])}
{_select("statusmontagem_id", st)} {_select("statusrotuloleilao_primeiro", st)} {_select("statusrotuloleilao_segundo", st)}
{_select("statustipoleilao_id", st)} {_select("statusfechamentosucesso_id", [("1", "Aberto"), ("4", "Vendido")])}
<input name="dt"> <input name="dt_hora"> <input name="dt_segundoleilao_data"> <input name="dt_segundoleilao_hora">
<input name="dt_contabil"> <input name="nu_comissaoarrematante" value="5">
{chks}{cats}
<textarea id="nm_descricao" name="nm_descricao" style="display:none"></textarea><div id="nm_descricao_body"></div>
<button type="button">Excluir</button> <button type="submit">Salvar</button>
</form>
<div class="ui-dialog" style="display:none">Deseja manter a data contábil igual à data do leilão? <button type="button" onclick="$('.ui-dialog').hide()">OK</button></div>
<script>$('[name=dt]').on('change', function () {{ $('.ui-dialog').show(); }});</script>
</body></html>"""


def pagina_edita(lid: str, ciclos: list[tuple[str, str]]) -> str:
    linhas = "".join(f"<tr><td>Ciclo {d}</td><td>{h}</td><td>Venda Direta</td></tr>" for d, h in ciclos)
    return f"""<!doctype html><html><head><meta charset="utf-8">{BASE_JS}</head><body>
<h1>Leilão {lid}</h1><a href="#tab_cadastro">Cadastro de Leilão</a> <a href="#tab_leilaodata">Datas</a>
<div id="tab_leilaodata">
<form method="post" action="/montagem/salvar-data/{lid}">
<input name="dtleilao"> <input name="dt_hora">
{_select("statusrotuloleilao_multiplas", [("1", "Leilão"), ("2", "Venda Direta")])}
<button type="submit">Salvar</button>
</form>
<table><thead><tr><th>Data</th></tr></thead><tbody>{linhas}</tbody></table>
</div></body></html>"""


PAGINA_LOGIN = """<!doctype html><html><body><form method="post" action="/login">
<input name="usuario"><input type="password" name="senha"><button type="submit">Entrar</button></form></body></html>"""


class SIGFalso:
    def __init__(self, exigir_login: bool = True, falhar_salvar_leilao: bool = False):
        self.exigir_login = exigir_login
        self.falhar_salvar_leilao = falhar_salvar_leilao
        self.leiloes: dict[str, dict] = {}
        self.ciclos: dict[str, list[tuple[str, str]]] = {}
        self._prox_id = 500
        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self.servidor.server_port}"

    def __enter__(self) -> "SIGFalso":
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc) -> None:
        self.servidor.shutdown()

    def _handler(self):
        sig = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _logado(self) -> bool:
                return not sig.exigir_login or "sessao=ok" in (self.headers.get("Cookie") or "")

            def _enviar(self, corpo: str | bytes, tipo: str = "text/html; charset=utf-8", status: int = 200, extra=()):
                dados = corpo.encode("utf-8") if isinstance(corpo, str) else corpo
                self.send_response(status)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(dados)))
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(dados)

            def _redirecionar(self, para: str, extra=()):
                self.send_response(303)
                self.send_header("Location", para)
                for k, v in extra:
                    self.send_header(k, v)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _form(self) -> dict[str, list[str]]:
                n = int(self.headers.get("Content-Length") or 0)
                return parse_qs(self.rfile.read(n).decode("utf-8"), keep_blank_values=True)

            def do_GET(self):
                p = urlparse(self.path).path
                if p == "/jquery.min.js":
                    return self._enviar(JQUERY, "application/javascript")
                if p == "/login":
                    return self._enviar(PAGINA_LOGIN)
                if not self._logado():
                    return self._redirecionar("/login")
                if p == "/montagem/leilao-formulario":
                    return self._enviar(pagina_formulario())
                partes = p.strip("/").split("/")
                if p.startswith("/montagem/edita-leilao/id/") and partes[-1] in sig.leiloes:
                    return self._enviar(pagina_edita(partes[-1], sig.ciclos.get(partes[-1], [])))
                self._enviar("não encontrado", status=404)

            def do_POST(self):
                p = urlparse(self.path).path
                if p == "/login":
                    self._form()
                    return self._redirecionar("/montagem/leilao-formulario", [("Set-Cookie", "sessao=ok; Path=/; Max-Age=86400")])
                if not self._logado():
                    return self._redirecionar("/login")
                if p == "/montagem/salvar-leilao":
                    f = self._form()
                    if sig.falhar_salvar_leilao:
                        return self._enviar("Erro interno", status=500)
                    sig._prox_id += 1
                    lid = str(sig._prox_id)
                    # checkbox marcado manda dois valores (hidden 0 + checkbox 1): fica o último
                    sig.leiloes[lid] = {k: v[-1] for k, v in f.items()} | {"categorias": f.get("categorialeilao[]", [])}
                    return self._redirecionar(f"/montagem/edita-leilao/id/{lid}")
                if p.startswith("/montagem/salvar-data/"):
                    lid = p.rsplit("/", 1)[-1]
                    f = self._form()
                    sig.ciclos.setdefault(lid, []).append((f["dtleilao"][0], f["dt_hora"][0]))
                    return self._redirecionar(f"/montagem/edita-leilao/id/{lid}")
                self._enviar("não encontrado", status=404)

        return H

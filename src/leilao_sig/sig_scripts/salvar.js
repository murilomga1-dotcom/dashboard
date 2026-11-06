// Aceita os avisos de sucesso e clica no Salvar certo. CFG = {alvo:'leilao'|'lote'}
// Só usar imediatamente antes de salvar; nunca perto de Excluir/Liberar.
(function (C) {
  var p = location.pathname;
  var okLeilao = /^\/montagem\/(leilao-formulario|edita-leilao\/id\/\d+|atualiza-leilao\/id\/\d+)/.test(p);
  var okLote = /^\/montagem\/loteamento\/id\/\d+\/leilao_id\/\d+/.test(p);
  if ((C.alvo === 'leilao' && !okLeilao) || (C.alvo === 'lote' && !okLote)) return 'FORA: ' + p;
  window.alert = function (m) { window.__lastAlert = m; };
  window.confirm = function () { return true; };
  var campo = C.alvo === 'leilao' ? '[name=nm]' : '[name=nm_titulo]';
  var form = $(campo).closest('form');
  if (!form.length) return 'ERRO: formulario nao encontrado';
  var b = form.find('button[type=submit],input[type=submit]').filter(function () {
    return /salvar/i.test($(this).text() + ' ' + ($(this).val() || '')) && !/excluir/i.test($(this).text());
  }).last();
  if (!b.length) return 'ERRO: botao Salvar nao encontrado';
  b[0].click();
  return 'SALVANDO ' + C.alvo;
})(CFG);

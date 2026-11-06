// Seleciona a vistoria no modal "Selecione a vistoria" (depois de buscar).
// CFG = {vistoria:'33578', chave:'GEB-6666'}  (chave = placa ou palavra do bem; '' para não filtrar)
(function (C) {
  var p = location.pathname;
  if (!/^\/montagem\/loteamento\/id\/\d+\/leilao_id\/\d+/.test(p)) return 'FORA: ' + p;
  var tb = $('table:visible').filter(function () { var t = $(this).text(); return /Vistoria/.test(t) && /Descri/.test(t); }).last();
  if (!tb.length) return 'ERRO: tabela de vistorias nao encontrada (buscar antes)';
  var linhas = tb.find('tr').filter(function () { return $(this).children('td').length > 2; });
  function resumo(tr) { return $(tr).children('td').slice(1, 5).map(function () { return $(this).text().replace(/\s+/g, ' ').trim().slice(0, 50); }).get().join(' | '); }
  var ok = linhas.filter(function () {
    var cols = $(this).children('td'), v = $(cols[1]).text().replace(/\s+/g, ' ').trim(), t = $(this).text().toUpperCase();
    return v.split(' ')[0] === String(C.vistoria) && (!C.chave || t.indexOf(String(C.chave).toUpperCase()) >= 0);
  });
  if (ok.length === 0) return 'NENHUMA || ' + linhas.map(function () { return resumo(this); }).get().join(' / ');
  if (ok.length > 1) return 'VARIAS || ' + ok.map(function () { return resumo(this); }).get().join(' / ');
  var b = ok.find('a,button').last();
  if (!b.length) return 'ERRO: botao de selecao nao encontrado';
  b[0].click();
  return 'SELECIONADA || ' + resumo(ok[0]);
})(CFG);

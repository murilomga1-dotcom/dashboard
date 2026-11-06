// Lista os lotes da Listagem (N., ID, vistoria+título, valor, status). Sem CFG.
(function () {
  var p = location.pathname;
  if (!/^\/montagem\/loteamento\/id\/\d+\/leilao_id\/\d+/.test(p)) return 'FORA: ' + p;
  var a = $('a').filter(function () { return $(this).text().trim() === 'Listagem'; }).first();
  if (a.length) a.click();
  var t = $('table').filter(function () { return /ID lote/.test($(this).text()); }).first();
  var r = t.find('tbody tr').filter(function () { return $(this).children('td').length > 4; }).map(function () {
    var c = $(this).children('td');
    return [1, 2, 4, 5, 6].map(function (i) { return $(c[i]).text().replace(/\s+/g, ' ').trim().slice(0, 70); }).join(' | ');
  }).get();
  return r.length ? r.length + ' lote(s) || ' + r.join(' // ') : 'NENHUM LOTE';
})();

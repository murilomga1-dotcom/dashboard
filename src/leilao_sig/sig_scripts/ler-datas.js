// Lista as datas cadastradas na aba Datas. Sem CFG.
(function () {
  var p = location.pathname;
  if (!/^\/montagem\/(edita-leilao|atualiza-leilao)\/id\/\d+/.test(p)) return 'FORA: ' + p;
  return $('#tab_leilaodata table tbody tr').map(function () { return $(this).text().replace(/\s+/g, ' ').trim(); }).get().join(' || ');
})();

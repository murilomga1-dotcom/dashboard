// Clica OK no modal "Deseja manter a data contábil igual a data do leilão?". Sem CFG.
(function () {
  var b = $('.ui-dialog:visible button').filter(function () { return /^ok$/i.test($(this).text().trim()); });
  if (!b.length) return 'SEM MODAL';
  b.first().click();
  return 'OK | modais restantes=' + $('.ui-dialog:visible').length;
})();

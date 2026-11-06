// Cadastra UM ciclo na aba Datas. CFG = {data:'dd/mm/aaaa', hora:'HH:MM', anterior:'dd/mm/aaaa'|null}
(function (C) {
  var p = location.pathname;
  if (!/^\/montagem\/(edita-leilao|atualiza-leilao)\/id\/\d+/.test(p)) return 'FORA: ' + p;
  $('a[href="#tab_leilaodata"]').click();
  var t = $('#tab_leilaodata');
  if (!t.length) return 'ERRO: aba Datas nao encontrada';
  var rows = t.find('table tbody tr').map(function () { return $(this).text().replace(/\s+/g, ' ').trim(); }).get();
  function tem(d) { return rows.some(function (r) { return r.indexOf('Ciclo ' + d) >= 0; }); }
  if (tem(C.data)) return 'JA_EXISTE ' + C.data;
  if (C.anterior && !tem(C.anterior)) return 'FALTA_ANTERIOR ' + C.anterior + ' || ' + rows.join(' / ');
  window.alert = function (m) { window.__lastAlert = m; };
  window.confirm = function () { return true; };
  t.find('[name=dtleilao]').val(C.data).trigger('change');
  t.find('[name=dt_hora]').val(C.hora).trigger('change');
  t.find('[name=statusrotuloleilao_multiplas]').val('2').trigger('change').trigger('chosen:updated');
  if (t.find('[name=dtleilao]').val() !== C.data || t.find('[name=dt_hora]').val() !== C.hora) return 'ERRO: campos nao preenchidos';
  var b = t.find('button,input[type=submit]').filter(function () { return /salvar/i.test($(this).text() + ' ' + ($(this).val() || '')); }).first();
  if (!b.length) return 'ERRO: Salvar da aba Datas nao encontrado';
  b[0].click();
  return 'SALVANDO ' + C.data + ' ' + C.hora;
})(CFG);

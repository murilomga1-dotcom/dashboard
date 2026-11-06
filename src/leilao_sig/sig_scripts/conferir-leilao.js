// Confere o cadastro do leilão antes de salvar. Sem CFG.
// Acerta tipo = Múltiplas Datas e "Status ao atingir" = Vendido; devolve só o que estiver fora do padrão.
(function () {
  var p = location.pathname;
  if (!/^\/montagem\/(leilao-formulario|edita-leilao\/id\/\d+|atualiza-leilao\/id\/\d+)/.test(p)) return 'FORA: ' + p;
  $('[name=statustipoleilao_id]').val('6').trigger('change');
  $('[name=statusfechamentosucesso_id]').val('4').trigger('change').trigger('chosen:updated');
  var LIG = ['bn_segundoleilao', 'bn_exibeavaliacao', 'bn_exibedesconto', 'bn_finalizadonaodivulgado', 'bn_exibeleilaovitrine', 'bn_fechamentoautomatico'];
  var DES = ['bn_ocultaapelido', 'bn_gravacao', 'bn_liberacaoonline', 'bn_despesasadm', 'bn_destaque', 'bn_transmissaoaovivo'];
  var dif = [];
  function chk(n) { return $('input[type=checkbox][name="' + n + '"]').prop('checked'); }
  LIG.forEach(function (n) { if (chk(n) !== true) dif.push('LIGAR ' + n); });
  DES.forEach(function (n) { if (chk(n) === true) dif.push('DESLIGAR ' + n); });
  var cats = $('input[type=checkbox][name="categorialeilao[]"]'), off = cats.filter(function () { return !this.checked; }).length;
  if (off) dif.push('CATEGORIAS desligadas=' + off + '/' + cats.length);
  var esp = { statusleilao_id: '6', statustipoleilao_id: '6', tp_judicial_extrajudicial: '2', statusvendadireta: '99',
              statusrotuloleilao_primeiro: '3', statusrotuloleilao_segundo: '3', statusmontagem_id: '9' };
  for (var k in esp) { var v = $('[name=' + k + ']').val(); if (v !== esp[k]) dif.push(k + '=' + v); }
  if ($('[name=dt_contabil]').val() !== $('[name=dt]').val()) dif.push('dt_contabil diferente');
  var fs = $('[name=statusfechamentosucesso_id] option:selected').text().trim();
  if (chk('bn_fechamentoautomatico') && fs !== 'Vendido') dif.push('status ao atingir=' + fs);
  if (!$('[name=filial_id] option:selected').text().trim().match(/^OCULTO$/i)) dif.push('localidade');
  if ($('.ui-dialog:visible').length) dif.push('MODAL aberto (rodar ok-modal.js)');
  return dif.length ? 'DIVERGE: ' + dif.join('; ') : 'OK | comissao=' + $('[name=nu_comissaoarrematante]').val();
})();

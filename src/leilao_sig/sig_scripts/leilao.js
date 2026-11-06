// Preenche o cadastro do leilão. Uso: enviar  var CFG={...};  + este arquivo.
// CFG = {site:'jsilvaleiloes', titulo:'JUSTIÇA ...', fuso:'0'|'-1'|'-2'|'+1',
//        dt1:'dd/mm/aaaa', h1:'HH:MM', dt2:'dd/mm/aaaa', h2:'HH:MM', html:'<p>...</p>'}
(function (C) {
  var p = location.pathname;
  if (!/^\/montagem\/(leilao-formulario|edita-leilao\/id\/\d+|atualiza-leilao\/id\/\d+)/.test(p)) return 'FORA: ' + p;
  var out = [], err = [];
  function txt(e) { return $(e).text().replace(/\s+/g, ' ').trim(); }
  function sel(n, v) { $('[name=' + n + ']').val(v).trigger('change'); }
  function chosen(s, v) {
    var $s = $(s); $s.val(v).trigger('change').trigger('chosen:updated');
    var vis = $s.next('.chosen-container').find('.chosen-single span').text().trim();
    return vis || txt($s.find('option:selected'));
  }
  // Leiloeiro (pelo domínio do site)
  var lo = $('[name=leiloeiro_id] option').filter(function () { return txt(this).toLowerCase().indexOf(C.site.toLowerCase()) >= 0; });
  if (lo.length !== 1) err.push('LEILOEIRO encontrados=' + lo.length);
  else out.push('leiloeiro=' + chosen('[name=leiloeiro_id]', lo.val()).replace(/https?:\/\/|www\./g, '').slice(0, 40));
  // Localidade OCULTO
  var fo = $('[name=filial_id] option').filter(function () { return txt(this).toUpperCase() === 'OCULTO'; });
  if (!fo.length) err.push('OCULTO nao encontrado');
  else { var fv = chosen('[name=filial_id]', fo.val()); out.push('localidade=' + fv); if (fv.toUpperCase() !== 'OCULTO') err.push('DIVERGE localidade (fazer pela tela)'); }
  // Fuso
  var fs = $('select').filter(function () { return $(this).find('option').text().indexOf('Noronha') >= 0; }).first();
  var fz = fs.find('option').filter(function () { return txt(this).indexOf(C.fuso + ' (') === 0; });
  if (!fs.length || fz.length !== 1) err.push('FUSO nao encontrado');
  else { var zv = chosen(fs, fz.val()); out.push('fuso=' + zv); if (zv.indexOf(C.fuso + ' (') !== 0) err.push('DIVERGE fuso (fazer pela tela)'); }
  // Campos
  $('[name=nm]').val(C.titulo).trigger('change');
  sel('statusleilao_id', '6'); sel('tp_judicial_extrajudicial', '2'); sel('statusvendadireta', '99'); sel('statusmontagem_id', '9');
  $('[name=dt]').val(C.dt1).trigger('change').trigger('blur');
  $('[name=dt_hora]').val(C.h1).trigger('change').trigger('blur');
  sel('statusrotuloleilao_primeiro', '3');
  $('[name=dt_segundoleilao_data]').val(C.dt2).trigger('change').trigger('blur');
  $('[name=dt_segundoleilao_hora]').val(C.h2).trigger('change').trigger('blur');
  sel('statusrotuloleilao_segundo', '3');
  $('[name=dt_contabil]').val(C.dt1).trigger('change');
  sel('statustipoleilao_id', '6');
  // Descrição: conteúdo + justificado + 10pt
  var ed = tinymce.get('nm_descricao');
  if (!ed) err.push('SEM EDITOR');
  else {
    ed.setContent(C.html); ed.execCommand('SelectAll'); ed.execCommand('JustifyFull');
    ed.execCommand('FontSize', false, '10pt'); ed.selection.collapse(); ed.save();
    var b = ed.getBody(), np = b.querySelectorAll('p').length, nj = b.querySelectorAll('p[style*=justify]').length;
    out.push('desc=' + ed.getContent({ format: 'text' }).length + 'c just=' + nj + '/' + np + ' links=' + b.querySelectorAll('a').length);
    if (nj !== np) err.push('DIVERGE justificado');
  }
  out.push('titulo=' + ($('[name=nm]').val() === C.titulo ? 'ok' : 'DIVERGE'));
  out.push('dt1=' + $('[name=dt]').val() + ' ' + $('[name=dt_hora]').val() + ' dt2=' + $('[name=dt_segundoleilao_data]').val() + ' ' + $('[name=dt_segundoleilao_hora]').val());
  out.push('modal=' + $('.ui-dialog:visible').length);
  return (err.length ? 'ERRO: ' + err.join('; ') + ' || ' : 'OK || ') + out.join(' | ');
})(CFG);

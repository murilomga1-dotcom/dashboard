// Preenche o lote (depois de selecionar a vistoria). Status sempre Aguardando.
// CFG = {titulo:'...', html:'<p>...</p>', v1:'68.000,00', aval:'68.000,00', v2:'34.000,00'}
(function (C) {
  var p = location.pathname;
  if (!/^\/montagem\/loteamento\/id\/\d+\/leilao_id\/\d+/.test(p)) return 'FORA: ' + p;
  if (!$('[name=nm_titulo]').length) return 'ERRO: formulario do lote nao carregado';
  var err = [];
  function set(n, v) { $('[name=' + n + ']').val(v).trigger('input').trigger('change').trigger('keyup').trigger('blur'); }
  if (C.titulo.length > 56) err.push('TITULO > 56 (' + C.titulo.length + ')');
  set('nm_titulo', C.titulo);
  set('vl_lanceinicial', C.v1);
  set('vl_lanceminimo', C.aval);
  set('vl_lanceinicialsegundoleilao', C.v2);
  set('vl_lanceminimosegundoleilao', C.aval);
  $('[name=statusliberacaolote_id]').val('4').trigger('change').trigger('chosen:updated');
  var ed = tinymce.get('nm_descricao');
  if (!ed) err.push('SEM EDITOR');
  else {
    ed.setContent(C.html); ed.execCommand('SelectAll'); ed.execCommand('JustifyFull');
    ed.execCommand('FontSize', false, '10pt'); ed.selection.collapse(); ed.save();
  }
  var chk = { nm_titulo: C.titulo, vl_lanceinicial: C.v1, vl_lanceminimo: C.aval, vl_lanceinicialsegundoleilao: C.v2, vl_lanceminimosegundoleilao: C.aval };
  for (var k in chk) if ($('[name=' + k + ']').val() !== chk[k]) err.push('DIVERGE ' + k + '=' + $('[name=' + k + ']').val());
  var st = $('[name=statusliberacaolote_id] option:selected').text().trim();
  if (st !== 'Aguardando') err.push('STATUS=' + st);
  var vist = ($('body').text().match(/Categoria:\s*([^\n]*?)\s*Cidade\/UF:\s*([^\n]*?)\s*T[ií]tulo:/) || []);
  var info = 'n=' + $('[name=nu]').val() + ' | incremento=' + $('[name=vl_incremento]').val() +
    ' | vistoria: ' + (vist[1] || '?') + ' / ' + (vist[2] || '?') +
    (ed ? ' | desc=' + ed.getContent({ format: 'text' }).length + 'c just=' + ed.getBody().querySelectorAll('p[style*=justify]').length + '/' + ed.getBody().querySelectorAll('p').length : '');
  return (err.length ? 'ERRO: ' + err.join('; ') + ' || ' : 'OK || ') + info;
})(CFG);

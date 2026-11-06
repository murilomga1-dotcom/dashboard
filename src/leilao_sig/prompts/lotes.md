# Lotes — ordem, título, descrição e valores

## Ordem no site (mais de um lote)

1. **Tipo:** Imóveis → Veículos → demais bens.
2. **Valor:** dentro do tipo, avaliação do maior para o menor.
3. **Processo:** dentro do tipo, bens do mesmo processo juntos, na posição do maior; dentro do grupo, maior → menor.

Processo com bens de tipos diferentes: cada bem no bloco do seu tipo (avisar). Mostrar a ordem final (tipo, valor, processo) na resposta.

## Título (máx. 56 caracteres)

`[bem] - [detalhe] - Cidade/UF`
- Imóvel: `Casa c/ 120m² - Terreno 300m² - Passos/MG`; `Apto. 68m² - 2 dorms - Maringá/PR`; `Parte ideal 50% - Casa 90m² - Lins/SP`
- Veículo: `Marca/Modelo versão - AA/AA - Cidade/UF` (ex.: `Jeep/Grand Cherokee Limited - 99/00 - Campo Largo/PR`)
- Equipamento: `Tipo - Marca Modelo - ano - Cidade/UF` (ex.: `Torno mecânico - Marca Mitto - Curitiba/PR`)
- Vários bens: `Lote c/ 3 máquinas de costura - Cidade/UF`
- Passou de 56: abreviar (Apartamento→Apto., Terreno→Terr., Santa→Sta., Governador→Gov.); nunca tirar a cidade de imóvel.
- **Metragem nunca é abreviada nem arredondada**: se o título passar de 56, reduzir outras palavras (ex.: tirar "Gleba 76") e manter a metragem exata do edital.
- Cidade: a do bem; se o edital não disser, usar a Cidade/UF da vistoria (o `lote.js` devolve).

## Descrição (um `<p>` por parte, `<p><br></p>` entre elas, nesta ordem)

Sem cor nos textos. A única formatação é negrito onde indicado.

1. **Resumo** (1–2 frases, caixa normal) + ` (Proc. nº)`. Em **imóveis**, incluir no mesmo parágrafo, antes da cidade/UF: `Imóvel com Incra n.º <nº> e CRI n.º <nº>, <Cidade/UF>`. Se o edital não trouxer Incra ou CRI de um imóvel, cadastrar o lote normalmente, sem esses números, e registrar o alerta no resumo final (não bloqueia o cadastro). Em outros bens: tirar matrícula, cartório, confrontações, Renavam, chassi, nº do motor; manter placa. Abreviações: `c/`, `dorm(s)`, `aprox.`, `alq.`, `nº`. **Metragem e valores sempre exatamente como no edital, sem arredondar** (ex.: `50,0287ha`, não `50ha`; `124,00m²`, não `124m²`).
   - Ex. imóvel: `Lote rural nº 95 da Gleba 76 do Projeto Integrado de Colonização Padre Adolpho Rohl, Gleba Rio Jaru, com área de 50,0287ha, situado no Município de Governador Jorge Teixeira/RO, contendo 01 casa simples em alvenaria, curral e cercas, Imóvel com Incra n.º 950.173.986.798-5 e CRI n.º 24.350, Jaru/RO (Proc. 7002054-21.2020.8.22.0003)`
   - Ex. veículo: `I/Jeep Grand Cherokee Limited, ano 1999/2000, cor preta, gasolina, placa GEB-6666. (Proc. 0007143-14.2018.8.16.0026)`
   - Ex. equipamento: `Torno mecânico marca Mitto, sem número de série aparente, em funcionamento. (Proc. ...)`
2. **Parcelamento do bem** (só se o edital tiver seção de parcelamento): **em negrito**, sem cor, antes da Obs.
   - Imóvel: `<p><strong>(O IMÓVEL PODE SER PARCELADO COM 25% DE ENTRADA E O RESTANTE EM ATÉ 30 MESES)</strong></p>`
   - Veículo: `(O VEÍCULO PODE SER PARCELADO COM 25% DE ENTRADA E O RESTANTE EM ATÉ 06 MESES - MEDIANTE APRESENTAÇÃO DE CAUÇÃO)`
   - Móveis/equipamentos: `(O BEM PODE SER PARCELADO COM 25% DE ENTRADA E O RESTANTE EM ATÉ 06 MESES - MEDIANTE APRESENTAÇÃO DE CAUÇÃO)`
   - (ajustar entrada/meses ao edital)
3. **Obs.:** ocupação e desocupação por mandado, benfeitorias não averbadas e custos de regularização, penhoras, alienação fiduciária, RENAJUD. **Não** incluir hipoteca nem débitos que a arrematação extingue ou sub-roga (IPTU/TLP, IPVA, condomínio, débito da demanda). Um só "Obs.:". Sem cor.
4. **Frases do lote** (quando for o caso), sem cor:
   - **Meação / cota-parte** (art. 843): usar a frase só quando o edital citar o nome do coproprietário e/ou a porcentagem reservada; sem nenhum dos dois, não usar. Meação: `(O VALOR DE R$ XX.XXX,XX REFERENTE À COTA-PARTE/MEAÇÃO DEVE SER QUITADO INTEGRALMENTE. O MONTANTE RESTANTE PODE SER PARCELADO COM ENTRADA DE 25% E O RESTANTE EM ATÉ 30 MESES)`
   - Cota-parte: `Obs.: O Lance Mínimo foi calculado considerando os termos do Art. 843, do CPC/2015, ou seja, reservando a cota parte do coproprietário ou cônjuge alheio à execução.`
   - Box: `(Obs.: Em se tratando de box de garagem situados dentro de um condomínio, a alienação ficará restrita aos condôminos do referido edifício, nos termos do Art. 1.331, § 1º, do Código Civil.)`
   - Já vendido em outro processo: `(Obs.: Lance condicional, pendente de confirmação de arrematação anterior em outro processo.)`
   - Fazenda Nacional imóvel: `(O IMÓVEL PODE SER PARCELADO COM 25% DE ENTRADA E O RESTANTE EM ATÉ 59 VEZES, LIMITADO À DÍVIDA DE R$ ******. CASO A ARREMATAÇÃO SUPERE À DÍVIDA, O SALDO REMANESCENTE DEVERÁ SER PAGO À VISTA)`
   - Fazenda Nacional veículo: `(O VEÍCULO PODE SER PARCELADO EM ATÉ 48 VEZES, LIMITADO À DÍVIDA DE R$ ******. CASO A ARREMATAÇÃO SUPERE À DÍVIDA, O SALDO REMANESCENTE DEVERÁ SER PAGO À VISTA)`
5. **Localização** (só bens móveis/veículos, antes das partes): `Localização do bem: <endereço do edital>` ou `Localização do bem: em poder do depositário <Nome>`. Sem nenhum dos dois → omitir e avisar.
6. **Cartório e partes — SOMENTE em leilões do Distrito Federal (JE/TJDFT)**. Fora do DF, não inserir. No DF: um único `<p>` com as linhas do edital separadas por `<br>`, na ordem `Cartório:`, `Réu(s)/Executado(s):` com o `Advogado(s):` correspondente, `Autor(es)/Exequente(s):` com seu advogado, `Interessado:`. Copiar nomes e OAB como estão no edital. Sem `Processo:` e sem `Código Leilojus`.

## Valores (CFG do lote.js, formato `68.000,00`)

- `v1` = Inicial 1º leilão = avaliação (ou o valor do 1º leilão do edital)
- `aval` = Mínimo (Avaliação) e Avaliação 2º leilão = avaliação
- `v2` = Inicial 2º leilão = lance mínimo do 2º leilão (conferir % × valor; se o edital só der o %, calcular e avisar)

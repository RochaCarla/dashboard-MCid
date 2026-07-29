# Dashboard GT — Gestão de Ações

Ferramenta de BI (dashboard) para acompanhamento de ações de Grupos de Trabalho interinstitucionais, desenvolvida pelo CEAG e Lab Livre (UnB) em parceria com o Ministério das Cidades. O template é reutilizável por múltiplos GTs; os dados de produção atuais são do GT Industrialização.

## Language

**GT (Grupo de Trabalho)**:
Instância interinstitucional que organiza linhas de atuação com ações a serem executadas por múltiplos atores.
_Avoid_: Comitê, comissão, squad

**Eixo Temático**:
Agrupamento principal de um GT que organiza processos e tarefas relacionados (ex: "Financiamento").
_Avoid_: Linha de atuação, pilar, frente. Nota: o JSON usa a chave `linhas` por legado, mas o termo correto no domínio é "Eixo Temático".

**Processo**:
Conjunto de tarefas dentro de um Eixo Temático que compartilham um objetivo operacional (ex: "Prospectar demandas de investimento").
_Avoid_: Fluxo, workflow

**Tarefa**:
Unidade atômica de trabalho dentro de um Processo, com responsável, status, prioridade e prazo.
_Avoid_: Ação (ambíguo — ver nota abaixo), item, ticket

**Cod_Task**:
Código hierárquico que identifica uma Tarefa na planilha (ex: `6.3.2` = eixo 6, atividade 3, tarefa 2). É a chave usada pela coluna "Depende de" e pelo grafo de dependências do dashboard. Os códigos são digitados manualmente e nem sempre seguem o número do eixo (ex: `1.4.1` está no eixo 2) — o dashboard trata o código como identificador opaco, sem inferir o eixo a partir dele.
_Avoid_: ID (o JSON já usa `id` para um inteiro sintético), WBS

**Dependência (pré-requisito)**:
Relação entre duas Tarefas declarada na coluna "Depende de": a tarefa só pode avançar depois que o(s) Cod_Task(s) listado(s) estiver(em) concluído(s). O conjunto forma um grafo dirigido acíclico exibido na seção "Rede de dependências das entregas".
_Avoid_: Bloqueio (reservado para o *status* `bloqueado`, que é declarado pelo gestor, não derivado do grafo)

**Entrega travada / pronta**:
Situação derivada (não existe na planilha): *travada* = tem pré-requisito ainda não concluído; *pronta* = todos os pré-requisitos concluídos e a tarefa ainda aberta. Uma tarefa pode estar `em_andamento` e travada ao mesmo tempo — os dois eixos de informação são independentes.
_Avoid_: Usar "travada" como sinônimo de status `bloqueado`

**Gargalo**:
Tarefa ainda não concluída que é pré-requisito, direto ou indireto, de outras. O peso do gargalo é o número de entregas que ele destrava.
_Avoid_: Caminho crítico (não há duração estimada por tarefa; não é CPM)

**Ação (schema v1)**:
No schema v1 (legado), sinônimo de Tarefa — unidade de trabalho dentro de uma Linha, sem a camada intermediária de Processo.
_Avoid_: Usar "ação" quando o schema é v2; preferir "tarefa"

**Responsável**:
Ator (pessoa ou órgão) designado para executar uma Tarefa. Pode ser uma instituição parceira do GT (ex: "CEAG UnB", "SNH", "BNDES").
_Avoid_: Assignee, dono

**CEAG**:
Centro de Estudos Avançados de Governo da UnB. Tem duplo papel: (1) executor de tarefas dentro do GT Industrialização, e (2) co-desenvolvedor da ferramenta de dashboard.
_Avoid_: Confundir o papel de executor com o de desenvolvedor

**Lab Livre**:
Laboratório da UnB. Co-desenvolvedor da ferramenta de dashboard junto com o CEAG.
_Avoid_: LabLivre (sem espaço)

## Schema

O formato principal é **v2** (Linha → Processos → Tarefas). O schema v1 (Linha → Ações) é mantido para compatibilidade com GTs que possuem planilhas mais simples sem camada intermediária de Processo.

## Fluxo de dados

**Atual:** Automático — o workflow `sync-google-sheets.yml` baixa diariamente (11h UTC) o CSV do Google Sheets, roda `scripts/xlsx_to_json.py` e commita `data/acoes.json` + `data/historico.json`.

**Legado:** Sincronização via SharePoint (workflow existe mas não está ativo; requer Azure AD App Registration).

O conversor grava em `meta` os campos `sincronizado_em` (timestamp UTC), `proxima_reuniao` e `guardia`, exibidos no card "Atualização" do dashboard. A data da próxima reunião do GT é configurada no workflow (`--proxima-reuniao`); campo vazio fica oculto.

### Regras de parsing do CSV

- Fonte: export CSV do Google Sheets (UTF-8, separador `,`); o script auto-detecta delimitador e encoding.
- **Colunas detectadas pelo nome no cabeçalho** (a planilha pode reordenar). Layout atual: Eixo Temático | Prioridade | Prazo | Processo | Atividade | **Cod_Task** | Tarefa | **Depende de** | Responsável | Status. Sem cabeçalho reconhecível, cai no layout posicional legado (Prioridade | Prazo | Eixo | …), que não tem Cod_Task nem Depende de.
- **Herança por célula mesclada**: Eixo Temático, Processo e Atividade herdam do último valor preenchido acima — respeitando a hierarquia: mudar de Eixo invalida Processo/Atividade herdados; mudar de Processo invalida Atividade. Responsável, Prioridade, Cod_Task e Depende de NÃO herdam (são sempre por linha).
- **Defaults quando vazio**: Prioridade = "média", Status = "não iniciado"
- Linha sem Atividade nem Tarefa mas com Processo: o Processo é a própria unidade de trabalho (vira tarefa com desc = Processo).
- Linha só com Eixo (ex: eixo recém-criado): o eixo aparece no dashboard com 0 tarefas.
- **Quando existe coluna Cod_Task**, ela é a identidade da tarefa: linha sem Cod_Task *e* sem Tarefa é continuação de célula mesclada (ex: só um prazo extra) e é descartada, em vez de virar uma tarefa fantasma duplicando a Atividade herdada.
- **Depende de**: aceita um ou vários Cod_Task separados por `,` `;` `/` `+` ou espaço. O conversor valida o grafo e avisa no log sobre código duplicado, auto-referência, ciclo e referência órfã — referências que não resolvem são removidas do JSON para o front-end nunca desenhar aresta sem destino.
- Prazos podem ser textuais ("3 meses", "Em aberto"); "Em aberto" vira vazio, datas são normalizadas para ISO, demais textos passam como estão.
- **Progresso**: Não existe na planilha atual. Será coluna futura. Enquanto ausente, derivar do Status: `nao_iniciado` → 0%, `em_andamento` → 50%, `concluido` → 100%, `bloqueado`/`em_risco`/`stand by` → 25%.
- **Estado atual dos dados**: 10 Eixos Temáticos, 46 tarefas, 16 vínculos de dependência em 11 cadeias (jul/2026).

### Rede de dependências (front-end)

A seção "Rede de dependências das entregas" tem duas visualizações do mesmo grafo, alternadas pelo seletor no topo:

**🕸 Rede** — grafo Cod_Task → Depende de em camadas: cada coluna é um passo da cadeia (1º passo = sem pré-requisito), cada componente conexo ocupa uma faixa de linhas. Aresta verde sólida = pré-requisito cumprido; aresta vermelha tracejada = predecessor ainda aberto. Responde "o que vem antes do quê".

**📅 Gantt** — as mesmas cadeias no tempo. Responde "quando". Hover realça a cadeia inteira nas duas visões; clique leva à tarefa na tabela do eixo.

#### Como as datas do Gantt são derivadas

A planilha tem **um** prazo por tarefa, sem data de início e às vezes textual ou vazio — não há cronograma pactuado por tarefa. O Gantt monta a janela por passagem para frente, e o que é estimado aparece hachurado com nota metodológica embaixo do gráfico:

- **Início** = quando o último pré-requisito termina (nunca antes de `meta.sincronizado_em`, a data-base)
- **Fim**, na ordem de precedência:
  - tarefa concluída → barra-toco de 18 dias terminando na data-base (não ocupa o futuro nem segura sucessores)
  - prazo ISO ou nome de mês ("Agosto") → essa data (`origem: planilha`)
  - prazo já vencido → barra do prazo perdido até hoje, em vermelho (`origem: vencida`)
  - duração declarada ("3 meses", "6 semanas") → início + duração (`origem: duracao`)
  - nada → início + 30 dias (`origem: estimada`, hachurada)

Isto é ordenação de dependências no tempo, **não CPM**: não há duração real por tarefa, folga nem caminho crítico calculado. A nota sob o gráfico diz isso explicitamente para o Gantt não ser lido como compromisso do GT.

Só entram no desenho tarefas que participam de alguma cadeia — tarefas isoladas ficam de fora para não virar ruído, e o resumo acima do grafo informa quantas das entregas totais estão encadeadas. Os modos "Só com bloqueio" e "Prontas para iniciar" filtram por cadeia inteira (não por nó solto), preservando o contexto de quem trava quem.

Métricas derivadas em runtime, não persistidas: entregas travadas, prontas para iniciar, cadeia mais longa e gargalos (ordenados pelo nº de entregas que destravam). O conversor grava um resumo equivalente em `meta.dependencias` e o total de travadas em cada snapshot do histórico (`travadas_por_dependencia`).

## Público-alvo

Todos os perfis usam o mesmo dashboard público (GitHub Pages):
1. **Gestores do GT** — visão gerencial de progresso e bloqueios
2. **Executores** (CEAG, SNH, BNDES, etc.) — acompanhar suas próprias entregas
3. **Público externo** — transparência e prestação de contas

Não há dados sensíveis; tudo é público por design.

## Example dialogue

> **Dev**: "O CEAG aparece como responsável nessa tarefa — eles vão editar o dashboard?"
> **Domain expert**: "Não. O CEAG é responsável pela *tarefa do GT* (análise de dados). Quem edita o dashboard é o Lab Livre junto com o CEAG no papel de *desenvolvedor*, não de executor."
>
> **Dev**: "A planilha tem 'ações' mas o código fala em 'tarefas' — qual é?"
> **Domain expert**: "Depende do schema. No v2, uma Linha tem Processos que têm Tarefas. No v1 antigo, uma Linha tem Ações diretamente. O dashboard suporta ambos."

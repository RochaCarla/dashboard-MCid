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

### Regras de parsing do CSV

- Fonte: export CSV do Google Sheets (UTF-8, separador `,`); o script auto-detecta delimitador e encoding.
- **Colunas detectadas pelo nome no cabeçalho** (a planilha pode reordenar). Layout atual: Eixo Temático | Prioridade | Prazo | Processo | Atividade | Tarefa | Responsável | Status. Sem cabeçalho reconhecível, cai no layout posicional legado (Prioridade | Prazo | Eixo | …).
- **Herança por célula mesclada**: Eixo Temático, Processo e Atividade herdam do último valor preenchido acima — respeitando a hierarquia: mudar de Eixo invalida Processo/Atividade herdados; mudar de Processo invalida Atividade. Responsável e Prioridade NÃO herdam.
- **Defaults quando vazio**: Prioridade = "média", Status = "não iniciado"
- Linha sem Atividade nem Tarefa mas com Processo: o Processo é a própria unidade de trabalho (vira tarefa com desc = Processo).
- Linha só com Eixo (ex: eixo recém-criado): o eixo aparece no dashboard com 0 tarefas.
- Prazos podem ser textuais ("3 meses", "Em aberto"); "Em aberto" vira vazio, datas são normalizadas para ISO, demais textos passam como estão.
- **Progresso**: Não existe na planilha atual. Será coluna futura. Enquanto ausente, derivar do Status: `nao_iniciado` → 0%, `em_andamento` → 50%, `concluido` → 100%, `bloqueado`/`em_risco`/`stand by` → 25%.
- **Estado atual dos dados**: 10 Eixos Temáticos, 34 tarefas (jun/2026).

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

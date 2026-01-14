# IRPF Analyzer

**Analisador de riscos e otimização de declaração IRPF**

Uma ferramenta CLI em Python para analisar arquivos `.DEC` e `.DBK` (declarações do IRPF) e identificar potenciais riscos de malha fina, além de sugerir otimizações fiscais.

> **100% offline** - Seus dados nunca saem do seu computador.

---

## Funcionalidades

- **Suporte a Múltiplos Formatos**
  - `.DEC` - Declarações transmitidas
  - `.DBK` - Backups de declarações (durante edição)

- **Análise de Risco de Malha Fina**
  - Índice de Conformidade Fiscal de 0% a 100% (maior = mais seguro)
  - Detecção de inconsistências patrimônio vs renda
  - Verificação de despesas médicas proporcionalmente altas
  - Identificação de dependentes duplicados
  - Cruzamento de vendas declaradas (alienações) com bens zerados

- **Análise de Fluxo Patrimonial**
  - Cálculo detalhado de recursos disponíveis
  - Soma de renda (inclui rendimentos de renda fixa) + ganho de capital (lucro) + lucro em ações estrangeiras
  - Estimativa de despesas de vida
  - Verificação se variação patrimonial está explicada

- **Suporte a Ativos Estrangeiros**
  - Parsing de lucro/prejuízo declarado em ações estrangeiras
  - Identificação de vendas via corretoras internacionais (Avenue, Interactive Brokers)

- **Sugestões de Otimização**
  - Comparativo declaração completa vs simplificada
  - Oportunidades de dedução PGBL (até 12% da renda bruta)
  - Doações incentivadas (até 6% do IR devido)
  - Verificação de despesas com educação
  - Livro-caixa para profissionais autônomos

- **Comparativo Ano-a-Ano**
  - Comparação entre duas declarações de anos diferentes
  - Evolução patrimonial detalhada
  - Variação de rendimentos e deduções
  - Impacto tributário comparado
  - Destaques de ativos (valorizações, vendas, novos)

- **Detecção de Padrões Suspeitos** 🆕
  - Validação de CPF/CNPJ via cálculo de dígitos verificadores (100% local)
  - Análise estatística com Lei de Benford para detectar valores fabricados
  - Detecção de outliers usando método IQR (Interquartile Range)
  - Identificação de valores redondos suspeitos em deduções
  - Verificação de depreciação irregular de veículos
  - Detecção de despesas médicas concentradas em poucos prestadores
  - Análise temporal multi-ano (renda estagnada vs patrimônio crescente)

- **Relatórios PDF Completos**
  - Exportação para PDF com todas as informações
  - Resumo financeiro e patrimonial
  - Análise de fluxo patrimonial detalhada
  - Checklist de documentos necessários

- **Checklist de Documentos**
  - Lista de documentos necessários baseada nos lançamentos
  - Categorização por tipo (rendimentos, deduções, bens, etc.)
  - Prioridades: obrigatório, recomendado, opcional

---

## Instalação

### Requisitos

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recomendado) ou pip

### Com uv (recomendado)

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/irpf-analyzer.git
cd irpf-analyzer

# Instale as dependências
uv sync

# Para suporte a PDF (opcional)
uv sync --extra pdf

# Execute
uv run irpf-analyzer --help
```

### Com pip

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/irpf-analyzer.git
cd irpf-analyzer

# Crie um ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# Instale
pip install -e .

# Para suporte a PDF (opcional)
pip install -e ".[pdf]"

# Execute
irpf-analyzer --help
```

---

## Uso

### Análise Completa

```bash
irpf-analyzer analyze seu-arquivo.DEC
# ou
irpf-analyzer analyze seu-arquivo.DBK
```

**Exemplo de saída:**

```
╭───── IRPF Analyzer - Declaração ──────╮
│ Contribuinte: JOAO DA SILVA           │
│ CPF: ***.***.***.72                   │
│ Exercício: 2025 (Ano-calendário 2024) │
│ Tipo: COMPLETA                        │
╰───────────────────────────────────────╯

Dependentes:
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Nome                 ┃ CPF         ┃ Nascimento ┃ Tipo                 ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ MARIA DA SILVA       │ 12345678901 │ 15/03/2018 │ filho_enteado_ate_21 │
└──────────────────────┴─────────────┴────────────┴──────────────────────┘

Despesas Médicas Declaradas:
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Prestador                        ┃ CNPJ           ┃     Valor ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ CLINICA MEDICA EXEMPLO LTDA     │ 12345678000199 │ R$ 500,00 │
│ HOSPITAL SAO LUCAS              │ 98765432000111 │ R$ 800,00 │
└──────────────────────────────────┴────────────────┴───────────┘
Total despesas médicas: R$ 1.300,00

╭────────── Resumo Patrimonial ──────────╮
│ Total Bens (anterior): R$ 500.000,00   │
│ Total Bens (atual): R$ 750.000,00      │
│ Variação Patrimonial: R$ 250.000,00    │
╰────────────────────────────────────────╯

📊 Análise de Fluxo Patrimonial:
                       Origem dos Recursos (Dinheiro Novo)
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Fonte                                                   ┃           Valor ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ Renda declarada (salário, dividendos, rend. renda fixa) │   R$ 180.000,00 │
│ Ganho de capital (LUCRO das alienações)                 │    R$ 50.000,00 │
│ Lucro em ações estrangeiras                             │            R$ 0 │
│                                                         │                 │
│ TOTAL RECURSOS                                          │   R$ 230.000,00 │
└─────────────────────────────────────────────────────────┴─────────────────┘

╭───────── Cálculo de Compatibilidade ─────────╮
│ Recursos totais: R$ 230.000,00               │
│ (-) Despesas de vida estimadas: R$ 54.000,00 │
│ (=) Recursos disponíveis: R$ 176.000,00      │
│ (-) Variação patrimonial: R$ 250.000,00      │
│ (=) Saldo: -R$ 74.000,00                     │
│                                              │
│ ⚠️  ATENÇÃO - Verificar origem dos recursos  │
╰──────────────────────────────────────────────╯
ℹ️  Nota: Valor bruto de vendas e ativos liquidados não são contados
porque o principal já existia no patrimônio anterior.

╭── 🎯 Índice de Conformidade Fiscal ───╮
│ Conformidade: 95%                     │
│ Excelente - Baixo risco de malha fina │
╰───────────────────────────────────────╯

💡 Sugestões de Otimização:
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Sugestão                   ┃ Descrição                  ┃ Economia Potencial ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ Considere declaração       │ Desconto simplificado (R$  │       R$ 15.454,34 │
│ simplificada               │ 16,754.34) é maior que     │                    │
│                            │ suas deduções (R$          │                    │
│                            │ 1,300.00)                  │                    │
│ Oportunidade: PGBL         │ Você pode deduzir até R$   │        R$ 5.940,00 │
│                            │ 21,600.00 em PGBL (12% da  │                    │
│                            │ renda bruta)               │                    │
└────────────────────────────┴────────────────────────────┴────────────────────┘

✅ Declaração com baixo risco de malha fina!
```

### Gerar Relatório PDF

```bash
irpf-analyzer report seu-arquivo.DEC -o relatorio.pdf
```

Gera um relatório PDF completo com:
- Dados da declaração
- Índice de conformidade fiscal
- Resumo financeiro e patrimonial
- Análise de fluxo patrimonial
- Inconsistências e avisos
- Sugestões de otimização
- Detalhes de dependentes, rendimentos, deduções, bens e alienações
- Checklist de documentos

### Gerar Checklist de Documentos

```bash
irpf-analyzer checklist seu-arquivo.DEC
```

**Exemplo de saída:**

```
╭─────────── 📋 Checklist de Documentos ───────────╮
│ Contribuinte: JOAO DA SILVA                      │
│ Exercício: 2025                                  │
│ Total de documentos: 12                          │
╰──────────────────────────────────────────────────╯

💰 Rendimentos
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Documento                  ┃ Descrição                  ┃  Prioridade  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ Informe de Rendimentos     │ Documento fornecido pela   │ OBRIGATÓRIO  │
│                            │ fonte pagadora             │              │
└────────────────────────────┴────────────────────────────┴──────────────┘

💊 Deduções
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Documento                  ┃ Descrição                  ┃  Prioridade  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ Recibo de Despesa Médica   │ Recibo ou nota fiscal do   │ OBRIGATÓRIO  │
│                            │ prestador de serviço       │              │
└────────────────────────────┴────────────────────────────┴──────────────┘

╭──────────────── Resumo ────────────────╮
│ Obrigatórios: 8                        │
│ Recomendados: 3                        │
│ Opcionais: 1                           │
╰────────────────────────────────────────╯
```

### Comparativo Ano-a-Ano

```bash
irpf-analyzer compare 2024.DEC 2025.DEC
```

Compara duas declarações de anos diferentes, mostrando:

**Exemplo de saída:**

```
╭──────────────────────────────────────────────────────╮
│ 📊 Comparativo de Declarações IRPF                   │
│ Contribuinte: JOAO DA SILVA                          │
│ CPF: ***.***.***-72                                  │
│ Período: 2024 → 2025                                 │
╰──────────────────────────────────────────────────────╯

💰 Comparativo de Rendimentos:
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Tipo                ┃           2024 ┃           2025 ┃         Variação ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ Tributáveis         │  R$ 150.000,00 │  R$ 180.000,00 │ +R$ 30.000 (+20%)│
│ Isentos             │   R$ 10.000,00 │   R$ 15.000,00 │  +R$ 5.000 (+50%)│
│ Exclusivos          │    R$ 5.000,00 │    R$ 8.000,00 │  +R$ 3.000 (+60%)│
│                     │                │                │                  │
│ Total Geral         │  R$ 165.000,00 │  R$ 203.000,00 │ +R$ 38.000 (+23%)│
└─────────────────────┴────────────────┴────────────────┴──────────────────┘

🏠 Evolução Patrimonial:
╭─────────────────────────────────────────────────╮
│ Patrimônio Líquido 2024: R$ 500.000,00          │
│ Patrimônio Líquido 2025: R$ 750.000,00          │
│ Variação: +R$ 250.000,00 (+50.0%)               │
╰─────────────────────────────────────────────────╯

Patrimônio por Categoria:
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Categoria               ┃           2024 ┃           2025 ┃         Variação ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ Imóveis                 │  R$ 350.000,00 │  R$ 350.000,00 │                - │
│ Aplicações Financeiras  │  R$ 100.000,00 │  R$ 280.000,00 │+R$ 180.000(+180%)│
│ Veículos                │   R$ 50.000,00 │  R$ 120.000,00 │ +R$ 70.000(+140%)│
└─────────────────────────┴────────────────┴────────────────┴──────────────────┘

🔍 Destaques de Ativos:

Maiores Valorizações:
  ▲ CDB BANCO XYZ 120% CDI: +R$ 50.000,00 (+25.0%)

Novos Ativos:
  + (Veículos) VW TAOS TSI 2024: R$ 214.000,00

Ativos Resgatados/Liquidados:
  ↩ (Aplicações Financeiras) CDB BANCO ABC: R$ 80.000,00

✅ Comparação 2024 → 2025 concluída!
```

**Exportar como JSON:**

```bash
irpf-analyzer compare 2024.DEC 2025.DEC -o json
```

### Análise Temporal Multi-Ano

```bash
irpf-analyzer analyze-multi 2023.DEC 2024.DEC 2025.DEC
```

Detecta padrões suspeitos que só aparecem ao comparar declarações de diferentes anos:

**Exemplo de saída:**

```
╭──────────────────────────────────────────────────────╮
│ 📊 Análise Temporal Multi-Ano                        │
│ Contribuinte: JOAO DA SILVA                          │
│ Período: 2023-2025                                   │
│ Declarações analisadas: 3                            │
╰──────────────────────────────────────────────────────╯

Evolução Anual:
┏━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Ano    ┃    Renda Total ┃     Patrimônio ┃  Desp. Médicas ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ 2023   │  R$ 150.000,00 │  R$ 500.000,00 │   R$ 12.000,00 │
│ 2024   │  R$ 155.000,00 │  R$ 750.000,00 │   R$ 12.500,00 │
│ 2025   │  R$ 160.000,00 │ R$ 1.000.000,00│   R$ 12.300,00 │
└────────┴────────────────┴────────────────┴────────────────┘

⚠️  Padrões Temporais Detectados:

╭──────────────────────────────────────────────────────╮
│ Tipo: renda_estagnada_patrimonio_crescente           │
│                                                      │
│ Renda estagnada (var. média 3.3%/ano) enquanto       │
│ patrimônio cresceu significativamente                │
│ (R$ 500.000 → R$ 1.000.000)                          │
│                                                      │
│ Anos afetados: 2023, 2024, 2025                      │
│ Risco: ALTO                                          │
│ Valor impacto: R$ 500.000,00                         │
│                                                      │
│ 💡 Verificar se há rendimentos não declarados,       │
│    heranças, doações ou ganhos de capital omitidos   │
╰──────────────────────────────────────────────────────╯

⚠️  2 padrão(ões) temporal(is) detectado(s)
```

**Padrões Temporais Detectados:**

| Padrão | Descrição |
|--------|-----------|
| Renda Estagnada + Patrimônio Crescente | Renda não cresce mas patrimônio aumenta significativamente |
| Queda Súbita de Renda | Renda cai > 30% mas patrimônio se mantém |
| Despesas Médicas Constantes | Valores praticamente iguais por 3+ anos (estatisticamente improvável) |
| Padrão de Liquidação | Liquidação sistemática de ativos sem ganho de capital declarado |

### Informações do Arquivo

```bash
irpf-analyzer info seu-arquivo.DEC
```

Mostra informações básicas e preview do conteúdo do arquivo.

---

## Como Funciona a Análise

### Índice de Conformidade Fiscal (0-100%)

| Score | Nível | Descrição |
|-------|-------|-----------|
| 80-100% | BAIXO | Excelente - Baixo risco de malha fina |
| 50-79% | MÉDIO | Atenção - Risco moderado |
| 25-49% | ALTO | Alerta - Risco elevado |
| 0-24% | CRÍTICO | Crítico - Alto risco de malha fina |

**Quanto maior o score, mais segura está a declaração.**

### Análise de Fluxo Patrimonial

O sistema calcula se a variação patrimonial está explicada pelos recursos disponíveis:

```
Recursos Totais = Renda Declarada (salário, dividendos, rendimentos de CDB/LCA/LCI)
                + Ganho de Capital (LUCRO das alienações, não o valor bruto)
                + Lucro em Ações Estrangeiras

NÃO são contados (pois o principal já existia no patrimônio anterior):
- Valor bruto de vendas/alienações
- Valor bruto de ativos liquidados (CDB, LCA, LCI que venceram)

Recursos Disponíveis = Recursos Totais - Despesas de Vida Estimadas

Se Variação Patrimonial <= Recursos Disponíveis × 1.5 → EXPLICADO ✅
```

**Por que não contar ativos liquidados e valor de vendas?**

Se você tinha um CDB de R$ 100.000 que venceu e virou R$ 110.000 na conta:
- O patrimônio cresceu apenas R$ 10.000 (o rendimento)
- O rendimento já está incluído em "Renda Declarada" (tributação exclusiva)
- Contar os R$ 100.000 novamente seria contagem dupla

**Despesas de Vida Estimadas:**
- 30% da renda para contribuintes com renda > R$ 500.000
- 50% para renda entre R$ 250.000 e R$ 500.000
- 65% para renda entre R$ 100.000 e R$ 250.000
- 80% para renda entre R$ 50.000 e R$ 100.000
- 100% para renda abaixo de R$ 50.000

### Constantes Fiscais de Referência (IRPF 2025)

| Dedução | Limite | Observações |
|---------|--------|-------------|
| **Simplificada** | 20% até R$ 16.754,34 | Desconto automático, sem outras deduções |
| **PGBL** | 12% da renda bruta | Só para declaração completa + contribuinte INSS |
| **Educação** | R$ 3.561,50/pessoa/ano | Não inclui cursos livres, idiomas, material |
| **Dependentes** | R$ 2.275,08/dependente | Dedução fixa por dependente |
| **Despesas médicas** | Sem limite | Requer comprovação (NF, recibos) |
| **Pensão alimentícia** | Sem limite | Apenas judicial/homologada |
| **Doações incentivadas** | 6% do IR devido | Criança/Idoso, Cultura, Audiovisual |

### Verificações Realizadas

1. **Patrimônio vs Renda**
   - Variação patrimonial compatível com recursos disponíveis
   - Patrimônio alto sem rendimentos (suspeito)

2. **Deduções**
   - Despesas médicas > 15% da renda (atenção)
   - Despesas médicas > 25% da renda (alto risco)
   - Dependentes com CPF duplicado

3. **Bens e Direitos**
   - Bens que foram zerados sem venda declarada
   - Vendas declaradas na seção de alienações
   - Ações estrangeiras com lucro/prejuízo informado

4. **Otimização Fiscal**
   - Comparativo simplificada vs completa
   - Oportunidade de contribuição PGBL
   - Doações incentivadas disponíveis
   - Livro-caixa para autônomos

5. **Detecção de Padrões** 🆕
   - **Validação CPF/CNPJ**: Cálculo local de dígitos verificadores (módulo 11)
   - **Lei de Benford**: Análise estatística dos primeiros dígitos (χ² > 15.51 = anomalia)
   - **Outliers (IQR)**: Valores fora do intervalo Q1-1.5×IQR a Q3+1.5×IQR
   - **Valores Redondos**: Deduções com mais de 50% de valores "certinhos" (R$ 1.000, R$ 5.000)
   - **Depreciação de Veículos**: Variação fora de 5-15% ao ano
   - **Despesas Concentradas**: Mais de 70% das despesas médicas em um único prestador
   - **Imóveis sem Aluguel**: Múltiplos imóveis sem renda de locação declarada

### Tipos de Ativos Reconhecidos

- **Isentos de warning quando zerados:**
  - CDB, LCA, LCI (tributados na fonte)
  - Tesouro Direto, Debêntures
  - Saldos em conta corrente/poupança

- **Ações estrangeiras:**
  - Identificadas por código 12 + indicadores ($, USD, Avenue, etc.)
  - Lucro/prejuízo extraído do campo específico do arquivo DEC

---

## Estrutura do Projeto

```
irpf-analyzer/
├── src/irpf_analyzer/
│   ├── cli/                    # Interface de linha de comando
│   │   ├── app.py              # Comandos Typer
│   │   └── console.py          # Configuração Rich
│   ├── core/
│   │   ├── analyzers/          # Analisadores de risco
│   │   │   ├── consistency.py  # Verificações de consistência
│   │   │   ├── deductions.py   # Verificações de deduções
│   │   │   ├── optimization.py # Sugestões de otimização fiscal
│   │   │   ├── comparison.py   # Comparativo ano-a-ano
│   │   │   └── risk.py         # Cálculo de score
│   │   ├── models/             # Modelos Pydantic
│   │   │   ├── analysis.py     # RiskScore, Warning, Suggestion
│   │   │   ├── comparison.py   # Modelos de comparação
│   │   │   ├── declaration.py  # Declaration principal
│   │   │   ├── patrimony.py    # BemDireito, Divida
│   │   │   ├── alienation.py   # Alienações (vendas)
│   │   │   └── checklist.py    # Checklist de documentos
│   │   ├── rules/              # Regras de negócio
│   │   │   └── tax_constants.py # Constantes fiscais (limites, alíquotas)
│   │   └── services/           # Serviços de negócio
│   │       └── checklist_generator.py
│   ├── infrastructure/
│   │   ├── parsers/
│   │   │   ├── dec_parser.py   # Parser de arquivos .DEC
│   │   │   ├── dbk_parser.py   # Parser de arquivos .DBK
│   │   │   └── detector.py     # Detecção de tipo de arquivo
│   │   └── reports/
│   │       └── pdf_generator.py # Gerador de relatórios PDF
│   └── shared/
│       ├── exceptions.py       # Exceções customizadas
│       └── formatters.py       # Formatação de valores
└── tests/
    ├── fixtures/               # Arquivos de teste
    └── unit/                   # Testes unitários
```

---

## Formato dos Arquivos

### .DEC (Declaração Transmitida)

Gerado pelo programa IRPF da Receita Federal **após a transmissão** da declaração. Contém o número do recibo de entrega.

### .DBK (Backup de Declaração)

Gerado pelo programa IRPF **durante a edição** da declaração. Permite analisar a declaração antes de transmitir.

**Ambos os formatos são suportados pelo IRPF Analyzer.**

**Principais tipos de linha parseados:**

| Tipo | Descrição |
|------|-----------|
| 16 | Dados do contribuinte |
| 20 | Totais e resumos |
| 25 | Dependentes |
| 26 | Despesas médicas |
| 27 | Bens e direitos |
| 63 | Alienações (vendas) |

---

## Desenvolvimento

### Executar Testes

```bash
uv run pytest
```

### Executar com Coverage

```bash
uv run pytest --cov=irpf_analyzer
```

### Lint e Formatação

```bash
uv run ruff check .
uv run ruff format .
```

---

## Segurança e Privacidade

- **Zero rede**: Nenhuma chamada de rede é feita
- **Zero telemetria**: Sem coleta de dados
- **Processamento local**: Tudo roda na sua máquina
- **Código aberto**: Você pode auditar o código

---

## Limitações

- Suporta arquivos `.DEC` e `.DBK`
- Parsing baseado no leiaute do IRPF 2025 (ano-calendário 2024)
- Algumas posições de campos podem variar entre versões do programa IRPF

---

## Contribuindo

Contribuições são bem-vindas! Por favor:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

---

## Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

---

## Aviso Legal

Esta ferramenta é apenas para fins informativos e educacionais. Não substitui a consulta a um contador ou profissional de impostos. O desenvolvedor não se responsabiliza por decisões tomadas com base nas análises fornecidas.

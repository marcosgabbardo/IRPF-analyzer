# IRPF Analyzer

**Analisador de riscos e otimização de declaração IRPF**

Uma ferramenta CLI em Python para analisar arquivos `.DEC` (declarações transmitidas do IRPF) e identificar potenciais riscos de malha fina, além de sugerir otimizações fiscais.

> **100% offline** - Seus dados nunca saem do seu computador.

---

## Funcionalidades

- **Análise de Risco de Malha Fina**
  - Score de risco de 0 a 100
  - Detecção de inconsistências patrimônio vs renda
  - Verificação de despesas médicas proporcionalmente altas
  - Identificação de dependentes duplicados
  - Cruzamento de vendas declaradas (alienações) com bens zerados

- **Suporte a Ativos Estrangeiros**
  - Parsing de lucro/prejuízo declarado em ações estrangeiras
  - Identificação de vendas via corretoras internacionais (Avenue, Interactive Brokers)

- **Sugestões de Otimização**
  - Comparativo declaração completa vs simplificada
  - Oportunidades de dedução PGBL

- **Interface Rica**
  - Output colorido no terminal
  - Tabelas formatadas com Rich
  - Resumo patrimonial detalhado

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

# Execute
irpf-analyzer --help
```

---

## Uso

### Análise Completa

```bash
irpf-analyzer analyze seu-arquivo.DEC
```

**Exemplo de saída:**

```
╭───── IRPF Analyzer - Declaração ──────╮
│ Contribuinte: FULANO DE TAL          │
│ CPF: ***.***.***.XX                  │
│ Exercício: 2025 (Ano-calendário 2024)│
│ Tipo: COMPLETA                       │
╰──────────────────────────────────────╯

╭─ 🎯 Score de Risco - Malha Fina ─╮
│ Score: 2/100                     │
│ Nível: BAIXO                     │
╰──────────────────────────────────╯

📋 Avisos:
  • Venda declarada: EMPRESA XYZ... (alienação encontrada)

💡 Sugestões de Otimização:
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
│ Sugestão              │ Descrição                │ Economia Potencial│
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ Considere declaração  │ Suas deduções são        │ -                 │
│ simplificada          │ menores que o desconto   │                   │
│                       │ máximo simplificado      │                   │
└───────────────────────┴──────────────────────────┴───────────────────┘

✅ Declaração com baixo risco de malha fina!
```

### Informações do Arquivo

```bash
irpf-analyzer info seu-arquivo.DEC
```

Mostra informações básicas e preview do conteúdo do arquivo.

---

## Como Funciona a Análise

### Score de Risco (0-100)

| Score | Nível | Descrição |
|-------|-------|-----------|
| 0-20 | BAIXO | Declaração com baixo risco |
| 21-50 | MÉDIO | Revise os pontos destacados |
| 51-75 | ALTO | Atenção aos pontos críticos |
| 76-100 | CRÍTICO | Alto risco de malha fina |

### Verificações Realizadas

1. **Patrimônio vs Renda**
   - Variação patrimonial compatível com renda declarada
   - Patrimônio alto sem rendimentos (suspeito)

2. **Deduções**
   - Despesas médicas > 15% da renda (atenção)
   - Despesas médicas > 25% da renda (alto risco)
   - Dependentes com CPF duplicado

3. **Bens e Direitos**
   - Bens que foram zerados sem venda declarada
   - Vendas declaradas na seção de alienações
   - Ações estrangeiras com lucro/prejuízo informado

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
│   │   │   └── risk.py         # Cálculo de score
│   │   └── models/             # Modelos Pydantic
│   │       ├── analysis.py     # RiskScore, Warning, Suggestion
│   │       ├── declaration.py  # Declaration principal
│   │       ├── patrimony.py    # BemDireito, Divida
│   │       └── alienation.py   # Alienações (vendas)
│   ├── infrastructure/
│   │   └── parsers/
│   │       ├── dec_parser.py   # Parser de arquivos .DEC
│   │       └── detector.py     # Detecção de tipo de arquivo
│   └── shared/
│       ├── exceptions.py       # Exceções customizadas
│       └── formatters.py       # Formatação de valores
└── tests/
    ├── fixtures/               # Arquivos de teste
    └── unit/                   # Testes unitários
```

---

## Formato do Arquivo .DEC

O arquivo `.DEC` é gerado pelo programa IRPF da Receita Federal após a transmissão da declaração. É um arquivo de texto com layout posicional (campos em posições fixas).

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

- Suporta apenas arquivos `.DEC` (declarações transmitidas)
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

"""Document checklist generator based on declaration entries."""

from decimal import Decimal

from irpf_analyzer.core.models.checklist import (
    Document,
    DocumentCategory,
    DocumentChecklist,
    DocumentPriority,
)
from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import GrupoBem, TipoDeducao
from irpf_analyzer.shared.formatters import format_currency


class DocumentChecklistGenerator:
    """Generates document checklist based on declaration entries."""

    def __init__(self, declaration: Declaration):
        self.declaration = declaration
        self.documentos: list[Document] = []

    def generate(self) -> DocumentChecklist:
        """Generate complete document checklist."""
        # Analyze each section of the declaration
        self._process_rendimentos()
        self._process_deducoes()
        self._process_bens_direitos()
        self._process_dependentes()
        self._process_alienacoes()

        # Always add basic documents
        self._add_basic_documents()

        return DocumentChecklist(
            ano_exercicio=self.declaration.ano_exercicio,
            documentos=self.documentos,
        )

    def _add_basic_documents(self) -> None:
        """Add basic required documents for any declaration."""
        self.documentos.append(
            Document(
                nome="Documento de identidade",
                descricao="RG, CNH ou outro documento oficial com foto",
                categoria=DocumentCategory.RENDIMENTOS,
                prioridade=DocumentPriority.OBRIGATORIO,
            )
        )
        self.documentos.append(
            Document(
                nome="Comprovante de CPF",
                descricao="CPF do titular e de todos os dependentes",
                categoria=DocumentCategory.DEPENDENTES,
                prioridade=DocumentPriority.OBRIGATORIO,
            )
        )
        self.documentos.append(
            Document(
                nome="Recibo da declaração anterior",
                descricao=f"Recibo de entrega do IRPF {self.declaration.ano_exercicio - 1}",
                categoria=DocumentCategory.RENDIMENTOS,
                prioridade=DocumentPriority.RECOMENDADO,
                referencia="Para importação de dados",
            )
        )

    def _process_rendimentos(self) -> None:
        """Process income entries and add required documents."""
        # Group by source (fonte pagadora)
        fontes_cnpj: set[str] = set()

        for rendimento in self.declaration.rendimentos:
            if rendimento.fonte_pagadora and rendimento.fonte_pagadora.cnpj:
                cnpj = rendimento.fonte_pagadora.cnpj
                if cnpj not in fontes_cnpj:
                    fontes_cnpj.add(cnpj)
                    nome_fonte = rendimento.fonte_pagadora.nome or "Fonte pagadora"
                    self.documentos.append(
                        Document(
                            nome="Informe de Rendimentos",
                            descricao=f"Informe de rendimentos de {nome_fonte}",
                            categoria=DocumentCategory.RENDIMENTOS,
                            prioridade=DocumentPriority.OBRIGATORIO,
                            fonte=nome_fonte,
                            referencia=f"CNPJ: {self._format_cnpj(cnpj)}",
                            valor=format_currency(rendimento.valor) if rendimento.valor else None,
                        )
                    )

        # Check for specific income types
        total_tributavel = self.declaration.total_rendimentos_tributaveis
        if total_tributavel > 0:
            self.documentos.append(
                Document(
                    nome="Comprovante de rendimentos tributáveis",
                    descricao="Holerites, contracheques ou recibos de pagamento",
                    categoria=DocumentCategory.RENDIMENTOS,
                    prioridade=DocumentPriority.RECOMENDADO,
                    valor=format_currency(total_tributavel),
                )
            )

        # Check for bank account income (investments)
        total_exclusivos = self.declaration.total_rendimentos_exclusivos
        if total_exclusivos > 0:
            self.documentos.append(
                Document(
                    nome="Informes de rendimentos financeiros",
                    descricao="Informes de bancos e corretoras sobre aplicações financeiras",
                    categoria=DocumentCategory.RENDIMENTOS,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    fonte="Bancos e corretoras",
                    valor=format_currency(total_exclusivos),
                )
            )

    def _process_deducoes(self) -> None:
        """Process deduction entries and add required documents."""
        # Group deductions by type for cleaner output
        deducoes_por_tipo: dict[TipoDeducao, list] = {}
        for deducao in self.declaration.deducoes:
            if deducao.tipo not in deducoes_por_tipo:
                deducoes_por_tipo[deducao.tipo] = []
            deducoes_por_tipo[deducao.tipo].append(deducao)

        # Medical expenses
        if TipoDeducao.DESPESAS_MEDICAS in deducoes_por_tipo:
            deducoes = deducoes_por_tipo[TipoDeducao.DESPESAS_MEDICAS]
            total = sum(d.valor for d in deducoes)

            # Add general medical document
            self.documentos.append(
                Document(
                    nome="Recibos de despesas médicas",
                    descricao="Recibos, notas fiscais de médicos, dentistas, hospitais, laboratórios",
                    categoria=DocumentCategory.DEDUCOES,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    valor=format_currency(total),
                )
            )

            # Add specific documents for each provider
            prestadores_vistos: set[str] = set()
            for deducao in deducoes:
                if deducao.cnpj_prestador and deducao.cnpj_prestador not in prestadores_vistos:
                    prestadores_vistos.add(deducao.cnpj_prestador)
                    nome = deducao.nome_prestador or "Prestador de saúde"
                    self.documentos.append(
                        Document(
                            nome=f"Recibo/NF - {nome[:40]}",
                            descricao=f"Comprovante de pagamento de serviço de saúde",
                            categoria=DocumentCategory.DEDUCOES,
                            prioridade=DocumentPriority.OBRIGATORIO,
                            fonte=nome,
                            referencia=f"CNPJ: {self._format_cnpj(deducao.cnpj_prestador)}",
                            valor=format_currency(deducao.valor),
                        )
                    )

        # Education expenses
        if TipoDeducao.DESPESAS_EDUCACAO in deducoes_por_tipo:
            deducoes = deducoes_por_tipo[TipoDeducao.DESPESAS_EDUCACAO]
            total = sum(d.valor for d in deducoes)

            self.documentos.append(
                Document(
                    nome="Comprovantes de despesas com educação",
                    descricao="Recibos de mensalidades escolares, faculdades, cursos técnicos",
                    categoria=DocumentCategory.DEDUCOES,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    valor=format_currency(total),
                )
            )

            # Specific institutions
            instituicoes_vistas: set[str] = set()
            for deducao in deducoes:
                if deducao.cnpj_prestador and deducao.cnpj_prestador not in instituicoes_vistas:
                    instituicoes_vistas.add(deducao.cnpj_prestador)
                    nome = deducao.nome_prestador or "Instituição de ensino"
                    self.documentos.append(
                        Document(
                            nome=f"Declaração - {nome[:40]}",
                            descricao="Declaração de pagamentos da instituição de ensino",
                            categoria=DocumentCategory.DEDUCOES,
                            prioridade=DocumentPriority.OBRIGATORIO,
                            fonte=nome,
                            referencia=f"CNPJ: {self._format_cnpj(deducao.cnpj_prestador)}",
                            valor=format_currency(deducao.valor),
                        )
                    )

        # Pension/alimony
        if TipoDeducao.PENSAO_ALIMENTICIA in deducoes_por_tipo:
            deducoes = deducoes_por_tipo[TipoDeducao.PENSAO_ALIMENTICIA]
            total = sum(d.valor for d in deducoes)

            self.documentos.append(
                Document(
                    nome="Comprovantes de pensão alimentícia",
                    descricao="Decisão judicial/acordo + comprovantes de pagamento",
                    categoria=DocumentCategory.DEDUCOES,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    valor=format_currency(total),
                )
            )

        # Private pension (PGBL)
        if TipoDeducao.PREVIDENCIA_PRIVADA in deducoes_por_tipo:
            deducoes = deducoes_por_tipo[TipoDeducao.PREVIDENCIA_PRIVADA]
            total = sum(d.valor for d in deducoes)

            self.documentos.append(
                Document(
                    nome="Informe de contribuições PGBL",
                    descricao="Informe anual de contribuições da entidade de previdência",
                    categoria=DocumentCategory.DEDUCOES,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    fonte="Entidade de previdência",
                    valor=format_currency(total),
                )
            )

        # Official pension (INSS)
        if TipoDeducao.PREVIDENCIA_OFICIAL in deducoes_por_tipo:
            deducoes = deducoes_por_tipo[TipoDeducao.PREVIDENCIA_OFICIAL]
            total = sum(d.valor for d in deducoes)

            self.documentos.append(
                Document(
                    nome="Comprovante de contribuição INSS",
                    descricao="Já incluído no informe de rendimentos ou carnê INSS",
                    categoria=DocumentCategory.DEDUCOES,
                    prioridade=DocumentPriority.RECOMENDADO,
                    valor=format_currency(total),
                )
            )

    def _process_bens_direitos(self) -> None:
        """Process assets and add required documents."""
        # Group assets by type - use description-based detection for better accuracy
        imoveis: list = []
        veiculos: list = []
        investimentos: list = []
        acoes_estrangeiras: list = []
        acoes_nacionais: list = []
        criptoativos: list = []
        participacoes: list = []
        outros: list = []

        for bem in self.declaration.bens_direitos:
            desc_upper = bem.discriminacao.upper()

            # Detect type from description (more reliable than grupo code)
            if self._is_foreign_stock(desc_upper):
                acoes_estrangeiras.append(bem)
            elif self._is_crypto(desc_upper):
                criptoativos.append(bem)
            elif self._is_real_estate(desc_upper):
                imoveis.append(bem)
            elif self._is_vehicle(desc_upper):
                veiculos.append(bem)
            elif self._is_company_participation(desc_upper):
                participacoes.append(bem)
            elif self._is_financial_investment(desc_upper):
                investimentos.append(bem)
            elif bem.grupo == GrupoBem.IMOVEIS:
                imoveis.append(bem)
            elif bem.grupo == GrupoBem.VEICULOS:
                veiculos.append(bem)
            elif bem.grupo in (
                GrupoBem.APLICACOES_FINANCEIRAS,
                GrupoBem.POUPANCA,
                GrupoBem.DEPOSITOS_VISTA,
                GrupoBem.FUNDOS,
            ):
                investimentos.append(bem)
            elif bem.grupo == GrupoBem.CRIPTOATIVOS:
                criptoativos.append(bem)
            elif bem.grupo == GrupoBem.PARTICIPACOES_SOCIETARIAS:
                participacoes.append(bem)
            else:
                outros.append(bem)

        # Real estate
        for bem in imoveis:
            self.documentos.append(
                Document(
                    nome="Escritura/Contrato de imóvel",
                    descricao="Escritura pública ou contrato de compra e venda",
                    categoria=DocumentCategory.BENS_DIREITOS,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    referencia=bem.discriminacao[:60],
                    valor=format_currency(bem.situacao_atual),
                )
            )
            self.documentos.append(
                Document(
                    nome="IPTU do imóvel",
                    descricao="Carnê do IPTU para confirmar dados do imóvel",
                    categoria=DocumentCategory.BENS_DIREITOS,
                    prioridade=DocumentPriority.RECOMENDADO,
                    referencia=bem.discriminacao[:60],
                )
            )

        # Vehicles
        for bem in veiculos:
            self.documentos.append(
                Document(
                    nome="Documento do veículo (CRLV)",
                    descricao="CRLV ou documento de propriedade do veículo",
                    categoria=DocumentCategory.BENS_DIREITOS,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    referencia=bem.discriminacao[:60],
                    valor=format_currency(bem.situacao_atual),
                )
            )

        # Investments
        if investimentos:
            self.documentos.append(
                Document(
                    nome="Informes de aplicações financeiras",
                    descricao="Informes de rendimentos de bancos e corretoras (posição em 31/12)",
                    categoria=DocumentCategory.BENS_DIREITOS,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    fonte="Bancos e corretoras",
                )
            )

        # Foreign stocks
        if acoes_estrangeiras:
            self.documentos.append(
                Document(
                    nome="Extratos de corretora internacional",
                    descricao="Extratos de Avenue, Interactive Brokers ou similar",
                    categoria=DocumentCategory.BENS_DIREITOS,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    fonte="Corretora internacional",
                )
            )
            self.documentos.append(
                Document(
                    nome="Controle de operações em bolsa estrangeira",
                    descricao="Planilha com compras, vendas, lucros/prejuízos em USD e BRL",
                    categoria=DocumentCategory.BENS_DIREITOS,
                    prioridade=DocumentPriority.OBRIGATORIO,
                )
            )
            # Individual stocks with profit/loss
            for bem in acoes_estrangeiras:
                if bem.lucro_prejuizo != Decimal("0"):
                    self.documentos.append(
                        Document(
                            nome=f"Comprovante de operação",
                            descricao=f"Notas de corretagem ou extrato de operações",
                            categoria=DocumentCategory.ALIENACOES,
                            prioridade=DocumentPriority.OBRIGATORIO,
                            referencia=bem.discriminacao[:50],
                            valor=f"Lucro/Prejuízo: {format_currency(bem.lucro_prejuizo)}",
                        )
                    )

        # Cryptocurrencies
        if criptoativos:
            self.documentos.append(
                Document(
                    nome="Extratos de exchanges de criptomoedas",
                    descricao="Histórico de operações das corretoras de cripto",
                    categoria=DocumentCategory.BENS_DIREITOS,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    fonte="Exchanges (Binance, Mercado Bitcoin, etc.)",
                )
            )
            self.documentos.append(
                Document(
                    nome="Controle de custódia de criptoativos",
                    descricao="Planilha com quantidade, preço médio e valor atual",
                    categoria=DocumentCategory.BENS_DIREITOS,
                    prioridade=DocumentPriority.OBRIGATORIO,
                )
            )

        # Company participations
        if participacoes:
            self.documentos.append(
                Document(
                    nome="Contrato social das empresas",
                    descricao="Contrato social atualizado com participação societária",
                    categoria=DocumentCategory.BENS_DIREITOS,
                    prioridade=DocumentPriority.OBRIGATORIO,
                )
            )
            for bem in participacoes:
                self.documentos.append(
                    Document(
                        nome="Documentos societários",
                        descricao="Contrato social, alterações e balancetes",
                        categoria=DocumentCategory.BENS_DIREITOS,
                        prioridade=DocumentPriority.OBRIGATORIO,
                        referencia=bem.discriminacao[:60],
                        valor=format_currency(bem.situacao_atual),
                    )
                )

    def _process_dependentes(self) -> None:
        """Process dependents and add required documents."""
        for dependente in self.declaration.dependentes:
            nome = dependente.nome or "Dependente"

            self.documentos.append(
                Document(
                    nome=f"Documentos de {nome[:30]}",
                    descricao="CPF, certidão de nascimento/casamento, comprovante de dependência",
                    categoria=DocumentCategory.DEPENDENTES,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    referencia=f"CPF: {self._format_cpf(dependente.cpf)}" if dependente.cpf else None,
                )
            )

            # If dependent is student (education deduction)
            if dependente.data_nascimento:
                # Rough check for student age
                from datetime import date
                idade = self.declaration.ano_exercicio - 1 - dependente.data_nascimento.year
                if 5 <= idade <= 24:
                    self.documentos.append(
                        Document(
                            nome=f"Comprovante de matrícula - {nome[:25]}",
                            descricao="Declaração de matrícula da escola/faculdade",
                            categoria=DocumentCategory.DEPENDENTES,
                            prioridade=DocumentPriority.RECOMENDADO,
                            referencia=nome,
                        )
                    )

    def _process_alienacoes(self) -> None:
        """Process sales (alienações) and add required documents."""
        for alienacao in self.declaration.alienacoes:
            nome_bem = alienacao.nome_bem or "Bem alienado"

            self.documentos.append(
                Document(
                    nome="Contrato/Escritura de venda",
                    descricao=f"Documento de alienação de {nome_bem[:40]}",
                    categoria=DocumentCategory.ALIENACOES,
                    prioridade=DocumentPriority.OBRIGATORIO,
                    referencia=nome_bem[:60],
                    valor=format_currency(alienacao.valor_alienacao) if alienacao.valor_alienacao else None,
                )
            )

            if alienacao.valor_alienacao and alienacao.valor_alienacao > Decimal("35000"):
                self.documentos.append(
                    Document(
                        nome="GCAP (Programa Ganho de Capital)",
                        descricao="Demonstrativo de apuração do ganho de capital",
                        categoria=DocumentCategory.ALIENACOES,
                        prioridade=DocumentPriority.OBRIGATORIO,
                        referencia=nome_bem[:60],
                    )
                )

    def _is_foreign_stock(self, desc: str) -> bool:
        """Check if description indicates foreign stock."""
        indicators = [
            "USD", "US$", "AVENUE", "INTERACTIVE BROKERS", "IBKR",
            "CHARLES SCHWAB", "DRIVEWEALTH", "CORRETORA INTERNACIONAL",
            "BOLSA AMERICANA", "NYSE", "NASDAQ",
        ]
        # Also check for $ symbol but only with context
        if "$" in desc and any(w in desc for w in ["COTACAO", "PRECO", "ACAO", "AÇÕES", "STOCK"]):
            return True
        return any(ind in desc for ind in indicators)

    def _is_crypto(self, desc: str) -> bool:
        """Check if description indicates cryptocurrency."""
        indicators = [
            "BITCOIN", "BTC", "ETHEREUM", "ETH", "CRIPTOATIVO",
            "CRIPTOMOEDA", "CRYPTO", "LITECOIN", "RIPPLE", "XRP",
            "CARDANO", "ADA", "SOLANA", "SOL", "BINANCE",
        ]
        return any(ind in desc for ind in indicators)

    def _is_real_estate(self, desc: str) -> bool:
        """Check if description indicates real estate."""
        indicators = [
            "APARTAMENTO", "CASA", "TERRENO", "IMOVEL", "IMÓVEL",
            "LOTE", "SALA COMERCIAL", "ESCRITORIO", "ESCRITÓRIO",
            "GALPAO", "GALPÃO", "FAZENDA", "SITIO", "SÍTIO",
            "CHACARA", "CHÁCARA", "LOJA", "BOX", "GARAGEM",
        ]
        return any(ind in desc for ind in indicators)

    def _is_vehicle(self, desc: str) -> bool:
        """Check if description indicates vehicle."""
        indicators = [
            "VEICULO", "VEÍCULO", "AUTOMOVEL", "AUTOMÓVEL",
            "CARRO", "MOTO", "MOTOCICLETA", "CAMINHAO", "CAMINHÃO",
            "RENAVAM", "PLACA", " TSI ", " TDI ", "VOLKSWAGEN",
            "TOYOTA", "HONDA", "CHEVROLET", "FIAT", "FORD",
            "JEEP", "HYUNDAI", "KIA", "NISSAN", "MERCEDES",
            "BMW", "AUDI", "TAOS",
        ]
        return any(ind in desc for ind in indicators)

    def _is_company_participation(self, desc: str) -> bool:
        """Check if description indicates company participation."""
        indicators = [
            "EMPRESA", "CAPITAL SOCIAL", "QUOTAS", "COTAS",
            "PARTICIPACAO SOCIETARIA", "PARTICIPAÇÃO SOCIETÁRIA",
            "SOCIO", "SÓCIO", "S/S LTDA", "S.A.", " SA ",
            "LTDA", "EIRELI", "MEI",
        ]
        # Exclude if it's clearly foreign stock
        if self._is_foreign_stock(desc):
            return False
        return any(ind in desc for ind in indicators)

    def _is_financial_investment(self, desc: str) -> bool:
        """Check if description indicates financial investment."""
        indicators = [
            "CDB", "LCA", "LCI", "LF ", "RENDA FIXA",
            "POUPANCA", "POUPANÇA", "TESOURO", "DEBENTURE", "DEBÊNTURE",
            "FUNDO", "FII", "FIDC", "COE", "APLICACAO", "APLICAÇÃO",
            "SALDO EM CONTA", "CONTA CORRENTE", "INVESTIMENTO",
        ]
        return any(ind in desc for ind in indicators)

    def _format_cnpj(self, cnpj: str) -> str:
        """Format CNPJ for display."""
        cnpj = cnpj.replace(".", "").replace("/", "").replace("-", "")
        if len(cnpj) == 14:
            return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
        return cnpj

    def _format_cpf(self, cpf: str) -> str:
        """Format CPF for display (masked)."""
        cpf = cpf.replace(".", "").replace("-", "")
        if len(cpf) == 11:
            return f"***.{cpf[3:6]}.{cpf[6:9]}-**"
        return cpf


def generate_checklist(declaration: Declaration) -> DocumentChecklist:
    """Generate document checklist from declaration."""
    generator = DocumentChecklistGenerator(declaration)
    return generator.generate()

from uuid import UUID

from src.application.ports.inbound.contract_service_port import (
    ContractServicePort,
    GetContractOutput,
    SubmitContractInput,
    SubmitContractOutput,
)
from src.application.ports.outbound.borrower_repository_port import (
    BorrowerRepositoryPort,
)
from src.application.ports.outbound.contract_repository_port import (
    ContractRepositoryPort,
)
from src.application.ports.outbound.event_publisher_port import EventPublisherPort
from src.domain.borrowers.entity import Borrower
from src.domain.borrowers.value_objects import CPF, BorrowerName, Email, Phone
from src.domain.contracts.entity import Contract
from src.domain.contracts.events import ContractSubmittedEvent
from src.domain.contracts.exceptions import (
    ContractNotFoundError,
    DuplicateIdempotencyKeyError,
)
from src.domain.contracts.value_objects import (
    Amount,
    DisbursementDate,
    Installments,
    InterestRate,
)


class SubmitContractService(ContractServicePort):
    def __init__(
        self,
        borrower_repo: BorrowerRepositoryPort,
        contract_repo: ContractRepositoryPort,
        event_publisher: EventPublisherPort,
    ) -> None:
        self._borrower_repo = borrower_repo
        self._contract_repo = contract_repo
        self._event_publisher = event_publisher

    async def submit(self, input: SubmitContractInput) -> SubmitContractOutput:
        # value objects validam no __post_init__; qualquer dado inválido levanta ValueError aqui
        cpf = CPF(input.cpf)
        disbursement_date = DisbursementDate(input.disbursement_date)
        amount = Amount(input.amount_cents)
        interest_rate = InterestRate(input.interest_rate)
        installments = Installments(input.installments)
        name = BorrowerName(input.name)
        email = Email(input.email) if input.email else None
        phone = Phone(input.phone) if input.phone else None

        # mesmo CPF = mesmo tomador; lookup por hash pra não precisar descriptografar tudo
        borrower = await self._borrower_repo.get_by_cpf_hash(cpf.to_hash())
        if borrower is None:
            borrower = Borrower.create(cpf=cpf, name=name, email=email, phone=phone)
            await self._borrower_repo.save(borrower)

        contract = Contract.create(
            idempotency_key=input.idempotency_key,
            product_id=input.product_id,
            borrower_id=borrower.id,
            amount=amount,
            interest_rate=interest_rate,
            installments=installments,
            disbursement_date=disbursement_date,
            external_reference=input.external_reference,
        )

        try:
            contract = await self._contract_repo.save(contract)
        except DuplicateIdempotencyKeyError as exc:
            # chave já existe — devolve o contrato original sem reprocessar
            existing = exc.existing
            return SubmitContractOutput(
                contract_id=existing.id,
                status=existing.current_status.value,
                created_at=existing.created_at,
                product_id=existing.product_id,
                is_duplicate=True,
            )

        # outbox na mesma transação; get_db() faz commit no final, então ou salva tudo ou nada
        event = ContractSubmittedEvent(
            aggregate_id=contract.id,
            payload={
                "contract_id": str(contract.id),
                "product_id": str(contract.product_id),
                "borrower_id": str(contract.borrower_id),
                "amount_cents": contract.amount.amount_cents,
                "interest_rate": contract.interest_rate.value,
                "installments": contract.installments.value,
                "disbursement_date": contract.disbursement_date.value.isoformat(),
                "status": contract.current_status.value,
            },
        )
        await self._event_publisher.publish(event)

        return SubmitContractOutput(
            contract_id=contract.id,
            status=contract.current_status.value,
            created_at=contract.created_at,
            product_id=contract.product_id,
        )

    async def get_by_id(self, contract_id: UUID) -> GetContractOutput:
        contract = await self._contract_repo.get_by_id(contract_id)
        if contract is None:
            raise ContractNotFoundError(str(contract_id))
        return GetContractOutput(
            contract_id=contract.id,
            status=contract.current_status.value,
            product_id=contract.product_id,
            borrower_id=contract.borrower_id,
            amount_cents=contract.amount.amount_cents,
            interest_rate=float(contract.interest_rate.value),
            installments=contract.installments.value,
            disbursement_date=contract.disbursement_date.value,
            external_reference=contract.external_reference,
            created_at=contract.created_at,
            updated_at=contract.updated_at,
        )

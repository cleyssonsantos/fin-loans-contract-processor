from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class ContractSubmittedEvent:
    aggregate_id: UUID
    payload: dict
    aggregate_type: str = field(default="contract")
    event_type: str = field(default="contract.submitted")

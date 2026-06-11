class BorrowerNotFoundError(Exception):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"tomador não encontrado: {identifier}")
        self.identifier = identifier

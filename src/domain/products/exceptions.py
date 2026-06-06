from uuid import UUID


class ProductSlugAlreadyExistsError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"já existe um produto com o slug '{slug}'")
        self.slug = slug


class ProductNotFoundError(Exception):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"produto não encontrado: {identifier}")
        self.identifier = identifier


class ProductAlreadyInactiveError(Exception):
    def __init__(self, product_id: UUID) -> None:
        super().__init__(f"produto {product_id} já está inativo")
        self.product_id = product_id


class WebhookConfigNotFoundError(Exception):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"configuração de webhook não encontrada: {identifier}")
        self.identifier = identifier


class WebhookConfigAlreadyInactiveError(Exception):
    def __init__(self, config_id: UUID) -> None:
        super().__init__(f"configuração de webhook {config_id} já está inativa")
        self.config_id = config_id


class NotificationConfigNotFoundError(Exception):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"configuração de notificação não encontrada: {identifier}")
        self.identifier = identifier


class NotificationConfigAlreadyInactiveError(Exception):
    def __init__(self, config_id: UUID) -> None:
        super().__init__(f"configuração de notificação {config_id} já está inativa")
        self.config_id = config_id

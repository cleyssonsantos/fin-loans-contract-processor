import logging
import re

_SENSITIVE_PATTERN = re.compile(
    r'(?i)'
    r'('
    r'(?:cpf|email|phone|api[_\-]?key|password|token|authorization|name_encrypted)'
    r')'
    r'(\s*[:=]\s*)'                          # separador (= ou :)
    r'([^\s,\}\]"\']+|"[^"]*"|\'[^\']*\')', # valor até whitespace ou vírgula
    re.IGNORECASE,
)

_MASK = r'\1\2[REDACTED]'


class SensitiveDataFilter(logging.Filter):
    """Remove dados sensíveis de qualquer mensagem antes de ela ser gravada no log.

    Aplica substituição por regex em LogRecord.getMessage(), mascarando valores
    de campos como cpf, email, api_key, token, authorization, etc.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _SENSITIVE_PATTERN.sub(_MASK, str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: _SENSITIVE_PATTERN.sub(_MASK, str(v))
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _SENSITIVE_PATTERN.sub(_MASK, a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def setup_logging() -> None:
    """Instala SensitiveDataFilter no root logger e no logger do uvicorn.

    Chamado no lifespan do app para garantir que nenhum log emitido
    após a inicialização contenha dados sensíveis.
    """
    sensitive_filter = SensitiveDataFilter()
    for logger_name in ("", "uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(logger_name).addFilter(sensitive_filter)

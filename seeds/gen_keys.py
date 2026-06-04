#!/usr/bin/env python3
"""
Gera as chaves JWT RS256 e a ENCRYPTION_KEY para desenvolvimento local.

Uso:
    python seeds/gen_keys.py          # gera as chaves (falha se já existirem)
    python seeds/gen_keys.py --force  # sobrescreve arquivos existentes

Ou via Makefile (dentro do Docker/devcontainer):
    make gen-keys
"""
import argparse
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = PROJECT_ROOT / "secrets"
PRIVATE_KEY_PATH = SECRETS_DIR / "private.pem"
PUBLIC_KEY_PATH = SECRETS_DIR / "public.pem"
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"


def _check_gitignore() -> None:
    if not GITIGNORE_PATH.is_file():
        return
    if "secrets/" not in GITIGNORE_PATH.read_text():
        print("  AVISO: 'secrets/' não encontrado no .gitignore — adicione antes de commitar!")


def generate(force: bool) -> None:
    SECRETS_DIR.mkdir(exist_ok=True)

    existing = [p for p in [PRIVATE_KEY_PATH, PUBLIC_KEY_PATH] if p.exists()]
    if existing and not force:
        names = " e ".join(p.name for p in existing)
        print(f"\n  Arquivo(s) já existem: {names}")
        print("  Use --force para sobrescrever.\n")
        sys.exit(1)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    PRIVATE_KEY_PATH.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    PRIVATE_KEY_PATH.chmod(0o600)  # somente owner pode ler
    print(f"  [+] {PRIVATE_KEY_PATH.relative_to(PROJECT_ROOT)} gerado (RSA 2048-bit, PKCS8)")

    PUBLIC_KEY_PATH.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"  [+] {PUBLIC_KEY_PATH.relative_to(PROJECT_ROOT)} gerado")

    # 24 bytes aleatórios → 32 chars URL-safe (exatamente 32 bytes em UTF-8)
    encryption_key = secrets.token_urlsafe(24)
    app_secret_key = secrets.token_urlsafe(32)

    sep = "─" * 52
    print(f"\nCole no seu .env:\n{sep}")
    print(f"APP_SECRET_KEY={app_secret_key}")
    print(f"ENCRYPTION_KEY={encryption_key}")
    print(f"{sep}\n")

    _check_gitignore()
    print("Nunca commite o diretorio secrets/ nem o .env com valores reais.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera chaves JWT RS256 e ENCRYPTION_KEY para desenvolvimento."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescreve arquivos existentes em secrets/",
    )
    args = parser.parse_args()
    generate(force=args.force)


if __name__ == "__main__":
    main()

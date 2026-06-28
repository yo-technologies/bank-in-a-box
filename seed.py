"""
Идемпотентный сидинг демо-данных при старте приложения.

Минимальный детерминированный сид (НЕ рандомный) для демонстрации:
несколько клиентов одной команды + по счёту у каждого, капитал банка и
авто-одобрение согласий. Выполняется через ORM, поэтому схема БД всегда
совпадает с моделями.

Параметризация через env:
  TEAM_CLIENT_ID      — код команды (например, team218). По умолчанию team200.
  TEAM_CLIENT_SECRET  — секрет команды для POST /auth/bank-token.
  SEED_CLIENTS        — сколько клиентов завести (по умолчанию 2).
  SEED_BALANCE        — стартовый баланс счёта (по умолчанию 1000000).

person_id одинаковы во всех банках (team218-1, team218-2, …), но номера
счетов различаются банком (цифра в 7-й позиции) — это позволяет
демонстрировать межбанковские переводы между vbank/abank/sbank.
"""
import os
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from .models import Client, Account, BankCapital, BankSettings, Team
    from .config import config
except ImportError:
    from models import Client, Account, BankCapital, BankSettings, Team
    from config import config


# Различающая цифра банка в номере счёта (7-я позиция).
BANK_DIGIT = {"vbank": "1", "abank": "2", "sbank": "3"}

TEAM_ID = os.getenv("TEAM_CLIENT_ID", "team200")
TEAM_SECRET = os.getenv("TEAM_CLIENT_SECRET", "5OAaa4DYzYKfnOU6zbR34ic5qMm7VSMB")
SEED_CLIENTS = int(os.getenv("SEED_CLIENTS", "2"))
SEED_BALANCE = Decimal(os.getenv("SEED_BALANCE", "1000000"))


def _account_number(bank_digit: str, index: int) -> str:
    """20-значный номер счёта, уникальный в рамках банка."""
    return f"408178{bank_digit}{index:013d}"


async def seed_if_empty(session: AsyncSession) -> bool:
    """
    Засидить демо-данные, если БД пуста. Returns True если сид выполнен.
    """
    existing = await session.execute(select(func.count(Client.id)))
    if (existing.scalar() or 0) > 0:
        return False

    bank_code = config.BANK_CODE
    digit = BANK_DIGIT.get(bank_code, "9")

    # Команда — для POST /auth/bank-token
    team = await session.execute(select(Team).where(Team.client_id == TEAM_ID))
    if team.scalar_one_or_none() is None:
        session.add(Team(
            client_id=TEAM_ID,
            client_secret=TEAM_SECRET,
            team_name=f"{TEAM_ID} (seed)",
            is_active=True,
        ))

    # Авто-одобрение согласий — чтобы межбанк работал turnkey
    for key, value in [
        ("auto_approve_consents", "true"),
        ("auto_approve_payment_consents", "true"),
        ("bank_code", bank_code),
    ]:
        session.add(BankSettings(key=key, value=value))

    # Капитал банка
    session.add(BankCapital(
        bank_code=bank_code,
        capital=Decimal("3500000.00"),
        initial_capital=Decimal("3500000.00"),
        total_deposits=Decimal("0"),
        total_loans=Decimal("0"),
    ))

    # Несколько клиентов команды + по счёту у каждого
    for i in range(1, SEED_CLIENTS + 1):
        client = Client(
            person_id=f"{TEAM_ID}-{i}",
            client_type="individual",
            full_name=f"{TEAM_ID} клиент №{i}",
            segment="employee",
            birth_year=1990,
            monthly_income=Decimal("100000"),
        )
        session.add(client)
        await session.flush()  # получить client.id
        session.add(Account(
            client_id=client.id,
            account_number=_account_number(digit, i),
            account_type="checking",
            balance=SEED_BALANCE,
            currency="RUB",
            status="active",
        ))

    await session.commit()
    return True

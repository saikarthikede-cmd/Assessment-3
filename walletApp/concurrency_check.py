import asyncio
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from walletApp import crud
from walletApp.database import SessionLocal, ensure_schema_compatibility


async def _debit_once(user_id):
    async with SessionLocal() as db:
        try:
            await crud.debit_wallet(db, user_id, Decimal("10.00"))
            return True, "ok"
        except HTTPException as exc:
            return False, str(exc.detail)


async def run_check(concurrency: int = 50) -> None:
    await ensure_schema_compatibility()

    async with SessionLocal() as setup_db:
        email = f"phase2_{uuid4()}@example.com"
        password_hash = "phase2-check-only"
        user = await crud.create_user(setup_db, email, password_hash)
        user_id = user.id
        await crud.create_wallet(setup_db, user_id)
        await crud.credit_wallet(setup_db, user_id, Decimal("100.00"))

    results = await asyncio.gather(*[_debit_once(user_id) for _ in range(concurrency)])

    successes = 0
    failures = 0
    failure_reasons = {}
    for ok, detail in results:
        if ok:
            successes += 1
        else:
            failures += 1
            failure_reasons[detail] = failure_reasons.get(detail, 0) + 1

    async with SessionLocal() as verify_db:
        wallet = await crud.get_balance(verify_db, user_id)
        ledger_entries = await crud.get_ledger(verify_db, user_id)

    debit_entries = [
        entry for entry in ledger_entries if entry.type == "debit" and entry.amount == Decimal("10.00")
    ]

    expected_successes = 10
    expected_failures = concurrency - expected_successes

    assert successes == expected_successes, f"expected {expected_successes} successes, got {successes}"
    assert failures == expected_failures, f"expected {expected_failures} failures, got {failures}"
    assert wallet.balance == Decimal("0.00"), f"expected final balance 0.00, got {wallet.balance}"
    assert len(debit_entries) == expected_successes, (
        f"expected {expected_successes} debit ledger entries, got {len(debit_entries)}"
    )

    print("PHASE2_CONCURRENCY_CHECK: PASS")
    print(
        f"successes={successes} failures={failures} final_balance={wallet.balance} "
        f"debit_ledger_entries={len(debit_entries)} failure_reasons={failure_reasons}"
    )


if __name__ == "__main__":
    asyncio.run(run_check(concurrency=50))

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from walletApp import crud
from walletApp.database import SessionLocal, ensure_schema_compatibility


def _debit_once(user_id):
    with SessionLocal() as db:
        try:
            crud.debit_wallet(db, user_id, Decimal("10.00"))
            return True, "ok"
        except HTTPException as exc:
            return False, str(exc.detail)


def run_check(concurrency: int = 50) -> None:
    ensure_schema_compatibility()

    with SessionLocal() as setup_db:
        email = f"phase2_{uuid4()}@example.com"
        password_hash = "phase2-check-only"
        user = crud.create_user(setup_db, email, password_hash)
        user_id = user.id
        crud.create_wallet(setup_db, user_id)
        crud.credit_wallet(setup_db, user_id, Decimal("100.00"))

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_debit_once, user_id) for _ in range(concurrency)]
        results = [future.result() for future in futures]

    successes = 0
    failures = 0
    failure_reasons = {}
    for ok, detail in results:
        if ok:
            successes += 1
        else:
            failures += 1
            failure_reasons[detail] = failure_reasons.get(detail, 0) + 1

    with SessionLocal() as verify_db:
        wallet = crud.get_balance(verify_db, user_id)
        ledger_entries = crud.get_ledger(verify_db, user_id)

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
    run_check(concurrency=50)

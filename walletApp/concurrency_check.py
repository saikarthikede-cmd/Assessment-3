from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from walletApp import crud
from walletApp.database import SessionLocal, ensure_schema_compatibility
from walletApp.models import Ledger, User, Wallet


def _debit_once(user_id):
    db = SessionLocal()
    try:
        try:
            crud.debit_wallet(db, user_id, Decimal("10.00"))
            return True, "ok"
        except HTTPException as exc:
            return False, str(exc.detail)
    finally:
        db.close()


def run_check(concurrency=50):
    ensure_schema_compatibility()

    setup_db = SessionLocal()
    try:
        email = f"phase2_{uuid4()}@example.com"
        user = crud.create_user(setup_db, email)
        crud.create_wallet(setup_db, user.id)
        crud.credit_wallet(setup_db, user.id, Decimal("100.00"))
        user_id = user.id
    finally:
        setup_db.close()

    successes = 0
    failures = 0
    failure_reasons = {}

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_debit_once, user_id) for _ in range(concurrency)]
        for future in as_completed(futures):
            ok, detail = future.result()
            if ok:
                successes += 1
            else:
                failures += 1
                failure_reasons[detail] = failure_reasons.get(detail, 0) + 1

    verify_db = SessionLocal()
    try:
        wallet = crud.get_balance(verify_db, user_id)
        ledger_entries = crud.get_ledger(verify_db, user_id)
        debit_entries = [entry for entry in ledger_entries if entry.type == "debit" and entry.amount == Decimal("10.00")]

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
    finally:
        verify_db.close()


if __name__ == "__main__":
    run_check(concurrency=50)

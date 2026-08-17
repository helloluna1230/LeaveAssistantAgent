"""SIMULATED HR data. Not real employee information.

Every record here is fake and exists only to demonstrate the Leave Assistant.
Includes deliberate edge cases: near-empty balance, expiring leave, and a
service-error trigger employee for exception testing.
"""

from __future__ import annotations

from datetime import date

# Employees keyed by employee_id. `manager_of` lists direct reports (limited view).
EMPLOYEES: dict[str, dict] = {
    "E1001": {"name": "Alice (simulated)", "role": "employee", "manager_of": []},
    "E1002": {"name": "Bob (simulated)", "role": "employee", "manager_of": []},
    "M1001": {"name": "Carol (simulated)", "role": "manager", "manager_of": ["E1001", "E1002"]},
    # Used only to exercise the SERVICE_UNAVAILABLE path in tests/demos.
    "E9999": {"name": "Faulty (simulated)", "role": "employee", "manager_of": []},
}

AS_OF = date(2026, 8, 13)

# Balances: employee_id -> leave_type -> figures.
BALANCES: dict[str, dict[str, dict]] = {
    "E1001": {
        "annual_leave": {
            "entitled_days": 15,
            "used_days": 6,
            "remaining_days": 9,
            "expiring_days": 3,
            "expiration_date": date(2026, 12, 31),
        },
        "sick_leave": {"entitled_days": 10, "used_days": 2, "remaining_days": 8},
        "compensatory_leave": {
            "entitled_days": 5,
            "used_days": 1,
            "remaining_days": 4,
            "expiring_days": 2,
            "expiration_date": date(2026, 9, 30),
        },
    },
    "E1002": {
        # Edge case: almost no annual leave left.
        "annual_leave": {
            "entitled_days": 12,
            "used_days": 11,
            "remaining_days": 1,
            "expiring_days": 0,
            "expiration_date": date(2026, 12, 31),
        },
        "sick_leave": {"entitled_days": 10, "used_days": 0, "remaining_days": 10},
        # Edge case: fully used comp leave (empty remaining).
        "compensatory_leave": {"entitled_days": 3, "used_days": 3, "remaining_days": 0},
    },
    "M1001": {
        "annual_leave": {
            "entitled_days": 20,
            "used_days": 5,
            "remaining_days": 15,
            "expiring_days": 0,
            "expiration_date": date(2026, 12, 31),
        },
        "sick_leave": {"entitled_days": 10, "used_days": 1, "remaining_days": 9},
        "compensatory_leave": {"entitled_days": 5, "used_days": 0, "remaining_days": 5},
    },
}

# Leave history: employee_id -> list of records.
HISTORY: dict[str, list[dict]] = {
    "E1001": [
        {"record_id": "H-E1001-01", "leave_type": "sick_leave", "start_date": date(2026, 2, 14),
         "end_date": date(2026, 2, 14), "days": 1, "status": "approved"},
        {"record_id": "H-E1001-02", "leave_type": "annual_leave", "start_date": date(2026, 3, 10),
         "end_date": date(2026, 3, 12), "days": 3, "status": "approved"},
        {"record_id": "H-E1001-03", "leave_type": "annual_leave", "start_date": date(2026, 5, 1),
         "end_date": date(2026, 5, 3), "days": 3, "status": "approved"},
    ],
    "E1002": [
        {"record_id": "H-E1002-01", "leave_type": "annual_leave", "start_date": date(2026, 1, 6),
         "end_date": date(2026, 1, 16), "days": 8, "status": "approved"},
        {"record_id": "H-E1002-02", "leave_type": "compensatory_leave", "start_date": date(2026, 6, 22),
         "end_date": date(2026, 6, 24), "days": 3, "status": "approved"},
    ],
    # Edge case: manager with no history in the queried window (empty result).
    "M1001": [
        {"record_id": "H-M1001-01", "leave_type": "annual_leave", "start_date": date(2026, 4, 20),
         "end_date": date(2026, 4, 22), "days": 3, "status": "approved"},
    ],
}

LEAVE_TYPES: list[dict] = [
    {"leave_type": "annual_leave", "display_name": "年假 / Annual Leave", "unit": "day",
     "accrual": "Accrued annually; unused days may expire per policy."},
    {"leave_type": "sick_leave", "display_name": "病假 / Sick Leave", "unit": "day",
     "accrual": "Granted per calendar year; medical proof may be required."},
    {"leave_type": "compensatory_leave", "display_name": "调休 / Compensatory Leave", "unit": "day",
     "accrual": "Earned from approved overtime; shorter validity window."},
]

# Simulated China public holidays for 2026.
PUBLIC_HOLIDAYS: dict[int, list[dict]] = {
    2026: [
        {"name": "元旦 New Year", "start_date": date(2026, 1, 1), "end_date": date(2026, 1, 1)},
        {"name": "春节 Spring Festival", "start_date": date(2026, 2, 16), "end_date": date(2026, 2, 22)},
        {"name": "清明 Qingming", "start_date": date(2026, 4, 4), "end_date": date(2026, 4, 6)},
        {"name": "劳动节 Labour Day", "start_date": date(2026, 5, 1), "end_date": date(2026, 5, 5)},
        {"name": "端午 Dragon Boat", "start_date": date(2026, 6, 19), "end_date": date(2026, 6, 21)},
        {"name": "中秋国庆 Mid-Autumn & National Day", "start_date": date(2026, 10, 1),
         "end_date": date(2026, 10, 8)},
    ]
}

# Employee that always returns a simulated backend outage.
FAULTY_EMPLOYEE_ID = "E9999"

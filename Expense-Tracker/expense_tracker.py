import argparse
import csv
import json
import os
import sys
from datetime import datetime

DATA_FILE   = os.path.join(os.path.dirname(__file__), "expenses.json")
BUDGET_FILE = os.path.join(os.path.dirname(__file__), "budgets.json")

# ----------------------------------------------------------------------
# Helper functions – loading / saving JSON
# ----------------------------------------------------------------------
def _load(path, default):
    """Read JSON from *path*; if missing return *default* (list or dict)."""
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_expenses():
    return _load(DATA_FILE, [])          # list of expense dicts

def save_expenses(expenses):
    _load(DATA_FILE, [])  # just to ensure dir exists; not strictly needed
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(expenses, f, indent=2)

def load_budgets():
    return _load(BUDGET_FILE, {})       # dict: month (str) → budget (float)

def save_budgets(budgets):
    with open(BUDGET_FILE, "w", encoding="utf-8") as f:
        json.dump(budgets, f, indent=2)

# ----------------------------------------------------------------------
# Core expense operations (unchanged – only tiny refactors for clarity)
# ----------------------------------------------------------------------
def _next_id(expenses):
    return max((e["id"] for e in expenses), default=0) + 1

def add_expense(args):
    if args.amount < 0:
        sys.exit("Error: amount cannot be negative")
    expenses = load_expenses()
    new_id = _next_id(expenses)
    today = datetime.now().strftime("%Y-%m-%d")
    expense = {
        "id": new_id,
        "date": today,
        "description": args.description,
        "amount": round(args.amount, 2),
        "category": args.category or "",
    }
    expenses.append(expense)
    save_expenses(expenses)
    print(f"Expense added successfully (ID: {new_id})")

def update_expense(args):
    expenses = load_expenses()
    for exp in expenses:
        if exp["id"] == args.id:
            if args.description is not None:
                exp["description"] = args.description
            if args.amount is not None:
                if args.amount < 0:
                    sys.exit("Error: amount cannot be negative")
                exp["amount"] = round(args.amount, 2)
            if args.category is not None:
                exp["category"] = args.category
            save_expenses(expenses)
            print("Expense updated successfully")
            return
    sys.exit(f"Error: no expense with ID {args.id}")

def delete_expense(args):
    expenses = load_expenses()
    filtered = [e for e in expenses if e["id"] != args.id]
    if len(filtered) == len(expenses):
        sys.exit(f"Error: no expense with ID {args.id}")
    save_expenses(filtered)
    print("Expense deleted successfully")

def list_expenses(_):
    expenses = load_expenses()
    if not expenses:
        print("No expenses recorded yet.")
        return
    header = f"{'ID':<4} {'Date':<12} {'Description':<20} {'Amount':<10} {'Category'}"
    print(header)
    print("-" * len(header))
    for e in expenses:
        print(
            f"{e['id']:<4} {e['date']:<12} {e['description'][:20]:<20} "
            f"${e['amount']:<9.2f} {e['category']}"
        )

def _filter_by_month(expenses, month):
    if month is None:
        return expenses
    cur_year = datetime.now().year
    return [
        e for e in expenses
        if datetime.strptime(e["date"], "%Y-%m-%d").year == cur_year
        and datetime.strptime(e["date"], "%Y-%m-%d").month == month
    ]

def summary(args):
    expenses = load_expenses()
    month = args.month
    filtered = _filter_by_month(expenses, month)
    total = sum(e["amount"] for e in filtered)

    if month:
        month_name = datetime(1900, month, 1).strftime("%B")
        print(f"Total expenses for {month_name}: ${total:.2f}")

        # ---- budget warning (optional) ----
        budgets = load_budgets()
        budget = budgets.get(str(month))
        if budget is not None and total > budget:
            print(f"⚠️  You exceeded the budget for this month (${budget:.2f})!")
    else:
        print(f"Total expenses: ${total:.2f}")

def set_budget(args):
    if args.budget < 0:
        sys.exit("Error: budget cannot be negative")
    budgets = load_budgets()
    budgets[str(args.month)] = round(args.budget, 2)
    save_budgets(budgets)
    print(f"Budget for month {args.month} set to ${args.budget:.2f}")

def export_csv(args):
    expenses = load_expenses()
    with open(args.file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Date", "Description", "Amount", "Category"])
        for e in expenses:
            writer.writerow([e["id"], e["date"], e["description"], f"{e['amount']:.2f}", e["category"]])
    print(f"Exported {len(expenses)} expenses to {args.file}")

# ----------------------------------------------------------------------
# Argument‑parser configuration (unchanged)
# ----------------------------------------------------------------------
def build_parser():
    parser = argparse.ArgumentParser(description="Simple expense‑tracker CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Add a new expense")
    p_add.add_argument("--description", required=True, help="Text description")
    p_add.add_argument("--amount", type=float, required=True, help="Amount (positive number)")
    p_add.add_argument("--category", help="Optional category")
    p_add.set_defaults(func=add_expense)

    # update
    p_up = sub.add_parser("update", help="Update an existing expense")
    p_up.add_argument("--id", type=int, required=True, help="Expense ID")
    p_up.add_argument("--description", help="New description")
    p_up.add_argument("--amount", type=float, help="New amount")
    p_up.add_argument("--category", help="New category")
    p_up.set_defaults(func=update_expense)

    # delete
    p_del = sub.add_parser("delete", help="Delete an expense")
    p_del.add_argument("--id", type=int, required=True, help="Expense ID")
    p_del.set_defaults(func=delete_expense)

    # list
    sub.add_parser("list", help="List all expenses").set_defaults(func=list_expenses)

    # summary
    p_sum = sub.add_parser("summary", help="Show total expenses")
    p_sum.add_argument("--month", type=int, choices=range(1, 13), help="Month number (1‑12) of current year")
    p_sum.set_defaults(func=summary)

    # set-budget
    p_budget = sub.add_parser("set-budget", help="Define a monthly budget")
    p_budget.add_argument("--month", type=int, required=True, choices=range(1, 13), help="Month number (1‑12)")
    p_budget.add_argument("--budget", type=float, required=True, help="Budget amount")
    p_budget.set_defaults(func=set_budget)

    # export
    p_exp = sub.add_parser("export", help="Export expenses to a CSV file")
    p_exp.add_argument("--file", required=True, help="Target CSV path")
    p_exp.set_defaults(func=export_csv)

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

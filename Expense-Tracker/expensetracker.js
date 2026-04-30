#!/usr/bin/env node
/**
 * expense-tracker.js – a tiny CLI expense manager (Node.js)
 *
 * Core commands:
 *   add          --description <text> --amount <num> [--category <text>]
 *   update       --id <num> [--description <text>] [--amount <num>] [--category <text>]
 *   delete       --id <num>
 *   list
 *   summary      [--month <1‑12>]
 *   set-budget   --month <1‑12> --budget <num>
 *   export       --file <path>
 *
 * Data files (same directory as this script):
 *   expenses.json – array of expense objects
 *   budgets.json  – object { "1": 200.0, "2": 150.0, … }
 *
 * Run `node expense-tracker.js --help` for usage.
 */

const { program } = require("commander");
const fs = require("fs");
const path = require("path");

// --------------------------
// Paths (same folder as script)
// --------------------------
const DATA_FILE   = path.join(__dirname, "expenses.json");
const BUDGET_FILE = path.join(__dirname, "budgets.json");

// --------------------------
// Helper: generic JSON loader that returns a *default* value if the file does not exist
// --------------------------
function loadJson(filePath, defaultValue) {
  if (!fs.existsSync(filePath)) {
    return defaultValue;
  }
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw);
  } catch (e) {
    console.error(`Failed to read ${path.basename(filePath)} – ${e.message}`);
    process.exit(1);
  }
}

// --------------------------
// Specific loaders – note the correct defaults!
// --------------------------
function loadExpenses() {
  return loadJson(DATA_FILE, []); // list of expense objects
}
function saveExpenses(expenses) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(expenses, null, 2), "utf-8");
}
function loadBudgets() {
  return loadJson(BUDGET_FILE, {}); // object: month (string) → budget (number)
}
function saveBudgets(budgets) {
  fs.writeFileSync(BUDGET_FILE, JSON.stringify(budgets, null, 2), "utf-8");
}

// --------------------------
// Core command implementations
// --------------------------
function nextId(expenses) {
  return expenses.reduce((max, e) => (e.id > max ? e.id : max), 0) + 1;
}

// ----- add -------------------------------------------------
function cmdAdd(opts) {
  const amount = Number(opts.amount);
  if (isNaN(amount) || amount < 0) {
    console.error("Error: amount must be a non‑negative number");
    process.exit(1);
  }

  const expenses = loadExpenses();
  const id = nextId(expenses);
  const today = new Date().toISOString().slice(0, 10); // YYYY‑MM‑DD

  expenses.push({
    id,
    date: today,
    description: opts.description,
    amount: Math.round(amount * 100) / 100,
    category: opts.category || "",
  });
  saveExpenses(expenses);
  console.log(`Expense added successfully (ID: ${id})`);
}

// ----- update ----------------------------------------------
function cmdUpdate(opts) {
  const expenses = loadExpenses();
  const target = expenses.find((e) => e.id === Number(opts.id));
  if (!target) {
    console.error(`Error: no expense with ID ${opts.id}`);
    process.exit(1);
  }

  if (opts.description !== undefined) target.description = opts.description;
  if (opts.amount !== undefined) {
    const amount = Number(opts.amount);
    if (isNaN(amount) || amount < 0) {
      console.error("Error: amount must be a non‑negative number");
      process.exit(1);
    }
    target.amount = Math.round(amount * 100) / 100;
  }
  if (opts.category !== undefined) target.category = opts.category;

  saveExpenses(expenses);
  console.log("Expense updated successfully");
}

// ----- delete ----------------------------------------------
function cmdDelete(opts) {
  const expenses = loadExpenses();
  const filtered = expenses.filter((e) => e.id !== Number(opts.id));
  if (filtered.length === expenses.length) {
    console.error(`Error: no expense with ID ${opts.id}`);
    process.exit(1);
  }
  saveExpenses(filtered);
  console.log("Expense deleted successfully");
}

// ----- list ------------------------------------------------
function cmdList() {
  const expenses = loadExpenses();
  if (expenses.length === 0) {
    console.log("No expenses recorded yet.");
    return;
  }

  const header = `${"ID".padEnd(4)} ${"Date".padEnd(12)} ${"Description".padEnd(
    20
  )} ${"Amount".padEnd(10)} Category`;
  console.log(header);
  console.log("-".repeat(header.length));

  for (const e of expenses) {
    console.log(
      `${String(e.id).padEnd(4)} ${e.date.padEnd(12)} ${e.description
        .slice(0, 20)
        .padEnd(20)} $${e.amount.toFixed(2).padEnd(8)} ${e.category}`
    );
  }
}

// ----- summary ---------------------------------------------
function filterByMonth(expenses, month) {
  if (!month) return expenses;
  const curYear = new Date().getFullYear();
  return expenses.filter((e) => {
    const [y, m] = e.date.split("-").map(Number);
    return y === curYear && m === month;
  });
}
function cmdSummary(opts) {
  const month = opts.month ? Number(opts.month) : null;
  const expenses = filterByMonth(loadExpenses(), month);
  const total = expenses.reduce((s, e) => s + e.amount, 0);

  if (month) {
    const monthName = new Date(1900, month - 1).toLocaleString("default", {
      month: "long",
    });
    console.log(`Total expenses for ${monthName}: $${total.toFixed(2)}`);

    // ----- optional budget warning -----
    const budgets = loadBudgets();
    const budget = budgets[month];
    if (budget !== undefined && total > budget) {
      console.warn(
        `⚠️  You exceeded the budget for this month ($${budget.toFixed(2)})!`
      );
    }
  } else {
    console.log(`Total expenses: $${total.toFixed(2)}`);
  }
}

// ----- set-budget ------------------------------------------
function cmdSetBudget(opts) {
  const month = Number(opts.month);
  const budget = Number(opts.budget);
  if (isNaN(budget) || budget < 0) {
    console.error("Error: budget must be a non‑negative number");
    process.exit(1);
  }

  const budgets = loadBudgets();          // ← now always an object
  budgets[month] = Math.round(budget * 100) / 100;
  saveBudgets(budgets);
  console.log(`Budget for month ${month} set to $${budget.toFixed(2)}`);
}

// ----- export ----------------------------------------------
function cmdExport(opts) {
  const expenses = loadExpenses();
  const lines = [
    ["ID", "Date", "Description", "Amount", "Category"].join(","),
    ...expenses.map(
      (e) =>
        `${e.id},${e.date},"${e.description.replace(/"/g, '""')}",${e.amount.toFixed(
          2
        )},${e.category}`
    ),
  ];
  fs.writeFileSync(opts.file, lines.join("\n"), "utf-8");
  console.log(`Exported ${expenses.length} expenses to ${opts.file}`);
}

// --------------------------
// Commander definitions
// --------------------------
program
  .name("expense-tracker")
  .description("Simple CLI expense manager")
  .version("1.0.0");

// add
program
  .command("add")
  .description("Add a new expense")
  .requiredOption("-d, --description <text>", "Description")
  .requiredOption("-a, --amount <num>", "Amount (positive number)")
  .option("-c, --category <text>", "Category")
  .action(cmdAdd);

// update
program
  .command("update")
  .description("Update an existing expense")
  .requiredOption("-i, --id <num>", "Expense ID")
  .option("-d, --description <text>", "New description")
  .option("-a, --amount <num>", "New amount")
  .option("-c, --category <text>", "New category")
  .action(cmdUpdate);

// delete
program
  .command("delete")
  .description("Delete an expense")
  .requiredOption("-i, --id <num>", "Expense ID")
  .action(cmdDelete);

// list
program.command("list").description("List all expenses").action(cmdList);

// summary
program
  .command("summary")
  .description("Show total expenses (all time or per month)")
  .option("-m, --month <num>", "Month number (1‑12)", (v) => parseInt(v, 10))
  .action(cmdSummary);

// set-budget (optional)
program
  .command("set-budget")
  .description("Define a budget for a month")
  .requiredOption("-m, --month <num>", "Month number (1‑12)", (v) => parseInt(v, 10))
  .requiredOption("-b, --budget <num>", "Budget amount")
  .action(cmdSetBudget);

// export
program
  .command("export")
  .description("Export all expenses to a CSV file")
  .requiredOption("-f, --file <path>", "Target CSV file")
  .action(cmdExport);

// ----------------------------------------------------------------------
program.parse(process.argv);

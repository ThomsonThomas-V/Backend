#!/usr/bin/env python3
"""
Number Guessing Game – CLI version

Features
--------
* Three difficulty levels (Easy / Medium / Hard)
* Limited number of guesses per level
* Hint system (parity + narrowed range) after a few wrong attempts
* Timer that shows how long the round lasted
* High‑score table (fewest attempts per difficulty) saved to disk
* Play multiple rounds until the user decides to quit

Run with:
    python game.py
"""

import json
import os
import random
import sys
import time
from typing import Optional  # <-- needed for the corrected type hints

# ----------------------------------------------------------------------
# Configuration constants (feel free to tweak)
# ----------------------------------------------------------------------
MIN_NUMBER = 1
MAX_NUMBER = 100

DIFFICULTIES = {
    "1": {"name": "Easy",   "chances": 10},
    "2": {"name": "Medium", "chances": 5},
    "3": {"name": "Hard",   "chances": 3},
}

HINT_AFTER_WRONG = 3               # after how many wrong guesses a hint is offered
HIGHSCORE_FILE = "highscores.json"  # persisted high‑score file (same folder)

# ----------------------------------------------------------------------
# Small I/O helpers
# ----------------------------------------------------------------------
def clear_line():
    """Print an empty line – helps readability."""
    print()


def prompt_int(
    prompt: str,
    low: Optional[int] = None,
    high: Optional[int] = None,
) -> int:
    """
    Read an integer from stdin, optionally enforce low/high bounds.

    Returns the integer the user entered.
    """
    while True:
        val = input(prompt).strip()
        if val.isdigit() or (val.startswith("-") and val[1:].isdigit()):
            num = int(val)
            if (low is not None and num < low) or (high is not None and num > high):
                print(f"Please enter a number between {low} and {high}.")
                continue
            return num
        else:
            print("That does not look like a number – try again.")


def prompt_choice(prompt: str, choices: list) -> str:
    """Read a choice from a list of allowed strings (case‑insensitive)."""
    choices_lower = [c.lower() for c in choices]
    while True:
        val = input(prompt).strip().lower()
        if val in choices_lower:
            return val
        else:
            print(f"Please type one of: {', '.join(choices)}")


# ----------------------------------------------------------------------
# High‑score handling
# ----------------------------------------------------------------------
def load_highscores() -> dict:
    """Return a dict like {'Easy': 7, 'Medium': 4, 'Hard': 3}."""
    if not os.path.exists(HIGHSCORE_FILE):
        return {}
    try:
        with open(HIGHSCORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Corrupted file – start fresh
        return {}


def save_highscores(highscores: dict):
    """Write the high‑score dict to disk (pretty‑printed)."""
    try:
        with open(HIGHSCORE_FILE, "w", encoding="utf-8") as f:
            json.dump(highscores, f, indent=2, sort_keys=True)
    except OSError as e:
        print(f"⚠️  Could not save high scores: {e}")


def maybe_update_highscore(highscores: dict, difficulty_name: str, attempts: int):
    """Update the dict if the new result beats the stored record."""
    record = highscores.get(difficulty_name)
    if record is None or attempts < record:
        highscores[difficulty_name] = attempts
        print(f"🎉  New high score for {difficulty_name} difficulty: {attempts} attempts!")
    else:
        print(f"Current high score for {difficulty_name}: {record} attempts.")
    return highscores


# ----------------------------------------------------------------------
# Hint system
# ----------------------------------------------------------------------
def give_hint(target: int, low_bound: int, high_bound: int):
    """
    Print a simple hint:
    * Whether the number is even or odd.
    * The current narrowed range (low_bound … high_bound).
    """
    parity = "even" if target % 2 == 0 else "odd"
    print(f"💡  Hint: The number is {parity} and lies between {low_bound} and {high_bound}.")


# ----------------------------------------------------------------------
# One round of the game
# ----------------------------------------------------------------------
def play_round(highscores: dict) -> dict:
    """Run a single guessing round and return the (potentially updated) high‑score dict."""
    print("\n=== Welcome to the Number Guessing Game! ===")
    print(f"I'm thinking of a number between {MIN_NUMBER} and {MAX_NUMBER}.\n")

    # ------------------------------------------------------------------
    # Choose difficulty
    # ------------------------------------------------------------------
    print("Please select the difficulty level:")
    for key, data in DIFFICULTIES.items():
        print(f"{key}. {data['name']} ({data['chances']} chances)")
    difficulty_key = prompt_choice("\nEnter your choice (1/2/3): ", list(DIFFICULTIES.keys()))
    difficulty = DIFFICULTIES[difficulty_key]
    chances = difficulty["chances"]
    diff_name = difficulty["name"]
    clear_line()
    print(f"Great! You have selected the {diff_name} difficulty level.")
    print("Let's start the game!\n")

    # ------------------------------------------------------------------
    # Initialise game state
    # ------------------------------------------------------------------
    target_number = random.randint(MIN_NUMBER, MAX_NUMBER)
    attempts = 0
    lower_possible = MIN_NUMBER
    upper_possible = MAX_NUMBER

    start_time = time.time()

    while attempts < chances:
        remaining = chances - attempts
        guess = prompt_int(
            f"Enter your guess (attempt {attempts + 1}/{chances}): ",
            low=MIN_NUMBER,
            high=MAX_NUMBER,
        )
        attempts += 1

        # --------------------------------------------------------------
        # Correct guess?
        # --------------------------------------------------------------
        if guess == target_number:
            elapsed = time.time() - start_time
            minutes = int(elapsed // 60)
            seconds = elapsed % 60
            print(f"\n✅  Congratulations! You guessed the number in {attempts} attempts.")
            print(f"⏱️  Time taken: {minutes}m {seconds:.1f}s")
            # Update high‑score table
            highscores = maybe_update_highscore(highscores, diff_name, attempts)
            break

        # --------------------------------------------------------------
        # Wrong guess – give feedback & tighten range
        # --------------------------------------------------------------
        if guess < target_number:
            print("Incorrect! The number is greater than your guess.")
            lower_possible = max(lower_possible, guess + 1)
        else:
            print("Incorrect! The number is less than your guess.")
            upper_possible = min(upper_possible, guess - 1)

        # Offer a hint after a few wrong attempts
        if attempts >= HINT_AFTER_WRONG:
            want_hint = prompt_choice("Would you like a hint? (y/n): ", ["y", "n"])
            if want_hint == "y":
                give_hint(target_number, lower_possible, upper_possible)

        if attempts < chances:
            print(f"You have {remaining - 1} chances left.\n")
        else:
            # Ran out of chances – reveal the answer
            print("\n❌  You've run out of chances!")
            print(f"The correct number was: {target_number}")
            print("Better luck next time.\n")

    # ------------------------------------------------------------------
    # End‑of‑round summary
    # ------------------------------------------------------------------
    print("\n=== High Scores ===")
    for level in ["Easy", "Medium", "Hard"]:
        score = highscores.get(level, "—")
        print(f"{level}: {score}")
    print("===================\n")

    return highscores


# ----------------------------------------------------------------------
# Main loop – keep playing until the user quits
# ----------------------------------------------------------------------
def main():
    # Load (or initialise) the persistent high‑score table
    highscores = load_highscores()

    while True:
        highscores = play_round(highscores)
        # Persist after each round
        save_highscores(highscores)

        again = prompt_choice("Do you want to play again? (y/n): ", ["y", "n"])
        if again != "y":
            print("\nThanks for playing! Goodbye 👋")
            break
        clear_line()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Graceful exit on Ctrl‑C
        print("\n\n👋  Game interrupted. Bye!")
        sys.exit(0)

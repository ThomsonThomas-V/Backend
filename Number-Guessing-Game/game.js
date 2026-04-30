#!/usr/bin/env node
/**
 * Number‑Guessing Game – pure Node.js, no external dependencies
 *
 * Features:
 *   • Three difficulty levels (Easy/Medium/Hard) → 10/5/3 guesses
 *   • Random number between 1 and 100
 *   • Hint system (parity + narrowed range) after a few wrong attempts
 *   • Timer (how long the round lasted)
 *   • Persistent high‑score table (fewest attempts per difficulty)
 *   • Play multiple rounds until the user quits
 *
 * Run with:   node game.js
 */

const fs   = require('fs');
const path = require('path');
const readline = require('readline');

// ----------------------------------------------------------------------
// Configuration constants (tweak if you like)
// ----------------------------------------------------------------------
const MIN_NUMBER   = 1;
const MAX_NUMBER   = 100;

const DIFFICULTIES = {
    1: { name: 'Easy',   chances: 10 },
    2: { name: 'Medium', chances: 5  },
    3: { name: 'Hard',   chances: 3  },
};

const HINT_AFTER_WRONG = 3;               // after how many wrong guesses a hint is offered
const HIGHSCORE_FILE   = path.join(__dirname, 'highscores.json');

// ----------------------------------------------------------------------
// Helper: async question prompt (wraps readline.question in a Promise)
// ----------------------------------------------------------------------
function ask(question) {
    const rl = readline.createInterface({
        input:  process.stdin,
        output: process.stdout,
    });
    return new Promise(resolve => rl.question(question, ans => {
        rl.close();
        resolve(ans.trim());
    }));
}

// ----------------------------------------------------------------------
// Persistent high‑score handling (read/write JSON)
// ----------------------------------------------------------------------
function loadHighScores() {
    if (!fs.existsSync(HIGHSCORE_FILE)) return {};
    try {
        const raw = fs.readFileSync(HIGHSCORE_FILE, 'utf8');
        return JSON.parse(raw);
    } catch (_) {
        // Corrupted file – start fresh
        return {};
    }
}

function saveHighScores(scores) {
    try {
        fs.writeFileSync(HIGHSCORE_FILE, JSON.stringify(scores, null, 2), 'utf8');
    } catch (e) {
        console.warn('⚠️  Could not write high‑score file:', e.message);
    }
}

// ----------------------------------------------------------------------
// Utility: read an integer with optional bounds, keep asking until valid
// ----------------------------------------------------------------------
async function readInt(prompt, low = null, high = null) {
    while (true) {
        const ans = await ask(prompt);
        const num = Number(ans);
        if (Number.isInteger(num) && (low === null || num >= low) && (high === null || num <= high)) {
            return num;
        }
        console.log(`Please enter an integer${low!==null?` ≥ ${low}`:''}${high!==null?` ≤ ${high}`:''}.`);
    }
}

// ----------------------------------------------------------------------
// Utility: read a yes/no answer (y/n)
// ----------------------------------------------------------------------
async function readYesNo(prompt) {
    while (true) {
        const ans = (await ask(prompt)).toLowerCase();
        if (ans === 'y' || ans === 'yes') return true;
        if (ans === 'n' || ans === 'no')  return false;
        console.log('Please answer with y (yes) or n (no).');
    }
}

// ----------------------------------------------------------------------
// Hint generator – parity + current narrowed range
// ----------------------------------------------------------------------
function giveHint(target, lowBound, highBound) {
    const parity = target % 2 === 0 ? 'even' : 'odd';
    console.log(`💡  Hint: The number is ${parity} and lies between ${lowBound} and ${highBound}.`);
}

// ----------------------------------------------------------------------
// One round of the game
// ----------------------------------------------------------------------
async function playRound(highScores) {
    console.log('\n=== Welcome to the Number Guessing Game! ===');
    console.log(`I'm thinking of a number between ${MIN_NUMBER} and ${MAX_NUMBER}.\n`);

    // ----------------  choose difficulty -----------------
    console.log('Please select the difficulty level:');
    for (const [key, cfg] of Object.entries(DIFFICULTIES)) {
        console.log(`${key}. ${cfg.name} (${cfg.chances} chances)`);
    }
    const diffChoice = await readInt('\nEnter your choice (1/2/3): ', 1, 3);
    const { name: diffName, chances } = DIFFICULTIES[diffChoice];
    console.log(`\nGreat! You have selected the ${diffName} difficulty level.`);
    console.log("Let's start the game!\n");

    // ----------------  initialise round -----------------
    const secretNumber = Math.floor(Math.random() * (MAX_NUMBER - MIN_NUMBER + 1)) + MIN_NUMBER;
    let attempts = 0;
    let lowerPossible = MIN_NUMBER;
    let upperPossible = MAX_NUMBER;
    const startTime = Date.now();

    // ----------------  main guessing loop ---------------
    while (attempts < chances) {
        const remaining = chances - attempts;
        const guess = await readInt(`Attempt ${attempts + 1}/${chances} – your guess: `, MIN_NUMBER, MAX_NUMBER);
        attempts++;

        if (guess === secretNumber) {
            const elapsedSec = ((Date.now() - startTime) / 1000).toFixed(1);
            console.log(`\n✅  Congratulations! You guessed it in ${attempts} attempt(s).`);
            console.log(`⏱️  Time taken: ${elapsedSec} seconds.`);

            // ---- update high‑score -------------------------------------------------
            const best = highScores[diffName];
            if (best == null || attempts < best) {
                highScores[diffName] = attempts;
                console.log(`🎉  New high score for ${diffName}! (${attempts} attempts)`);
            } else {
                console.log(`Current high score for ${diffName}: ${best} attempts`);
            }
            break;
        }

        // ---- wrong guess ---------------------------------------------------------
        if (guess < secretNumber) {
            console.log('Incorrect! The secret number is greater than your guess.');
            lowerPossible = Math.max(lowerPossible, guess + 1);
        } else {
            console.log('Incorrect! The secret number is less than your guess.');
            upperPossible = Math.min(upperPossible, guess - 1);
        }

        // ---- hint opportunity ----------------------------------------------------
        if (attempts >= HINT_AFTER_WRONG) {
            const wantHint = await readYesNo('Would you like a hint? (y/n): ');
            if (wantHint) giveHint(secretNumber, lowerPossible, upperPossible);
        }

        if (attempts < chances) {
            console.log(`You have ${remaining - 1} chance(s) left.\n`);
        } else {
            console.log('\n❌  You have used all your chances!');
            console.log(`The number was: ${secretNumber}`);
        }
    }

    // ---------- display high‑scores after the round ----------
    console.log('\n=== High Scores (fewest attempts) ===');
    for (const level of ['Easy', 'Medium', 'Hard']) {
        console.log(`${level}: ${highScores[level] ?? '—'}`);
    }
    console.log('=====================================\n');

    return highScores;
}

// ----------------------------------------------------------------------
// Main loop – keep playing until the player quits
// ----------------------------------------------------------------------
async function main() {
    let highScores = loadHighScores();

    while (true) {
        highScores = await playRound(highScores);
        saveHighScores(highScores);

        const again = await readYesNo('Do you want to play again? (y/n): ');
        if (!again) {
            console.log('\nThanks for playing! Goodbye 👋');
            break;
        }
    }
}

// ----------------------------------------------------------------------
// Run the game, handling Ctrl‑C gracefully
// ----------------------------------------------------------------------
main().catch(err => {
    console.error('Unexpected error:', err);
    process.exit(1);
});

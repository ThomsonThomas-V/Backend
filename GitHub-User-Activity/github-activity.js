#!/usr/bin/env node
/**
 * github‑activity – fetch recent GitHub events for a user.
 *
 * Features (standard‑library only):
 *   • Date & time shown in a human‑readable format (relative when possible)
 *   • Optional limit (`--limit N`) – defaults to 10
 *   • Optional filter by event type (`--type PushEvent` etc.)
 *   • ANSI colour output (green = pushes, cyan = issues, yellow = stars,
 *     magenta = create/delete, reset after each line)
 *   • Automatic use of a personal access token if GITHUB_TOKEN env‑var is set.
 *
 * Usage examples:
 *   node github-activity.js octocat
 *   node github-activity.js octocat --limit 5
 *   node github-activity.js octocat --type PushEvent
 *
 *   # With a token (elevates unauthenticated 60‑req/hr limit to 5 000/hr):
 *   $env:GITHUB_TOKEN = "ghp_XXXXXXXXXXXXXXXX"
 *   node github-activity.js octocat
 */

const https = require('https');
const { execSync } = require('child_process'); // only used for a tiny fallback if needed

// ------------------------------------------------------------
// Helpers – colour codes
// ------------------------------------------------------------
const COLORS = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  cyan: '\x1b[36m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  white: '\x1b[37m',
};

function colorize(text, colour) {
  return COLORS[colour] + text + COLORS.reset;
}

// ------------------------------------------------------------
// Helper – Relative time (e.g., "2 h ago")
// ------------------------------------------------------------
function relativeTime(dateStr) {
  const now = new Date();
  const then = new Date(dateStr);
  const diffMs = now - then; // positive number

  const seconds = Math.round(diffMs / 1000);
  const minutes = Math.round(seconds / 60);
  const hours = Math.round(minutes / 60);
  const days = Math.round(hours / 24);
  const weeks = Math.round(days / 7);
  const months = Math.round(days / 30);
  const years = Math.round(days / 365);

  if (years > 0) return `${years} year${years !== 1 ? 's' : ''} ago`;
  if (months > 0) return `${months} month${months !== 1 ? 's' : ''} ago`;
  if (weeks > 0) return `${weeks} week${weeks !== 1 ? 's' : ''} ago`;
  if (days > 0) return `${days} day${days !== 1 ? 's' : ''} ago`;
  if (hours > 0) return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
  if (minutes > 0) return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
  return `${seconds} second${seconds !== 1 ? 's' : ''} ago`;
}

// ------------------------------------------------------------
// Helper – fetch JSON from the GitHub API (Promise based)
// ------------------------------------------------------------
function fetchJson(url) {
  const headers = {
    'User-Agent': 'github-activity-cli',
    Accept: 'application/vnd.github+json',
  };
  // If a PAT is set, add Authorization header – this bumps the rate limit.
  if (process.env.GITHUB_TOKEN) {
    headers.Authorization = `token ${process.env.GITHUB_TOKEN}`;
  }

  const options = { headers };
  return new Promise((resolve, reject) => {
    https.get(url, options, (res) => {
      let raw = '';
      if (res.statusCode !== 200) {
        // Drain the response body so the socket can be reused.
        res.resume();
        reject(
          new Error(
            `GitHub API responded with ${res.statusCode} ${res.statusMessage}`
          )
        );
        return;
      }

      res.setEncoding('utf8');
      res.on('data', (chunk) => (raw += chunk));
      res.on('end', () => {
        try {
          const data = JSON.parse(raw);
          resolve(data);
        } catch (e) {
          reject(new Error('Failed to parse JSON from GitHub'));
        }
      });
    }).on('error', (err) => reject(err));
  });
}

// ------------------------------------------------------------
// Helper – format each event into a human‑readable line
// ------------------------------------------------------------
function formatEvent(ev) {
  const repo = ev.repo?.name ?? 'UNKNOWN';
  const when = relativeTime(ev.created_at);

  // Choose a colour based on the event type (for readability)
  let colour = 'white';
  let description;

  switch (ev.type) {
    case 'PushEvent': {
      colour = 'green';
      const count = ev.payload?.size ?? 0;
      // Show commit messages if they exist (max 3)
      const commitMsgs = (ev.payload?.commits ?? [])
        .slice(0, 3)
        .map((c) => c.message.split('\n')[0]) // first line of message only
        .join('; ');
      description = `Pushed ${count} commit${count !== 1 ? 's' : ''} to ${repo}`;
      if (commitMsgs) description += ` – ${commitMsgs}`;
      break;
    }
    case 'IssuesEvent': {
      colour = 'cyan';
      const action = ev.payload?.action ?? 'unknown';
      const issueNumber = ev.payload?.issue?.number ?? '?';
      description = `${action.charAt(0).toUpperCase() + action.slice(1)} issue #${issueNumber} in ${repo}`;
      break;
    }
    case 'WatchEvent': {
      colour = 'yellow';
      description = `Starred ${repo}`;
      break;
    }
    case 'CreateEvent': {
      colour = 'magenta';
      const refType = ev.payload?.ref_type ?? 'object';
      const ref = ev.payload?.ref ?? '';
      description = `Created ${refType}${ref ? ` "${ref}"` : ''} in ${repo}`;
      break;
    }
    case 'DeleteEvent': {
      colour = 'magenta';
      const refType = ev.payload?.ref_type ?? 'object';
      const ref = ev.payload?.ref ?? '';
      description = `Deleted ${refType}${ref ? ` "${ref}"` : ''} in ${repo}`;
      break;
    }
    case 'ForkEvent': {
      colour = 'magenta';
      const forkedRepo = ev.payload?.forkee?.full_name ?? '';
      description = `Forked ${repo} → ${forkedRepo}`;
      break;
    }
    default: {
      // For any other event we just dump the type.
      colour = 'white';
      description = `${ev.type} on ${repo}`;
    }
  }

  return `${colorize('•', colour)} ${description} ${colorize(`(${when})`, 'white')}`;
}

// ------------------------------------------------------------
// Argument parsing (manual – still pure std lib)
// ------------------------------------------------------------
function parseArgs(argv) {
  const args = {
    username: null,
    limit: 10,
    filter: null,
  };

  // Simple positional + named parsing
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (token === '--limit' && i + 1 < argv.length) {
      args.limit = Number(argv[++i]) || 10;
    } else if (token === '--type' && i + 1 < argv.length) {
      args.filter = argv[++i];
    } else if (!token.startsWith('-')) {
      positional.push(token);
    } else {
      console.error(`Unknown flag: ${token}`);
      process.exit(1);
    }
  }

  if (positional.length !== 1) {
    console.error('Usage: github-activity <username> [--limit N] [--type EventType]');
    process.exit(1);
  }

  args.username = positional[0];
  return args;
}

// ------------------------------------------------------------
// Main entry point
// ------------------------------------------------------------
async function main() {
  const { username, limit, filter } = parseArgs(process.argv.slice(2));

  const apiUrl = `https://api.github.com/users/${encodeURIComponent(
    username
  )}/events`;

  let events;
  try {
    events = await fetchJson(apiUrl);
  } catch (err) {
    // Map common errors to user‑friendly messages
    if (err.message.includes('404')) {
      console.error(`❌ User "${username}" not found on GitHub.`);
    } else if (err.message.includes('403')) {
      console.error(
        `❌ GitHub returned 403 – possibly rate‑limited. Set a personal access token in GITHUB_TOKEN to raise the limit.`
      );
    } else {
      console.error(`❌ Network or API error: ${err.message}`);
    }
    process.exit(1);
  }

  if (!Array.isArray(events) || events.length === 0) {
    console.log('No recent activity found for this user.');
    return;
  }

  // Apply optional filter before limiting
  const filtered = filter ? events.filter((e) => e.type === filter) : events;

  if (filtered.length === 0) {
    console.log(
      `No events of type "${filter}" found for user "${username}".`
    );
    return;
  }

  const toShow = filtered.slice(0, limit);
  for (const ev of toShow) {
    console.log(formatEvent(ev));
  }
}

// Run the async main function
main().catch((e) => {
  console.error('❌ Unexpected error:', e);
  process.exit(1);
});

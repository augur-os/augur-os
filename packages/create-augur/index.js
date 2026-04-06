#!/usr/bin/env node

'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const REPO_URL = 'https://github.com/augur-os/augur-os.git';
const MIN_PYTHON_MAJOR = 3;
const MIN_PYTHON_MINOR = 11;

// ── Helpers ──────────────────────────────────────────────────────────────────

function bold(text) {
  return `\x1b[1m${text}\x1b[0m`;
}

function green(text) {
  return `\x1b[32m${text}\x1b[0m`;
}

function yellow(text) {
  return `\x1b[33m${text}\x1b[0m`;
}

function red(text) {
  return `\x1b[31m${text}\x1b[0m`;
}

function dim(text) {
  return `\x1b[2m${text}\x1b[0m`;
}

function info(msg) {
  console.log(`  ${msg}`);
}

function success(msg) {
  console.log(`  ${green('+')} ${msg}`);
}

function warn(msg) {
  console.log(`  ${yellow('!')} ${msg}`);
}

function fail(msg) {
  console.error(`  ${red('x')} ${msg}`);
}

function commandExists(cmd) {
  const result = spawnSync('which', [cmd], { stdio: 'pipe' });
  return result.status === 0;
}

function run(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, {
    stdio: 'inherit',
    ...opts,
  });
  return result;
}

function ask(question) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  console.log();
  console.log(bold('  create-augur') + dim('  — your second brain, on your machine'));
  console.log();

  // 1. Get project name
  let name = process.argv[2];

  if (name === '--help' || name === '-h') {
    console.log('  Usage: npx create-augur [project-name]');
    console.log();
    console.log('  Creates a new Augur project in the specified directory.');
    console.log('  If no name is given, you will be prompted interactively.');
    console.log();
    process.exit(0);
  }

  if (!name) {
    name = await ask('  Project name: ');
    if (!name) {
      fail('Project name is required.');
      process.exit(1);
    }
  }

  // Validate name (basic: no slashes, no spaces, no leading dots)
  if (/[/\\]/.test(name) || name.startsWith('.')) {
    fail(`Invalid project name: ${name}`);
    process.exit(1);
  }

  const targetDir = path.resolve(process.cwd(), name);

  // 2. Check for existing directory
  if (fs.existsSync(targetDir)) {
    fail(`Directory already exists: ${targetDir}`);
    process.exit(1);
  }

  // 3. Check git
  if (!commandExists('git')) {
    fail('git is required but not found. Install it and try again.');
    process.exit(1);
  }

  // 4. Clone
  info(`Cloning Augur into ${bold(name)}...`);
  console.log();

  const cloneResult = run('git', [
    'clone',
    '--depth', '1',
    REPO_URL,
    targetDir,
  ]);

  if (cloneResult.status !== 0) {
    fail('Failed to clone repository.');
    process.exit(1);
  }

  // 5. Remove .git and re-init
  const dotGitPath = path.join(targetDir, '.git');
  fs.rmSync(dotGitPath, { recursive: true, force: true });

  const initResult = run('git', ['init'], { cwd: targetDir });
  if (initResult.status !== 0) {
    warn('Failed to initialize fresh git repo. You can do this manually.');
  }

  console.log();
  success('Project cloned and initialized.');
  console.log();

  // 6. Check Python
  info('Checking prerequisites...');
  console.log();

  let pythonOk = false;
  const pythonResult = spawnSync('python3', ['--version'], { stdio: 'pipe' });

  if (pythonResult.status === 0) {
    const versionStr = pythonResult.stdout.toString().trim();
    const match = versionStr.match(/Python (\d+)\.(\d+)/);
    if (match) {
      const major = parseInt(match[1], 10);
      const minor = parseInt(match[2], 10);
      if (major > MIN_PYTHON_MAJOR || (major === MIN_PYTHON_MAJOR && minor >= MIN_PYTHON_MINOR)) {
        success(`Python ${major}.${minor} found`);
        pythonOk = true;
      } else {
        warn(`Python ${major}.${minor} found, but ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ is required`);
      }
    }
  } else {
    warn('Python 3 not found. Install Python 3.11+ to use MCP server and skills.');
  }

  // 7. Check uv and install Python deps
  if (commandExists('uv') && pythonOk) {
    success('uv found — installing Python dependencies...');
    const uvResult = run('uv', ['sync'], { cwd: targetDir });
    if (uvResult.status === 0) {
      success('Python dependencies installed');
    } else {
      warn('uv sync failed. Run "uv sync" manually in the project directory.');
    }
  } else if (!commandExists('uv')) {
    warn('uv not found. Install it (https://docs.astral.sh/uv/) then run "uv sync"');
  }

  // 8. Check pnpm and install Node deps
  if (commandExists('pnpm')) {
    success('pnpm found — installing Node dependencies...');
    const pnpmResult = run('pnpm', ['install'], { cwd: targetDir });
    if (pnpmResult.status === 0) {
      success('Node dependencies installed');
    } else {
      warn('pnpm install failed. Run "pnpm install" manually in the project directory.');
    }
  } else if (commandExists('npm')) {
    warn('pnpm not found. Install it: npm install -g pnpm');
    warn('Then run "pnpm install" in the project directory.');
  } else {
    warn('pnpm not found. Install pnpm to set up the dashboard.');
  }

  // 9. Print next steps
  console.log();
  console.log(bold('  Next steps:'));
  console.log();
  console.log(`    cd ${name}`);

  if (!pythonOk) {
    console.log('    # Install Python 3.11+');
  }
  if (!commandExists('uv')) {
    console.log('    curl -LsSf https://astral.sh/uv/install.sh | sh');
    console.log('    uv sync');
  }
  if (!commandExists('pnpm')) {
    console.log('    npm install -g pnpm');
    console.log('    pnpm install');
  }

  console.log('    pnpm --filter dashboard dev');
  console.log();
  console.log(dim('  Docs:    https://augur.run/docs'));
  console.log(dim('  GitHub:  https://github.com/augur-os/augur-os'));
  console.log();
}

main().catch((err) => {
  fail(err.message);
  process.exit(1);
});

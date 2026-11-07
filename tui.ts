import { color, label, prompt } from '@astrojs/cli-kit';
import { execFile } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { mkdir, mkdtemp } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const python = process.env.PYTHON || 'python3';
const cli = fileURLToPath(new URL('./lab.py', import.meta.url));
const execute = promisify(execFile);
const badge = label(' bench ');
const safe = (value: string) => value.replace(/\p{Cc}/gu, ' ');

async function run(args: string[], showProgress = false) {
  try {
    const result = execute(python, [cli, ...args]);
    if (showProgress) result.child.stdout?.pipe(process.stdout, { end: false });
    return (await result).stdout;
  } catch (error) {
    const failure = error as { stderr?: string; code?: string };
    if (failure.code === 'ENOENT') throw new Error('Install Python 3 or set PYTHON to its executable.');
    throw new Error(safe(failure.stderr?.trim() || 'Python runner failed.'));
  }
}

async function field(message: string, initial: string, validate = (v: string) => Boolean(v.trim())) {
  const { value } = await prompt({ type: 'text', name: 'value', label: badge, message, initial,
    validate, error: 'Enter a valid value.' } as const);
  return value!.trim();
}

async function choose(message: string, values: string[]) {
  for (;;) {
    const choices = values.map(value => ({ label: safe(value), value, selected: true }));
    await prompt({ type: 'multiselect', name: 'items', label: badge, message, choices } as const);
    // cli-kit 0.4.1 updates the choices in place when the user toggles them.
    const selected = choices.filter(choice => choice.selected).map(choice => choice.value);
    if (selected.length) return selected;
    console.log('Select at least one item.');
  }
}

async function main() {
  if (!process.stdin.isTTY || !process.stdout.isTTY) throw new Error('Open an interactive terminal, or use python3 lab.py --help.');
  console.log(color.bold('\n  Local LLM Speed Bench'));
  const url = await field('OpenAI-compatible endpoint', 'http://127.0.0.1:8080/v1', value => {
    try {
      const u = new URL(value);
      return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password && !u.search && !u.hash;
    } catch { return false; }
  });
  let models: string[] = [];
  try {
    models = JSON.parse(await run(['models', '--url', url]));
  } catch (error) {
    console.log(color.yellow(String(error)));
  }
  if (!models.length) {
    const ids = await field('Enter chat model IDs, separated by commas', '', v => v.split(',').every(id => id.trim().length > 0));
    models = [...new Set(ids.split(',').map(id => id.trim()))];
  }
  const { mode } = await prompt({ type: 'select', name: 'mode', initial: 'full', label: badge, message: 'Benchmark plan', choices: [
    { value: 'full', label: 'Full recommended run', hint: 'All listed models · short, long and 8K' },
    { value: 'custom', label: 'Custom run', hint: 'Choose models, workloads and repetitions' },
  ] } as const);
  let cases = ['short', 'long', '8k'];
  let samples = '3', tokens = '256';
  if (mode === 'custom') {
    models = await choose('Chat models · Space to toggle', models);
    cases = await choose('Prompt lengths · Space to toggle', cases);
    const positive = (s: string) => /^\d+$/.test(s) && Number.isSafeInteger(Number(s)) && Number(s) > 0;
    samples = await field('Measured requests per workload', samples, positive);
    tokens = await field('Maximum output tokens per request', tokens, positive);
  }
  const runtime = await field('Runtime label for the report', 'Local server');
  const seed = randomUUID();
  console.log(`\n  ${models.map(safe).join(', ')}\n  ${cases.join(' / ')} · ${samples} samples · ${tokens} output tokens\n  ${models.length * (1 + cases.length * Number(samples))} sequential requests including warm-ups\n`);
  const { start } = await prompt({ type: 'confirm', name: 'start', label: badge, message: 'Start benchmark?', initial: true } as const);
  if (!start) return;
  const root = resolve('bench-runs');
  await mkdir(root, { recursive: true });
  const dir = await mkdtemp(join(root, 'run-'));
  console.log(`  Results: ${dir}`);
  const runs: string[] = [];
  for (const [i, model] of models.entries()) {
    console.log(color.cyan(`  [${i + 1}/${models.length}] ${safe(model)}`));
    const out = join(dir, `model-${i + 1}.json`);
    try {
      await run(['bench', '--progress', '--url', url, '--model', model, '--runtime', runtime, '--cases', ...cases,
        '--samples', samples, '--tokens', tokens, '--seed', seed, '--out', out], true);
      runs.push(out);
    } catch (error) {
      console.error(color.yellow(`  Failed: ${error}`));
      process.exitCode = 1;
    }
  }
  if (runs.length) {
    const out = join(dir, 'league.html');
    await run(['report', ...runs, '--out', out]);
    console.log(color.green(`  Report (${runs.length}/${models.length} models): ${out}`));
  } else throw new Error('No model completed the selected workloads.');
}

main().catch(error => { console.error(String(error)); process.exitCode = 1; });

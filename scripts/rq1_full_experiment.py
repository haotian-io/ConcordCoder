#!/usr/bin/env python3
"""
RQ1 Full Experiment Runner - 6 Model Comparison

Tests 6 models with both concordcoder and baseline conditions:
- qwen3.5-plus
- glm-5.1
- gemini-3.1-pro-preview
- MiniMax-M2.7
- kimi-k2.6
- deepseek-v4-pro

Usage:
  cd /home/liuhaotian/Jap/ConcordCoder/Code
  python3 scripts/rq1_full_experiment.py
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path

# Configuration
API_KEY = 'sk-EKztVaWERPFH6c8ftI2WDO6ajGYB1ekg6Tc42nExMC83vzs7'
BASE_URL = 'https://api.bltcy.ai/v1'
REPO_ROOT = '/home/liuhaotian/Jap/ConcordCoder/astropy'
INSTANCE_ID = 'astropy__astropy-12907'

MODELS = [
    'qwen3.5-plus',
    'glm-5.1',
    'gemini-3.1-pro-preview',
    'MiniMax-M2.7',
    'kimi-k2.6',
    'deepseek-v4-pro',
]

OUT_DIR = Path('results/rq1_full')
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    print('='*60)
    print('RQ1 Full Experiment - 6 Models')
    print('='*60)
    print(f'Instance: {INSTANCE_ID}')
    print(f'Repo: {REPO_ROOT}')
    print(f'Models: {MODELS}')
    print()

    os.environ['CONCORD_SWE_REPO_ROOT'] = REPO_ROOT
    os.environ['OPENAI_API_KEY'] = API_KEY
    os.environ['OPENAI_BASE_URL'] = BASE_URL

    all_results = []
    t0 = time.time()

    for model in MODELS:
        print(f'\n{"="*60}')
        print(f'[{model}] Starting tests...')
        print(f'{"="*60}')

        # Run concordcoder condition
        print(f'[{model}] Running concordcoder...', flush=True)
        try:
            cmd = [
                sys.executable, 'scripts/rq1_runner.py',
                '--instance-id', INSTANCE_ID,
                '--models', model,
                '--conditions', 'concordcoder',
                '--out-dir', str(OUT_DIR),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                # Parse output
                for line in result.stdout.split('\n'):
                    if 'elapsed=' in line:
                        print(f'  ✅ concordcoder: {line.strip()}')
                        break
                else:
                    print(f'  ✅ concordcoder completed')
                all_results.append({'model': model, 'condition': 'concordcoder', 'status': 'success'})
            else:
                print(f'  ❌ concordcoder failed: {result.stderr[:200]}')
                all_results.append({'model': model, 'condition': 'concordcoder', 'status': 'failed', 'error': result.stderr[:200]})
        except Exception as e:
            print(f'  ❌ concordcoder error: {e}')
            all_results.append({'model': model, 'condition': 'concordcoder', 'status': 'error', 'error': str(e)})

        # Run baseline condition
        print(f'[{model}] Running baseline...', flush=True)
        try:
            cmd = [
                sys.executable, 'scripts/rq1_runner.py',
                '--instance-id', INSTANCE_ID,
                '--models', model,
                '--conditions', 'baseline',
                '--out-dir', str(OUT_DIR),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'elapsed=' in line:
                        print(f'  ✅ baseline: {line.strip()}')
                        break
                else:
                    print(f'  ✅ baseline completed')
                all_results.append({'model': model, 'condition': 'baseline', 'status': 'success'})
            else:
                print(f'  ❌ baseline failed: {result.stderr[:200]}')
                all_results.append({'model': model, 'condition': 'baseline', 'status': 'failed', 'error': result.stderr[:200]})
        except Exception as e:
            print(f'  ❌ baseline error: {e}')
            all_results.append({'model': model, 'condition': 'baseline', 'status': 'error', 'error': str(e)})

    total = time.time() - t0

    print(f'\n{"="*60}')
    print(f'Results Summary (Total: {total:.1f}s)')
    print('='*60)
    for r in all_results:
        status = r.get('status', '?')
        error = r.get('error', '')
        print(f'  {r["model"]:25s} | {r["condition"]:15s} | {status} | {error}')

    # Save summary
    out_file = OUT_DIR / 'summary.json'
    out_file.write_text(json.dumps({
        'instance_id': INSTANCE_ID,
        'models': MODELS,
        'total_time_s': round(total, 2),
        'results': all_results,
    }, ensure_ascii=False, indent=2))
    print(f'\nSummary saved: {out_file}')


if __name__ == '__main__':
    main()

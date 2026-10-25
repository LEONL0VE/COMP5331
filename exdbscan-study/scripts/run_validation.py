"""Run DBSCAN, graph, unconstrained, constrained, dependency and data tests in order."""

import io
import sys
import unittest
import platform
import numpy as np
from _common import ROOT, save_json, source_fingerprint, timestamp


def main():
    phases = ['dbscan', 'graph', 'exdbscan', 'constraints', 'dependencies', 'datasets']
    reports = []
    transcript = io.StringIO()
    for phase in phases:
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=f'test_{phase}.py')
        result = unittest.TextTestRunner(stream=transcript, verbosity=2).run(suite)
        reports.append({'phase': phase, 'tests': result.testsRun,
                        'failures': len(result.failures), 'errors': len(result.errors),
                        'passed': result.wasSuccessful() and result.testsRun > 0})
        print(f'{phase}: {result.testsRun} tests, {"PASS" if result.wasSuccessful() else "FAIL"}')
    success = all(r['passed'] for r in reports)
    (ROOT / 'results').mkdir(exist_ok=True)
    (ROOT / 'results' / 'validation.log').write_text(transcript.getvalue())
    save_json(ROOT / 'results' / 'validation.json', {
        'status': 'passed' if success else 'failed', 'created_at': timestamp(),
        'source_fingerprint': source_fingerprint(), 'phases': reports,
        'tests_run': sum(r['tests'] for r in reports),
        'python': sys.version, 'numpy': np.__version__, 'platform': platform.platform(),
    })
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

import os
from pathlib import Path
import subprocess
import sys
import unittest


class DependencyTests(unittest.TestCase):
    def test_algorithms_run_when_external_algorithm_packages_are_blocked(self):
        code = '''
import sys
class BlockAlgorithms:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'sklearn', 'scipy', 'networkx'}:
            raise RuntimeError('Forbidden algorithm package: ' + fullname)
sys.meta_path.insert(0, BlockAlgorithms())
from density_explain import DBSCAN, ExDBSCAN
model = DBSCAN(1, 2).fit([[3, 0], [3.1, 0], [0, 0]])
result = ExDBSCAN(model).explain(2, target_cluster=0, k=2)
assert result.status == 'ok'
from density_explain.robust import robust_explain, parameter_stability
robust = robust_explain(model, [0, 0], 0, rho=0.2)
assert robust['status'] == 'ok'
assert parameter_stability(model, robust['counterfactual'], 0, [1], [2])['passed'] == 1
'''
        root = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, PYTHONPATH=str(root / 'src'))
        completed = subprocess.run([sys.executable, '-c', code], env=environment,
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == '__main__':
    unittest.main()

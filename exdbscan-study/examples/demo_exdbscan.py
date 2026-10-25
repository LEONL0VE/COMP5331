"""Print separately validated unconstrained and immutable-feature explanations."""

import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from density_explain import DBSCAN, ExDBSCAN
from density_explain.datasets import mock_constraint_case
from density_explain.metrics import evaluate_explanation

model = DBSCAN(eps=1, min_pts=3).fit(mock_constraint_case())
explainer = ExDBSCAN(model)
for immutable in [(), (1,), (0,)]:
    result = explainer.explain(5, target_cluster=0, k=3, immutable_features=immutable)
    print(json.dumps({'immutable_features': immutable,
                      'result': result.to_dict(),
                      'metrics': evaluate_explanation(model.result_, result)}, indent=2, allow_nan=False))

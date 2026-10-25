"""Small hand-checkable example, including noise later becoming a border."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from density_explain import DBSCAN

X = [[1], [0], [.1], [.2], [3]]
model = DBSCAN(eps=.81, min_pts=3).fit(X)
print('index  coordinates  neighbors  cluster  type')
for i, row in enumerate(X):
    print(i, row, model.neighbor_counts_[i], model.labels_[i], model.point_types_[i])

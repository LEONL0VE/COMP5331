# Algorithm Specification and Correspondence with the Papers

## DBSCAN

- Source: Ester et al., KDD 1996, Definitions 1-6 and ExpandCluster.
- Input is a finite real-valued matrix. Distance is Euclidean, epsilon > 0, and
  MinPts is a positive integer that includes the point itself.
- Neighborhoods are closed: `distance <= eps`. Fitting adds no extra tolerance
  and does not automatically standardize features.
- Neighborhood counts are computed for each point. Core points expand clusters
  through a queue; non-core points may join a cluster but cannot expand it.
- Input order determines cluster discovery order. A shared border point joins
  the first discovered cluster; this rule does not affect core connected components.
- `-2` denotes an unclassified point internally; final label `-1` denotes noise.
- Duplicate observations are retained and contribute to density counts.
- `memberships()` explicitly queries a fixed set of core points; it does not
  refit DBSCAN.

## ExDBSCAN

The implementation follows Matthews et al., KDD 2026, Equations 2-4, appendix
Algorithms 1 and 2, and the appendix on immutable features (A.5 in the published
version and A.8 in the extended arXiv version).

1. Keep the fitted clustering fixed. An explicit target must exist, must not be
   noise, and must differ from the original point's cluster.
2. Select target core points. If no target is specified, candidates come from
   other clusters that are not already reachable.
3. For immutable dimensions, retain core points satisfying
   `||p_I-q_I|| <= eps`, then construct the graph after filtering.
4. Nodes are candidate core points. Connect two nodes only if they belong to the
   same cluster and their distance is at most eps. Edge weights are Euclidean distances.
5. Compute graph distances `D_G` using Dijkstra's algorithm. Points in different
   connected components have distance +inf and reciprocal penalty 0.
6. Use the objective
   `E(S) = sum_q ||p-q||^2 + sum_{i<j} 1 / D_hat(q_i,q_j)`.
7. At each iteration, choose the point with the smallest incremental cost
   `||p-q||^2 + sum_{s in S} 1/D_hat(q,s)`.
8. For an unconstrained query outside the target ball, construct the
   counterfactual as `p' = q + eps * (p-q)/||p-q||`.
9. With immutable features, project onto the intersection of the ball and the
   affine subspace defined by the fixed coordinates.

The physical analogy motivates the objective only. The algorithm does not use
gradient descent, force-field simulation, or continuous motion integration.

## Geometry of Immutable Features

Let I be the immutable dimensions, A the mutable dimensions, and q the reference
core point:

```text
a = ||p_I - q_I||
If a > eps: this core point is unreachable
rho = sqrt((eps-a) * (eps+a))
b = ||p_A - q_A||
If b <= rho: p is already inside this ball cross-section
Otherwise:
    p'_I = p_I
    p'_A = q_A + rho/b * (p_A-q_A)
```

Immutable coordinates are copied from the original point to ensure exact
elementwise equality. The implementation does not project in the full space and
then restore immutable coordinates. This analytic construction develops the
geometry described in the paper.

## Interpretation Choices and Edge Cases

### Graph-Distance Scaling

The paper uses `D_hat = (d_c / mean_graph_weight) * D_G`, where d_c is the minimum
distance from p to a candidate core point. This implementation interprets
"average graph weight" as **the mean positive edge weight over distinct
undirected edges in the filtered graph**. The paper does not precisely specify
whether the average is over edge weights or all shortest-path distances. This
is therefore a documented reproduction choice, not a claim of bitwise agreement
with the authors' implementation.

When there are no positive edges, scale=1 because no finite positive path has a
repulsion term requiring scaling. Set `normalization='none'` to inspect the
paper's unscaled energy equation.

### Radius Boundary

The paper's neighborhood definition uses <=, while its graph construction prose
uses <. This project consistently uses <=, matching the original DBSCAN
definition. Counterfactual construction moves the cross-section radius inward
by one floating-point ULP. Validation allows a numerical residual of
`1e-10 * max(1, eps)`; this tolerance is not used when fitting DBSCAN.

### Coincident and Unreachable Points

For core points with identical coordinates in the same cluster, only the first
is retained as an explanation candidate, avoiding division by zero and duplicate
explanations. This does not alter training-data density. If different reference
core points yield exactly the same counterfactual for the same target under
immutable-feature constraints, one result is retained and the status is
`partial`. The selection trace still records all selected reference points.

Filtering may disconnect the graph. Disconnected pairs have zero repulsion
penalty; ineligible bridging core points are not restored automatically.

### Target Membership

The paper's existence criterion guarantees reachability of a target cluster.
Core balls from multiple clusters can overlap, so results retain all reachable
clusters instead of assigning an unsupported unique label. If the original point
already reaches an explicit target, the result is `already_reachable`. When no
target is specified, already reachable clusters are excluded as alternative
targets. The algorithm does not rerun DBSCAN or change the original data, core
status, or cluster identifiers.

### Greedy Selection and Optimality

Without constraints, when the original point lies outside the target coverage
region and k=1, selecting the nearest core point and projecting onto its ball
produces a nearest counterfactual. For k>1, discrete greedy selection does not
guarantee a global optimum.

With immutable features, selection still uses the paper's full-space core-point
cost. It therefore does not guarantee the smallest final change in mutable
coordinates across all candidate core points.

## Computational Cost

Let n be the number of training observations, d the number of dimensions, M the
number of candidate core points, and E the number of graph edges:

- Neighborhood queries take O(n^2 d). Neighborhood lists require O(n^2) space in
  the worst case; a full distance matrix is not constructed.
- Core-graph construction takes O(M^2 d), with O(M+E) adjacency-list storage.
- Each newly selected reference point requires one Dijkstra search, taking
  approximately O((M+E) log M).
- Incremental score updates take O(kM), and counterfactual construction takes O(kd).
- At most 16 shortest-path rows are cached per graph, and at most four candidate
  graphs are cached. A full all-pairs distance matrix is not stored by default.

These costs describe this implementation rather than repeating the paper's
simplified assumption that the graph necessarily grows linearly. This project
targets teaching and small-scale reproduction, without a claim of large-scale
production throughput.

## Evaluation Metrics

- `returned_validity`: independently validated points divided by returned
  points; defined as 0 for an empty result.
- `requested_validity`: valid points divided by the requested k; partial and
  infeasible results remain in the evaluation.
- `complete`: k points were returned and all are valid.
- `mean_proximity`: mean Euclidean distance from valid counterfactuals to the
  original point.
- `dpp_euclidean`: `det(K)` computed from actual endpoint distances, with
  K_ij=1/(1+d_ij).
- `dpp_reference_graph`: the same kernel applied to raw graph distances between
  reference core points. This is explicitly a graph-structure proxy, not a claim
  of equivalence to incompletely specified graph distances between newly
  generated counterfactual points.
- The graph-distance kernel is not necessarily positive semidefinite. Signed
  determinants are retained; negative values are not silently clipped.
- Metrics support comparisons within the current configurations. Changing
  spatial units affects both distance-based energy and diversity values.

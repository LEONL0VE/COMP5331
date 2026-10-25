# Sources and Implementation Provenance

## Mathematical Definitions

1. Ester, Kriegel, Sander, Xu. *A Density-Based Algorithm for Discovering Clusters
   in Large Spatial Databases with Noise*. KDD 1996.
   https://cdn.aaai.org/KDD/1996/KDD96-037.pdf
2. Matthews et al. *ExDBSCAN: Explaining DBSCAN with Counterfactual Reasoning*.
   KDD 2026. DOI: 10.1145/3770855.3817692.
   https://juser.fz-juelich.de/record/1063312/files/KDD2026___ExDBSCAN.pdf
3. Extended material: https://arxiv.org/html/2605.30225v1
4. Author repository: https://github.com/tommasoamico/ExDBSCAN
   Listed for traceability and potential future comparisons. This project did
   not copy, import, or execute the repository's algorithm code.

## Real Data

- USGS FDSN Earthquake Catalog: https://earthquake.usgs.gov/fdsnws/event/1/
- Selected earthquake locations in Southern California during 2024 with
  magnitude >= 2.
- Exact request URLs, retrieval timestamps, and raw CSV SHA-256 hashes are
  recorded in `data/raw/*.json`.
- Feature transformations, sampling rules, and processed-data hashes are
  recorded in `data/processed/*.json`.
- Events with identical coordinates but distinct event IDs are retained;
  duplicate observations are not automatically treated as invalid data.
- GeoLife was a candidate in the earlier plan, not a required dataset. A smaller
  historical USGS spatial snapshot was used to complete real-data validation.
  This project does not claim to have completed GeoLife or trajectory-level
  clustering experiments.

## Code Provenance and Collaboration

The code in this directory was independently developed from the mathematical
definitions above with Codex assistance during this collaboration. It does not
copy the authors' repository or wrap third-party clustering or counterfactual
packages as independently implemented algorithms. Validation uses manual cases,
an independent graph-connectivity oracle, Floyd-Warshall, combination enumeration,
and analytic geometry. Scikit-learn was not used for either implementation or
validation.

NumPy is used only for arrays, norms, random numbers, basic linear algebra, and
data files. The Python standard library provides queues, heaps, tests, CSV/JSON
handling, timing, and public-data downloads. Future group contributions and
modifications can be recorded here. This record is not a claim that the code
was written entirely by humans without assistance.

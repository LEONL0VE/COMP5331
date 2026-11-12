# DBSCAN & ExDBSCAN

An independent implementation and empirical validation of density-based clustering and counterfactual explanations for DBSCAN.

## Overview

This project explores density-based spatial clustering and counterfactual reasoning through two algorithms:

- **DBSCAN**: Identifies clusters based on density connectivity and detects noise points.
- **ExDBSCAN**: Extends DBSCAN with counterfactual reasoning to explain clustering outcomes and explore how changes in input conditions affect them.

The project focuses on algorithmic implementation, correctness validation, and evaluation using real-world spatial data.

## Dataset

We use the **USGS FDSN Earthquake Catalog** as a real-world validation dataset.

- **Region:** Southern California, USA
- **Period:** 2024
- **Magnitude threshold:** ≥ 2.0
- **Source:** [USGS Earthquake Catalog](https://earthquake.usgs.gov/fdsnws/event/1/)

Raw data, retrieval metadata, processing configurations, and data hashes are retained to support reproducibility.

## Implementation & Validation

The algorithms are implemented based on the mathematical definitions in the referenced publications.

Validation includes:
- Manually constructed test cases.
- Independent graph-connectivity verification.
- Floyd–Warshall-based validation.
- Exhaustive combination enumeration.
- Analytic geometry checks.

Scikit-learn is not used for implementation or validation.

## Project Scope

This project focuses on spatial clustering and counterfactual validation using earthquake location data. Trajectory-level clustering and GeoLife experiments are outside the current scope.

## References

1. Ester, M., Kriegel, H.-P., Sander, J., & Xu, X. (1996). *A Density-Based Algorithm for Discovering Clusters in Large Spatial Databases with Noise.* KDD 1996.
   - [Paper (PDF)](https://cdn.aaai.org/KDD/1996/KDD96-037.pdf)

2. Matthews et al. (2026). *ExDBSCAN: Explaining DBSCAN with Counterfactual Reasoning.* KDD 2026.
   - [Paper (PDF)](https://juser.fz-juelich.de/record/1063312/files/KDD2026___ExDBSCAN.pdf)
   - [Extended Version](https://arxiv.org/html/2605.30225v1)
   - [Author Repository](https://github.com/tommasoamico/ExDBSCAN)

## Technologies

- Python
- NumPy
- Python Standard Library

---

*This project is intended for research, algorithmic validation, and reproducible experimentation.*
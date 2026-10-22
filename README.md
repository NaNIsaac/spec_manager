# spec_manager

Parser for SPEC (Certified Scientific Software) scan files, including `#O/#P` motor positions, `#D` timestamps and `#UXML` metadata, plus plotting scripts for rocking curves and peak broadening (FWHM vs Q) of SrTiO₃ films.

SPEC 데이터 파일을 `Spec` / `SpecScan` 객체로 읽는 파서와, 이를 이용한 분석 스크립트. 개인 분석 코드.

## Requirements

Python 3.13+, pandas, scipy, matplotlib.

## Usage

```python
from spec import Spec

with Spec("data/250626") as spec:
    scan = spec.get_scan(1)
    scan.command, scan.time, scan.motors["Delta"]
    df = scan.to_dataframe()         # #L 열 이름 그대로
    scan.uxml                        # #UXML → dict
```

```powershell
uv sync
uv run rocking_curve.py   # data/250626 의 scan 1104, 879 rocking curve (imroi1, 정규화, log)
uv run main.py            # data/data*.csv 의 scan 별 Gaussian FWHM vs Q (γ, δ 오프셋 보정, 5550 eV)
```

두 스크립트는 저장소 루트에서 실행한다. 에너지 · 오프셋 · 시료 라벨은 `main.py` 에 하드코딩되어 있다. `data/data*.csv` 는 헤더 없는 `scan, gamma, delta, theta` 4열.

## Structure

```
spec.py            Spec, SpecScan 파서
rocking_curve.py   rocking curve 비교 그림
main.py            FWHM vs Q
data/              예제 SPEC 파일(250626, 3753 scans)과 scan 목록 CSV
```

## Where the same code lives now

Facts from the git history of the three repositories (checked 2026-10-23):

- The parser in `spec.py` was copied into [CXD](https://github.com/NaNIsaac/CXD) when CXD started (`src/cxd/core/spec.py`, CXD 3e5b632, 2026-04-14) and extended there (lazy reading, ROI and beam-centre helpers). On 2026-10-16 it moved to [QoraGeom](https://github.com/NaNIsaac/QoraGeom) as `qorageom.spec` (QoraGeom 76a67d1), and CXD now imports it from there (CXD 17ce71f). CXD keeps no SPEC parser of its own.
- `qorageom.spec` reads `data/250626` the same way as `spec.py`: all 3753 scans give the same command, `#D` time, motors, UXML, columns, data and detector distance. `scan.sdd_from_uxml` is `scan.sdd` there; it also adds the scan axis, energy, detector and ROI.
- `rocking_curve.py` and `main.py` are in CXD as `scripts/rocking_curve.py` and `scripts/fwhm_vs_q.py` (CXD 97bd33b, 722366b). There the paths and constants are command-line arguments whose defaults are the values used here (5.55 keV, gamma offset 1.4367 deg, delta offset 0.0112 deg).

This repository keeps the scripts as they were used on these data, and both run from here.

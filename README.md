# spec_manager

Parser for SPEC (Certified Scientific Software) scan files, including `#O/#P` motor positions, `#D` timestamps and `#UXML` metadata, plus plotting scripts for rocking curves and peak broadening (FWHM vs Q) of SrTiO₃ films.

SPEC 데이터 파일을 `Spec` / `SpecScan` 객체로 읽는 파서와, 이를 이용한 분석 스크립트. 개인 분석 코드.

## Requirements

Python 3.13+, pandas, scipy, matplotlib.

## Usage

```python
from spec import Spec

with Spec("path/to/file.spec") as spec:
    scan = spec.get_scan(1)
    scan.command, scan.time, scan.motors["Delta"]
    df = scan.to_dataframe()         # #L 열 이름 그대로
    scan.uxml                        # #UXML → dict
```

```powershell
uv sync
uv run rocking_curve.py PATH_TO_SPEC   # 그 파일의 scan 1104, 879 rocking curve (imroi1, 정규화, log)
uv run main.py PATH_TO_SPEC            # data/data*.csv 의 scan 별 Gaussian FWHM vs Q (γ, δ 오프셋 보정, 5550 eV)
```

두 스크립트는 저장소 루트에서 실행한다. 스크립트가 쓰던 실측 SPEC 파일(2025-06-26, 3753 scans)과 그 scan 목록 CSV 는 저장소에 없다. 파서와 스크립트를 시험해 보려면 생성된 데이터로 같은 형식의 파일을 만든다. `data/data*.csv` 는 git 이 무시하므로 자기 scan 목록을 둬도 커밋되지 않는다.

```powershell
uv run tests/synthetic_spec.py out.spec   # 측정값이 아닌 생성 데이터: data/data1-3.csv 와 그 scan 이 든 out.spec
uv run main.py out.spec
uv run rocking_curve.py out.spec
```

 에너지 · 오프셋 · 시료 라벨은 `main.py` 에 하드코딩되어 있다. `data/data*.csv` 는 헤더 없는 `scan, gamma, delta, theta` 4열.

## Test

```powershell
uv run --with pytest pytest
```

파서(필드, UXML 중첩·형 변환, 중복·잘못된 줄·없는 scan), Gaussian FWHM 적합, Q 계산(λ = 1 Å 에서 2θ = 60° 의 4π sin θ / λ), 두 스크립트의 실행을 생성 데이터로 확인한다. 실측 데이터로 얻은 결과를 확인하는 시험은 아니다.

## Structure

```
spec.py            Spec, SpecScan 파서
rocking_curve.py   rocking curve 비교 그림
main.py            FWHM vs Q
data/              (비어 있음) scan 목록 CSV 를 두는 곳, 생성기가 채운다
tests/             생성 데이터 기반 pytest 와 생성기(synthetic_spec.py)
```

## Where the same code lives now

Facts from the git history of the three repositories (checked 2026-10-23):

- The parser in `spec.py` was copied into [CXD](https://github.com/NaNIsaac/CXD) when CXD started (`src/cxd/core/spec.py`, CXD 3e5b632, 2026-04-14) and extended there (lazy reading, ROI and beam-centre helpers). On 2026-10-16 it moved to [QoraGeom](https://github.com/NaNIsaac/QoraGeom) as `qorageom.spec` (QoraGeom 76a67d1), and CXD now imports it from there (CXD 17ce71f). CXD keeps no SPEC parser of its own.
- `qorageom.spec` reads `data/250626` the same way as `spec.py`: all 3753 scans give the same command, `#D` time, motors, UXML, columns, data and detector distance. `scan.sdd_from_uxml` is `scan.sdd` there; it also adds the scan axis, energy, detector and ROI.
- `rocking_curve.py` and `main.py` are in CXD as `scripts/rocking_curve.py` and `scripts/fwhm_vs_q.py` (CXD 97bd33b, 722366b). There the paths and constants are command-line arguments whose defaults are the values used here (5.55 keV, gamma offset 1.4367 deg, delta offset 0.0112 deg).

This repository keeps the scripts as they were used on these data, and both run from here.

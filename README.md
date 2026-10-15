# spec_manager

Parser for SPEC (Certified Scientific Software) scan files, including `#O/#P` motor positions, `#D` timestamps and `#UXML` metadata, plus plotting scripts for rocking curves and peak broadening (FWHM vs Q) of SrTiO₃ films.

SPEC 데이터 파일을 `Spec` / `SpecScan` 객체로 읽는 파서와, 이를 이용한 분석 스크립트. 개인 분석 코드. 같은 파서가 [CXD](https://github.com/NaNIsaac/CXD) 의 `cxd.core.spec` 으로 이어졌다.

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

`main.py` 는 SPEC 파일을 `./250626` 에서 찾는다. 저장소의 예제 파일은 `data/250626` 이므로 `main.py` 의 `file` 을 고치거나 파일을 옮겨야 한다. 에너지 · 오프셋 · 시료 라벨도 `main.py` 에 하드코딩되어 있다. `data/data*.csv` 는 헤더 없는 `scan, gamma, delta, theta` 4열.

## Structure

```
spec.py            Spec, SpecScan 파서
rocking_curve.py   rocking curve 비교 그림
main.py            FWHM vs Q
data/              예제 SPEC 파일(250626, 3753 scans)과 scan 목록 CSV
```

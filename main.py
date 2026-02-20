import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from spec import Spec

def calculate_q_geometry(delta, gamma, energy=5550, g_off=1.4367, d_off=0.0112):
    """
    [Offset Applied Geometry Q Calculation]
    - g_off: Gamma offset (1.4367)
    - d_off: Delta offset (0.0112)
    """
    # 1. 파장 계산 (Angstrom)
    wavelength = 12398.41 / energy 
    
    # 2. Offset 보정 및 라디안 변환
    # 실제 물리적인 산란각은 세팅값에서 오프셋을 뺀 값입니다.
    gam_corr = np.radians(gamma - g_off)
    del_corr = np.radians(delta - d_off)
    
    # 3. 합성 2-Theta 계산 (Legacy Logic)
    # cos(2theta) = cos(gamma_corr) * cos(delta_corr)
    cos_2th = np.cos(gam_corr) * np.cos(del_corr)
    cos_2th = np.clip(cos_2th, -1.0, 1.0)
    two_theta_rad = np.arccos(cos_2th)
    
    # 4. Q_total 계산 (4 * pi / lambda) * sin(theta)
    q_total = (4.0 * np.pi / wavelength) * np.sin(two_theta_rad / 2.0)
    
    return q_total

def gaussian(x, a, xc, sigma, y0):
    """Gaussian function for FWHM fitting"""
    return y0 + a * np.exp(-(x - xc)**2 / (2 * sigma**2))

def fit_gaussian_fwhm(x, y):
    """Fits data to Gaussian and returns FWHM."""
    if len(y) < 4:
        return np.nan
    
    p0 = [np.max(y)-np.min(y), x[np.argmax(y)], (np.max(x)-np.min(x))/10.0, np.min(y)]
    
    popt, _ = curve_fit(gaussian, x, y, p0=p0, maxfev=2000)
    return 2.3548 * abs(popt[2])


def main():
    file = './250626'
    energy_val = 5550
    # 제공해주신 오프셋 값
    GAMMA_OFF = 1.4367
    DELTA_OFF = 0.0112
    
    data_files = ["data/data1.csv", "data/data2.csv", "data/data3.csv"]
    labels = ["STO on SiO2 25 / Ti 25 300", "STO on Ti 500 700", "STO on SiO2 500"]
    colors = ['black', 'red', 'blue']
    
    plt.figure(figsize=(10, 7))

    with Spec(file) as spec:
        for csv_path, label, color in zip(data_files, labels, colors):
            csv_df = pd.read_csv(csv_path, header=None, names=["scan", "gamma", "delta", "theta"])
            group_results = []
            
            for _, row in csv_df.iterrows():
                scan = spec.get_scan(row['scan'])
                if scan is None or not scan.data:
                    continue

                # 오프셋을 적용한 Q 계산
                q_val = calculate_q_geometry(row['delta'], row['gamma'], 
                                             energy=energy_val, 
                                             g_off=GAMMA_OFF, 
                                             d_off=DELTA_OFF)
                
                df_spec = scan.to_dataframe()
                x_data = df_spec.iloc[:, 0].values.astype(float)
                y_data = df_spec['imroi1'].values.astype(float)

                fwhm = fit_gaussian_fwhm(x_data, y_data)

                if not np.isnan(fwhm):
                    group_results.append({'q': q_val, 'fwhm': fwhm, "intensity": sum(y_data)})

            if group_results:
                res_df = pd.DataFrame(group_results).sort_values('q')
                plt.scatter(res_df['q'], res_df['fwhm'], color=color, label=label, s=50, edgecolors='k')

    plt.xlabel(r"$Q$ ($\AA^{-1}$)", fontsize=13)
    plt.ylabel(r"fwhm ($^\circ$)", fontsize=13)
    plt.title(fr"Broadening (Offsets: $\gamma={GAMMA_OFF}^\circ, \delta={DELTA_OFF}^\circ$)", fontsize=13)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    main()
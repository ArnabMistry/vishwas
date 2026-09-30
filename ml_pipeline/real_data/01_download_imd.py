"""VISHWAS Phase 2 Real-Data Validation: Download & Extract IMD Gridded Rainfall.

Step 1: Download IMD gridded daily rainfall data (using imdlib).
Crop to India bounding box (Lat 8.0-36.0, Lon 68.0-98.0).
Missing values (-999.0) converted to NaN.
Output: backend/data/real/raw/imd_test.nc or month-wise netCDF.
"""

import os
import sys

def main():
    print("IMD download pipeline module initialized.")

if __name__ == "__main__":
    main()

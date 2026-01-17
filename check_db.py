import pandas as pd
import os

path = "database.xlsx"
search_term = "U:\\Public"

if not os.path.exists(path):
    print("File not found")
else:
    xl = pd.ExcelFile(path)
    found = False
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        # Use regex=False to avoid escape issues
        mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, regex=False).any(), axis=1)
        if mask.any():
            print(f"Found in sheet: {sheet}")
            print(df[mask])
            found = True
    if not found:
        print("Search term not found in any sheet.")

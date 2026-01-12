import pandas as pd

def analyze_excel(file_path):
    try:
        xl = pd.ExcelFile(file_path)
        print(f"Sheets: {xl.sheet_names}")
        for sheet in xl.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet)
            print(f"\nSheet: {sheet}")
            print(f"Columns: {df.columns.tolist()}")
            print(f"Total rows: {len(df)}")
            print("Preview:")
            print(df.head(2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_excel("/Users/nale31/Desktop/ИИ/Антигравити/HR-бот/database.xlsx")

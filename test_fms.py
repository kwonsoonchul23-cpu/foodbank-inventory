import pandas as pd

file_path = 'g:/다른 컴퓨터/내 컴퓨터 (1)/anti/Inventory/basic/fms_260727.xlsx'
df = pd.read_excel(file_path)
storage_col = [c for c in df.columns if '보관' in str(c)]
if storage_col:
    print(df[storage_col[0]].unique())

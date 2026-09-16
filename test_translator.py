from openpyxl.formula.translate import Translator

f1 = '=IF(I17=0, K17+M17, "")'
try:
    print("f1:", Translator(f1, origin='G17').translate_formula('G18'))
except Exception as e:
    print("f1 error:", e)

f2 = '=IF(ISNA(MATCH(B17,Sheet2!A:A,0)),"X","O")'
try:
    print("f2:", Translator(f2, origin='O17').translate_formula('O18'))
except Exception as e:
    print("f2 error:", e)

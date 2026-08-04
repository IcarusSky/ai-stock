"""探针：确认新浪板块成分接口字段"""
import akshare as ak

print("=== stock_sector_spot(新浪行业) ===")
df = ak.stock_sector_spot(indicator="新浪行业")
print("shape:", df.shape)
print("columns:", list(df.columns))
print(df.head(3))
print()

# 拿第一个 label 探 detail
if not df.empty:
    label = str(df.iloc[0].get("label", "")).strip()
    name = str(df.iloc[0].get("板块", "")).strip()
    print(f"=== stock_sector_detail({label} = {name}) ===")
    try:
        d = ak.stock_sector_detail(sector=label)
        print("shape:", d.shape)
        print("columns:", list(d.columns))
        print(d.head(3))
    except Exception as e:
        print("ERROR:", e)

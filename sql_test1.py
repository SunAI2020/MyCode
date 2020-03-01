import pymysql
import records
db=records.Database("mysql+pymysql://sun:123456@localhost:3306/test_schema?charset=utf8mb4")
rows=db.query("SELECT * FROM test_table LIMIT 0,5")
print(rows.dataset)
print("*"*132)


for row in rows:
    print(row.serial_no,row.product_name,row.product_status,sep='\t')
print("*"*132)


#print(rows.all())
#print(rows.first())
emp={
    'product_status':'总代入库',
    'product_kind':'防火墙'
    }
rows=db.query("SELECT * FROM test_table WHERE PRODUCT_STATUS=:product_status AND PRODUCT_KIND=:product_kind",**emp)
print(rows.dataset)

print("*"*132)









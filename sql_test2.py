import pymysql

#连接到 SQL datebase
conn=pymysql.connect(host='127.0.0.1',port=3306,user='root',passwd='sx-secsun3721',db='test_schema',charset='utf8mb4')

#获取游标
cursor=conn.cursor()

#返回受影响的行数
effect_row1=cursor.execute("select * from test_table")
print(effect_row1)
print("*"*132)

#打开数据库
cursor.execute("select * from test_table")

#输入数据
serial_no=input("please input serial NO:")
product_kind=input("please input product_kind:")
product_type=input("please input product_type:")
product_name=input("please input product_name:")

#插入一条记录
try:
    # 执行SQL command
    cursor.execute("insert into test_table(serial_no,product_kind,product_type,product_name)values(%s,%s,%s,%s)",(serial_no,product_kind,product_type,product_name))
    # 提交到数据库
    conn.commit()
except:
    #如果出现错误则回滚
    conn.rollback()


#插入多条记录
#cursor.executemany("insert into test_table(serial_no,product_kind,product_type,product_name)values(%s,%s,%s,%s)",
#               [("2019-10-11-0005","Web防火墙","万兆Web防火墙","Web防火墙fw3511"),
#                ("2019-10-11-0006","Web防火墙","万兆Web防火墙","Web防火墙fw3511")])
#
print("*"*132)
#输出第一行的记录内容
cursor.execute("select * from test_table")
row1=cursor.fetchone()
print(row1,sep='\t')
print("*"*132)

#输出第2-6行共计5行的记录内容
row2=cursor.fetchmany(5)
print(row2,sep='\t')
print("*"*132)

#输出其余行的记录内容
row3=cursor.fetchall()
print(row3,sep='\t')
print("*"*132)
#

#获取最后一条插入的新数据ID
new_id=cursor.lastrowid
print(new_id)


row4=0
print("*"*132)
rows=cursor.execute("select * from test_table")
for row4 in range(rows):
    print(row4)
    row5=cursor.fetchone()
    print(row5,'\t')
    print("*"*132)

#打印数据库列表
try:
    cursor.execute("SELECT * FROM test_table")
    results = cursor.fetchall()
    print ("***serial_no***\t ***product_kind***\t ***product_type***\t ***product_name***\t ***product_license***\t")
    for row in results:
    #print (row)
        serial_no=row[0]
        product_kind=row[1]
        product_type=row[2]
        product_name=row[3]
        product_license=row[4]
    # Now print fetched result
#        print ("serial_no = %s,product_kind = %s,product_type = %s,product_name = %s,product_license = %s" % \
        print ( "%s,\t\t %s,\t\t %s,\t\t %s,\t\t %s" % \
             (serial_no, product_kind, product_type, product_name, product_license ))
except:
   import traceback
   traceback.print_exc()
   print ("Error: unable to fetch data")
#print(rows.all())
#print(rows.first())
#emp={
#    'product_status':'总代入库',
#    'product_kind':'防火墙'
#    }
#rows=db.query("SELECT * FROM test_table WHERE PRODUCT_STATUS=:product_status AND PRODUCT_KIND=:product_kind",**emp)
#print(rows.dataset)

#print("*"*132)


#关闭游标
cursor.close()

#关闭数据库连接
conn.close()






import pymysql
from datetime import datetime
#连接到 SQL datebase
conn=pymysql.connect(host='192.168.3.128',port=3306,user='sun',passwd='123456',db='test_schema',charset='utf8mb4')

#获取游标
cursor=conn.cursor()

#返回受影响的行数
effect_row1=cursor.execute("select * from test_table")
print(effect_row1)
print("*"*132)

#打开数据库
cursor.execute("select * from test_table")

#输入数据
time=datetime.now()
year1=time.year
month1=time.month
day1=time.day
hour1=time.hour
minute1=time.minute
second1=time.second
print(time,year1,month1,day1,hour1,minute1,second1)
serial_no=str(year1)+"-"+str(month1)+"-"+str(day1)+" "+str(hour1)+":"+str(minute1)+":"+str(second1)
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
print("这是第{lines}行记录:".format(lines=cursor.rownumber),row1,sep='\t')
#print(row1,sep='\t')
print("*"*132)

#输出第2-6行共计5行的记录内容
row2=cursor.fetchmany(5)
print("这是第{lines}行记录:".format(lines=cursor.rownumber),row2,sep='\t')
#print("这是第{lines}行记录:".format(lines=cursor.rownumber))
#print(row2,cursor.rownumber,sep='\t')
print("*"*132)

#输出其余行的记录内容
row3=cursor.fetchall()
print("这是第{lines}行记录:".format(lines=cursor.rownumber),row3,sep='\t')
#print(row3,cursor.rownumber,sep='\t')
print("*"*132)
#

#获取最后一条插入的新数据ID
new_id=cursor.lastrowid
print("最后一条记录的ID是：",new_id,"行号是",cursor.rownumber)


row4=0
print("*"*132)
rows=cursor.execute("select * from test_table")
for row4 in range(rows):
    print("记录的ID是：",row4,"行号cursor.rownumber=",cursor.rownumber)
    row5=cursor.fetchone()
    print(row5,'\t')
    print("*"*132)

#更新记录内容
conn = pymysql.connect("192.168.3.128","sun","123456","test_schema" )
# prepare a cursor object using cursor() method

#cursor = db.cursor()

cursor = conn.cursor(pymysql.cursors.DictCursor)

# prepare a cursor object using cursor() method
cursor = conn.cursor()
sql = "UPDATE TEST_TABLE SET PRODUCT_TYPE = 'Web防火墙' \
        WHERE LICENSE = 'hhhh'"

try:

   # Execute the SQL command
#   cursor.execute("UPDATE TEST_TABLE SET PRODUCT_LICENSE = 'ffff' WHERE PRODUCT_KIND = '防火墙'")
   cursor.execute(sql)

   # Commit your changes in the database
   conn.commit()

except:
   # Rollback in case there is any error
   conn.rollback()

#删除一条记录
conn=pymysql.connect(host='192.168.3.128',port=3306,user='sun',passwd='123456',db='test_schema',charset='utf8mb4')
cursor=conn.cursor()
cursor.execute("SELECT * FROM test_table")
results = cursor.fetchall()
# prepare a cursor object using cursor() method
#cursor = db.cursor(pymysql.cursors.DictCursor)
sql = "DELETE FROM TEST_TABLE WHERE PRODUCT_LICENSE>'hhhh'"
row=0
try:
    for row in results:
   # Execute the SQL comman
#    while product_license:
#    cursor.execute(sql)
        cursor.execute("DELETE FROM test_table WHERE serial_no IS NULL")
      # Commit your changes in the database
    conn.commit()

except:
   # Rollback in case there is any error
    conn.rollback()
#关闭游标
cursor.close()

#关闭数据库连接
conn.close()

#打印数据库列表
conn=pymysql.connect(host='192.168.3.128',port=3306,user='sun',passwd='123456',db='test_schema',charset='utf8mb4')
cursor=conn.cursor()
try:
    cursor.execute("SELECT * FROM test_table")
    results = cursor.fetchall()
    print ("_cursor.rownumber_\t _serial_no_\t _product_kind_\t _product_type_\t _product_name_\t _product_license_")
    for row in results:
    #print (row)
        serial_no=row[0]
        product_kind=row[1]
        product_type=row[2]
        product_name=row[3]
        product_license=row[4]
    # Now print fetched result
#        print ("serial_no = %s,product_kind = %s,product_type = %s,product_name = %s,product_license = %s" % \
        print ( "%s\t\t %s\t\t %s\t\t %s\t\t %s\t\t %s" % \
             (cursor.rownumber,serial_no, product_kind, product_type, product_name, product_license ))
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






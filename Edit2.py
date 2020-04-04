import sys
import pymysql
#from PyQt5.QtWidgets import QWidget,QMainWindow,QInputDialog,QTextEdit,QAction, QToolTip,QTableWidget,QMessageBox,QDesktopWidget,QPushButton,QApplication,QTableWidget
from PyQt5.QtGui import QIcon,QFont,QColor, QBrush
from PyQt5.QtCore import QCoreApplication,Qt
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
from edit_2 import Ui_mainWindow 
from datetime import datetime

###################################################################################
FL=open('db_p.txt','r')
P1=FL.readline().strip('\n')
P2=FL.readline().strip('\n')
P3=FL.readline().strip('\n')
P4=FL.readline().strip('\n')
P5=FL.readline().strip('\n')
P6=FL.readline().strip('\n')
 
Conn=pymysql.connect(host=P1,port=int(P2),user=P3,passwd=P4,db=P5,charset='utf8mb4')
Cursor=Conn.cursor()
Sql="SELECT * FROM {}".format(P6)
 
Sums=Cursor.execute(Sql)
Rows = Cursor.fetchone()

###################################################################################
class Edits(QMainWindow,Ui_mainWindow):

   
###################################################################################
    def __init__(self):
###################################################################################
        super(Edits,self).__init__()
        self.initUI()
        self.setupUi(self)
        self.tblshow(Rows)
        self.center()
       
###################################################################################
    def initUI(self):
###################################################################################
        #定义程序图标
        self.setWindowIcon(QIcon('chanpin12.jpg'))
        QApplication.setStyle(QStyleFactory.create('Windows'))
        #这种静态的方法设置一个用于显示工具提示的字体。使用16px滑体字体。
        QToolTip.setFont(QFont('SansSerif', 16))

        self.statusBar()

        #定义动作
        homeAction = QAction(QIcon('home.jpg'), '主页', self)
        homeAction.setShortcut('Ctrl+H')
        homeAction.setStatusTip('返回主页')
        homeAction.triggered.connect(self.close)

        contractAction = QAction(QIcon('hetong2.jpg'), '合同管理', self)
        contractAction.setShortcut('Ctrl+C')
        contractAction.setStatusTip('合同管理')
        contractAction.triggered.connect(self.close)

        paymentAction = QAction(QIcon('zijin2.jpg'), '资金管理', self)
        paymentAction.setShortcut('Ctrl+Z')
        paymentAction.setStatusTip('资金管理')
        paymentAction.triggered.connect(self.close)

        serviceAction = QAction(QIcon('fuwu5.jpg'), '服务管理', self)
        serviceAction.setShortcut('Ctrl+F')
        serviceAction.setStatusTip('服务管理')
        serviceAction.triggered.connect(self.close)

        personAction = QAction(QIcon('tuandui1.jpg'), '人员管理', self)
        personAction.setShortcut('Ctrl+R')
        personAction.setStatusTip('人员管理')
        personAction.triggered.connect(self.close)

        storeAction = QAction(QIcon('kufang2.jpg'), '仓储管理', self)
        storeAction.setShortcut('Ctrl+K')
        storeAction.setStatusTip('仓储管理')
        storeAction.triggered.connect(self.close)

        sellerAction = QAction(QIcon('hezuohuoban6.jpg'), '销售管理', self)
        sellerAction.setShortcut('Ctrl+X')
        sellerAction.setStatusTip('销售管理')
        sellerAction.triggered.connect(self.close)

        customerAction = QAction(QIcon('hezuohuoban5.jpg'), '客户管理', self)
        customerAction.setShortcut('Ctrl+Y')
        customerAction.setStatusTip('客户管理')
        customerAction.triggered.connect(self.close)

        tranceAction = QAction(QIcon('wuliu4.jpg'), '物流管理', self)
        tranceAction.setShortcut('Ctrl+W')
        tranceAction.setStatusTip('物流管理')
        tranceAction.triggered.connect(self.close)


        fileAction = QAction(QIcon('file.jpg'), '文件', self)
        fileAction.setShortcut('Ctrl+F')
        fileAction.setStatusTip('进入文件管理菜单')
        fileAction.triggered.connect(self.close)

        editAction = QAction(QIcon('edit.jpg'), '编辑', self)
        editAction.setShortcut('Ctrl+E')
        editAction.setStatusTip('进入文件编辑模式')
        editAction.triggered.connect(self.close)

        saveAction = QAction(QIcon('save.jpg'), '保存', self)
        saveAction.setShortcut('Ctrl+S')
        saveAction.setStatusTip('保存文件')
        saveAction.triggered.connect(self.close)

        printAction = QAction(QIcon('print.jpg'), '打印', self)
        printAction.setShortcut('Ctrl+P')
        printAction.setStatusTip('打印列表')
        printAction.triggered.connect(self.close)

        helpAction = QAction(QIcon('help.jpg'), '帮助', self)
        helpAction.setShortcut('Ctrl+H')
        helpAction.setStatusTip('帮助')
        helpAction.triggered.connect(self.close)

        exitAction = QAction(QIcon('exit4.jpg'), '退出系统', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('退出系统')
        exitAction.triggered.connect(self.close)

        openAction = QAction(QIcon('open.jpg'), '打开文件', self)
        openAction.setShortcut('Ctrl+O')
        openAction.setStatusTip('打开一个文件')
        openAction.triggered.connect(self.close)

        #定义状态条
        self.statusBar().showMessage('Ready')

        #定义工具条
        toolbar = self.addToolBar('主页')
        toolbar.addAction(homeAction)
        toolbar = self.addToolBar('合同管理')
        toolbar.addAction(contractAction)
        toolbar = self.addToolBar('资金管理')
        toolbar.addAction(paymentAction)
        toolbar = self.addToolBar('服务管理')
        toolbar.addAction(serviceAction)
        toolbar = self.addToolBar('人员管理')
        toolbar.addAction(personAction)
        toolbar = self.addToolBar('仓储管理')
        toolbar.addAction(storeAction)
        toolbar = self.addToolBar('销售管理')
        toolbar.addAction(sellerAction)
        toolbar = self.addToolBar('客户管理')
        toolbar.addAction(customerAction)
        toolbar = self.addToolBar('物流管理')
        toolbar.addAction(tranceAction)

        toolbar = self.addToolBar('编辑')
        toolbar.addAction(editAction)
        toolbar = self.addToolBar('保存')
        toolbar.addAction(saveAction)
        toolbar = self.addToolBar('打印')
        toolbar.addAction(printAction)
        toolbar = self.addToolBar('帮助')
        toolbar.addAction(helpAction)
        toolbar = self.addToolBar('退出')
        toolbar.addAction(exitAction)
        
        #定义主窗口位置和大小
        qr = self.frameGeometry()
        self.setGeometry(qr)
        self.setGeometry(100, 100, 300, 300)
        self.setWindowTitle('编辑数据')
        self.show()


###################################################################################
    def opensql(self):
###################################################################################
        Conn=pymysql.connect(host=P1,port=int(P2),user=P3,passwd=P4,db=P5,charset='utf8mb4')
        Cursor=Conn.cursor()
        Sql="SELECT * FROM {}".format(P6)
        Sums=Cursor.execute(Sql)

##        text=str('总共找到{}条记录').format(sums)
##        print(text)
        return Cursor

###################################################################################
    def closesql(self):
###################################################################################
        Cursor.close()
        #关闭数据库连接
        Conn.close()



###################################################################################
    def showDialog(self):
###################################################################################
        text, ok = QInputDialog.getText(self, 'Input Dialog', 
            '请输入授权码:')
        if ok:
            self.lineEdit_6.setText(str(text))

###################################################################################
    def exit_menu(self):
###################################################################################
        self.close()

###################################################################################
    def return_menu(self):
###################################################################################
        self.close()
        

###################################################################################
#    def buttonClicked(self):
###################################################################################
      
#        sender = self.sender()
#        self.statusBar().showMessage(sender.text() + ' was pressed')
        

###################################################################################
    def center(self):
###################################################################################
        #获得窗口
        qr = self.frameGeometry()
        #获得屏幕中心点
        cp = QDesktopWidget().availableGeometry().center()
        #显示到屏幕中心
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        
###################################################################################
#    def keyPressEvent(self, e):
###################################################################################
#        #按Esc键退出系统
#        if e.key() == Qt.Key_Escape:
#            self.close()

###################################################################################
    def closeEvent(self, event):
###################################################################################
         reply = QMessageBox.warning(self, '保存数据',"保存数据吗?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.Yes)
         if reply == QMessageBox.Yes:
             eds.ps_bt1()
         else:
             event.ignore()
         reply = QMessageBox.warning(self, '退出系统',"确定退出吗?", QMessageBox.No | 
            QMessageBox.Yes)
         if reply == QMessageBox.Yes:
             event.accept()
         else:
             event.ignore()

###################################################################################
    def tblshow(self,rows):
###################################################################################
        serial_no=rows[0]
        contract_date=rows[1]
        contract_no=rows[2]
        product_name=rows[3]
        product_type=rows[4]
        factory=rows[5]
        seller=rows[6]
        customer=rows[7]
        license_code=rows[8]
        license_date=rows[9]
        stores=rows[10]
        product_status=rows[11]
 
        #显示数据列表        
        self.lineEdit_1.setText(serial_no)
        self.lineEdit_2.setText(contract_no)
        self.lineEdit_3.setText(product_name)
        self.lineEdit_4.setText(product_type)
        self.lineEdit_5.setText(customer)
        self.lineEdit_6.setText(license_code)
        self.dateEdit_1.setDate(contract_date)
        self.dateEdit_2.setDate(license_date)

        self.comboBox_1.clear()
        self.comboBox_1.addItem(factory)
        fl1=open('factory.txt','r')
        list1=fl1.readlines()
        for it1 in list1:
            if it1.strip('\n') != factory:
                self.comboBox_1.addItem(it1.strip('\n'))
        fl1.close()

        self.comboBox_2.clear()
        self.comboBox_2.addItem(seller)
        fl2=open('seller.txt','r')
        list2=fl2.readlines()
        for it2 in list2:
            if it2.strip('\n') != seller:
                self.comboBox_2.addItem(it2.strip('\n'))
        fl2.close()

        self.comboBox_3.clear()
        self.comboBox_3.addItem(stores)
        fl3=open('stores.txt','r')
        list3=fl3.readlines()
        for it3 in list3:
            if it3.strip('\n') != stores:
                self.comboBox_3.addItem(it3.strip('\n'))
        fl3.close()

        self.comboBox_4.clear()
        self.comboBox_4.addItem(product_status)
        fl4=open('pstatus.txt','r')
        list4=fl4.readlines()
        for it4 in list4:
            if it4.strip('\n') != product_status:
                self.comboBox_4.addItem(it4.strip('\n'))
        fl4.close()

###################################################################################
    def date1_chg(self):
###################################################################################
        contract_date1=self.dateEdit_1.date().toString(Qt.ISODate)
##        print(str(contract_date1))
        return contract_date1
    
###################################################################################
    def date2_chg(self):
###################################################################################
        license_date1=self.dateEdit_2.date().toString(Qt.ISODate)
##        print(str(license_date1))
        return license_date1
    
###################################################################################
    def ln1_chg(self):
###################################################################################
        serial_no1=self.lineEdit_1.text()
##        print(str(serial_no1))
        return serial_no1

###################################################################################
    def ln2_chg(self):
###################################################################################
        contract_no1=self.lineEdit_2.text()
##        print(str(contract_no1))
        return contract_no1

###################################################################################
    def ln3_chg(self):
###################################################################################
        product_name1=self.lineEdit_3.text()
##        print(str(product_name1))
        return product_name1
    
###################################################################################
    def ln4_chg(self):
###################################################################################
        product_type1=self.lineEdit_4.text()
##        print(str(product_type1))
        return product_type1

###################################################################################
    def ln5_chg(self):
###################################################################################
        customer1=self.lineEdit_5.text()
##        print(str(customer1))
        return customer1

###################################################################################
    def ln6_chg(self):
###################################################################################
        license_code1=self.lineEdit_6.text()
        lic=str(license_code1)
##        print(lic)
        return lic
      
###################################################################################
    def cmb1_chg(self):
###################################################################################
        factory1=self.comboBox_1.currentText()
##        print(str(factory1))
        return factory1

###################################################################################
    def cmb2_chg(self):
###################################################################################
        seller1=self.comboBox_2.currentText()
##        print(str(seller1))
        return seller1

###################################################################################
    def cmb3_chg(self):
###################################################################################
        stores1=self.comboBox_3.currentText()
##        print(str(stores1))
        return stores1

###################################################################################
    def cmb4_chg(self):
###################################################################################
        product_status1=self.comboBox_4.currentText()
##        print(str(product_status1))
        return product_status1

        
###################################################################################
##################################################################################
    def ps_bt1(self):
###################################################################################
##        conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
##        cursor=conn.cursor()
##        sql="SELECT * FROM {}".format(self.p6)
##        sums=cursor.execute(sql)

        sql = "UPDATE {} SET CONTRACT_DATE = '{}', CONTRACT_NO = '{}',PRODUCT_NAME = '{}',\
               PRODUCT_TYPE = '{}',FACTORY = '{}',SELLER = '{}',CUSTOMER = '{}', LICENSE = '{}', \
               LICENSE_LIMITED = '{}', PRODUCT_LOCATION = '{}',PRODUCT_STATUS = '{}' WHERE SERIAL_NO = '{}'"\
               .format(P6,self.date1_chg(),self.ln2_chg(),\
              self.ln3_chg(),self.ln4_chg(),self.cmb1_chg(),self.cmb2_chg(),self.ln5_chg(),self.ln6_chg(),\
              self.date2_chg(),self.cmb3_chg(),self.cmb4_chg(),self.ln1_chg())

        try:
            Cursor.execute(sql)
            # Commit your changes in the database
            Conn.commit()

        except:
           # Rollback in case there is any error
            Conn.rollback()
###################################################################################
    def ps_bt2(self):
###################################################################################
        serial_no1=datetime.now().strftime('%Y%m%d%H%M%S')
        data1=datetime.now().strftime('%Y-%m-%d')

##        Conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
##        Cursor=Conn.cursor()
##        Sql="SELECT * FROM {}".format(self.p6)
##        sums=cursor.execute(sql)

        Rows = Cursor.fetchall()
##        new_id=Cursor.lastrowid

      
        try:
            sql = "insert into {}(serial_no,contract_date,contract_no,\
                           product_name,product_type,factory,seller,customer,license,\
                           license_limited,product_location,product_status)\
                           values(serial_no1,data1,"","","","","","","",data1,"","")".format(P6)
            print(sql)
##            Cursor.execute("insert into %s(serial_no,contract_date,contract_no,\
##                           product_name,product_type,factory,seller,customer,license,\
##                           license_limited,product_location,product_status)\
##                           values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(P6,serial_no1,data1,\
##                           "","","","","","","",data1,"",""))
            Cursor.execute(sql)

            Conn.commit()
            print(serial_no1)
        except:
           # Rollback in case there is any error
            Conn.rollback()

        sql = "select * from {} where serial_no = (%s)".format(P6),(serial_no1)
        print(sql)
        Cursor.execute(sql)
        Rows = Cursor.fetchone()
        eds.tblshow(Rows)
###################################################################################
    def ps_bt3(self):
###################################################################################
##        conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
##        cursor=conn.cursor()
##        sql="SELECT * FROM {}".format(self.p6)
##        sums=cursor.execute(sql)

        Sql = "DELETE FROM {} WHERE SERIAL_NO = '{}'".format(P6,self.ln1_chg())

        try:
            Cursor.execute(Sql)
                # Commit your changes in the database
            Conn.commit()
            eds.ps_bt4()

        except:
           # Rollback in case there is any error
            Conn.rollback()


###################################################################################
    def ps_bt4(self):
###################################################################################
        eds.ps_bt1()    
        try:
            Rows = Cursor.fetchone()
            eds.tblshow(Rows)

        except:
##            import traceback
##            traceback.print_exc()
##            print ("Error: unable to fetch data")
            self.statusBar().showMessage('已经是最后一条记录！！！')
            reply = QMessageBox.question(self,"请注意：","已到最后一条记录,\
             \n返回第一条记录吗？",QMessageBox.Yes|QMessageBox.No)
            if reply == QMessageBox.Yes:

                Cursor.close()
                Conn.close()

                Conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
                Cursor=conn.cursor()
                Sql="SELECT * FROM {}".format(self.p6)
                Sums=sCursor.execute(sql)
                
##                self.cursor.scroll(0,mode="absolute")
                Rows = Cursor.fetchone()
##                print(sql)
                eds.tblshow(Rows)

###################################################################################
    def ps_bt5(self):
###################################################################################
        self.close()

        

        
###################################################################################

###################################################################################

###################################################################################
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    eds = Edits()
    cur = eds.opensql()
    
###################################################################################
    #下拉菜单
    eds.action42.triggered.connect(eds.exit_menu)
    eds.action41.triggered.connect(eds.return_menu)
    

###################################################################################
    #按钮控件
    eds.pushButton_1.clicked.connect(eds.ps_bt1)
    eds.pushButton_2.clicked.connect(eds.ps_bt2)
    eds.pushButton_3.clicked.connect(eds.ps_bt3)
    eds.pushButton_4.clicked.connect(eds.ps_bt4)
    eds.pushButton_5.clicked.connect(eds.ps_bt5)



###################################################################################
    #文本行控件
    eds.lineEdit_1.textChanged.connect(eds.ln1_chg)
    eds.lineEdit_2.textChanged.connect(eds.ln2_chg)
    eds.lineEdit_3.textChanged.connect(eds.ln3_chg)
    eds.lineEdit_4.textChanged.connect(eds.ln4_chg)
    eds.lineEdit_5.textChanged.connect(eds.ln5_chg)
    eds.lineEdit_6.textChanged.connect(eds.ln6_chg)
    
###################################################################################
    #日期控件
    eds.dateEdit_1.dateChanged.connect(eds.date1_chg)
    eds.dateEdit_2.dateChanged.connect(eds.date2_chg)

###################################################################################
    #下拉框控件
    eds.comboBox_1.currentTextChanged.connect(eds.cmb1_chg)
    eds.comboBox_2.currentTextChanged.connect(eds.cmb2_chg)
    eds.comboBox_3.currentTextChanged.connect(eds.cmb3_chg)
    eds.comboBox_4.currentTextChanged.connect(eds.cmb4_chg)
    
###################################################################################
    sys.exit(app.exec_())
###################################################################################
        

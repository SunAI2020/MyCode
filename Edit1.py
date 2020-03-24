import sys
import pymysql
#from PyQt5.QtWidgets import QWidget,QMainWindow,QInputDialog,QTextEdit,QAction, QToolTip,QTableWidget,QMessageBox,QDesktopWidget,QPushButton,QApplication,QTableWidget
from PyQt5.QtGui import QIcon,QFont,QColor, QBrush
from PyQt5.QtCore import QCoreApplication,Qt
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
from edit_2 import Ui_MainWindow 

from datetime import datetime

class Edits(QMainWindow,Ui_MainWindow):

    conn=pymysql.connect(host='192.168.3.128',port=3306,user='sun',passwd='123456',db='test_schema',charset='utf8mb4')
        #获取游标
    cursor=conn.cursor()
        #返回受影响的行数
       
    sums=cursor.execute("SELECT * FROM test_table")
    rows = cursor.fetchone()
##    text=str('总共找到{}条记录').format(sums)
##    print(text)
    
    def __init__(self):
        super(Edits,self).__init__()
        self.initUI()
        self.setupUi(self)
#        cursor=self.opensql()
#        self.edit_list()
        self.tblshow(self.rows)
        self.center()
        
        
    def initUI(self):
        #定义程序图标
        self.setWindowIcon(QIcon('chanpin12.jpg'))
        QApplication.setStyle(QStyleFactory.create('Windows'))
        #这种静态的方法设置一个用于显示工具提示的字体。我们使用16px滑体字体。
        QToolTip.setFont(QFont('SansSerif', 10))

        #创建一个提示，我们称之为settooltip()方法。我们可以使用丰富的文本格式
        #self.setToolTip('这是产品列表 ')

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


    def opensql(self):
        conn=pymysql.connect(host='192.168.3.128',port=3306,user='sun',passwd='123456',db='test_schema',charset='utf8mb4')
        #获取游标
        cursor=conn.cursor()
        #返回受影响的行数
        
        sums=cursor.execute("SELECT * FROM test_table")
        text=str('总共找到{}条记录').format(sums)
        print(text)
        return cursor

    def closesql(self):
        cursor.close()
        #关闭数据库连接
        conn.close()



    def showDialog(self):
        text, ok = QInputDialog.getText(self, 'Input Dialog', 
            '请输入授权码:')
        if ok:
            self.lineEdit_6.setText(str(text))

    def exit_menu(self):
        self.close()

    def return_menu(self):
        self.close()
        

#    def buttonClicked(self):
      
#        sender = self.sender()
#        self.statusBar().showMessage(sender.text() + ' was pressed')
        

    def center(self):
        
        #获得窗口
        qr = self.frameGeometry()
        #获得屏幕中心点
        cp = QDesktopWidget().availableGeometry().center()
        #显示到屏幕中心
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        
#    def keyPressEvent(self, e):
#        #按Esc键退出系统
#        if e.key() == Qt.Key_Escape:
#            self.close()

    def closeEvent(self, event):
         reply = QMessageBox.question(self, '退出系统',"确定退出吗?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.No)
         if reply == QMessageBox.Yes:
             event.accept()
         else:
             event.ignore()

    def edit_list(self):

        conn=pymysql.connect(host='192.168.3.128',port=3306,user='sun',passwd='123456',db='test_schema',charset='utf8mb4')
        #获取游标
        cursor=conn.cursor()
        sums=cursor.execute("SELECT * FROM test_table")
        #返回记录数据


    def tblshow(self,rows):
##        rows = self.rows
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

        self.comboBox_1.addItem(factory)
        fl1=open('factory.txt','r')
        list1=fl1.readlines()
        for it1 in list1:
            self.comboBox_1.addItem(it1.strip('\n'))
        fl1.close()

        self.comboBox_2.addItem(seller)
        fl2=open('seller.txt','r')
        list2=fl2.readlines()
        for it2 in list2:
            self.comboBox_2.addItem(it2.strip('\n'))
        fl2.close()

        self.comboBox_3.addItem(stores)
        fl3=open('stores.txt','r')
        list3=fl3.readlines()
        for it3 in list3:
            self.comboBox_3.addItem(it3.strip('\n'))
        fl3.close()

        self.comboBox_4.addItem(product_status)
        fl4=open('pstatus.txt','r')
        list4=fl4.readlines()
        for it4 in list4:
            self.comboBox_4.addItem(it4.strip('\n'))
        fl4.close()
        
        return self.cursor

    def date1_chg(self):
        contract_date1=self.dateEdit_1.date().toString(Qt.ISODate)
        print(str(contract_date1))
        return contract_date1

    def date2_chg(self):
        license_date1=self.dateEdit_2.date().toString(Qt.ISODate)
        print(str(license_date1))
        return license_date1

    def ln1_chg(self):
        serial_no1=self.lineEdit_1.text()
        print(str(serial_no1))
        return serial_no1

    def ln2_chg(self):
        contract_no1=self.lineEdit_2.text()
        print(str(contract_no1))
        return contract_no1

    def ln3_chg(self):
        product_name1=self.lineEdit_3.text()
        print(str(product_name1))
        return product_name1

    def ln4_chg(self):
        product_type1=self.lineEdit_4.text()
        print(str(product_type1))
        return product_type1

    def ln5_chg(self):
        customer1=self.lineEdit_5.text()
        print(str(customer1))
        return customer1

    def ln6_chg(self):
        license_code1=self.lineEdit_6.text()
        lic=str(license_code1)
        print(lic)
        return lic
      
    def cmb1_chg(self):
        factory1=self.comboBox_1.currentText()
        print(str(factory1))
        return factory1

    def cmb2_chg(self):
        seller1=self.comboBox_2.currentText()
        print(str(seller1))
        return seller1

    def cmb3_chg(self):
        stores1=self.comboBox_3.currentText()
        print(str(stores1))
        return stores1

    def cmb4_chg(self):
        product_status1=self.comboBox_4.currentText()
        print(str(product_status1))
        return product_status1
        
    def ln1_prt(self):
        print(str(serial_no))

    def ps_bt1(self):

        conn = pymysql.connect("192.168.3.128","sun","123456","test_schema" )
##        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # prepare a cursor object using cursor() method
        cursor = conn.cursor()
##        sql = "UPDATE TEST_TABLE SET  CONTRACT_NO = '{}', \
##              PRODUCT_NAME = '{}',PRODUCT_TYPE = '{}' WHERE SERIAL_NO = '{}'".format(self.ln2_chg(),\
##              self.ln3_chg(),self.ln4_chg(),self.ln1_chg())




        sql = "UPDATE TEST_TABLE SET CONTRACT_DATE = '{}', CONTRACT_NO = '{}',PRODUCT_NAME = '{}',\
               PRODUCT_TYPE = '{}',FACTORY = '{}',SELLER = '{}',CUSTOMER = '{}', LICENSE = '{}', \
               LICENSE_LIMITED = '{}', PRODUCT_LOCATION = '{}',PRODUCT_STATUS = '{}' WHERE SERIAL_NO = '{}'"\
               .format(self.date1_chg(),self.ln2_chg(),\
              self.ln3_chg(),self.ln4_chg(),self.cmb1_chg(),self.cmb2_chg(),self.ln5_chg(),self.ln6_chg(),\
              self.date2_chg(),self.cmb3_chg(),self.cmb4_chg(),self.ln1_chg())



        try:
            cursor.execute(sql)
                # Commit your changes in the database
            conn.commit()

        except:
           # Rollback in case there is any error
            conn.rollback()
           
        cursor.close()
        #关闭数据库连接
        conn.close()



        
    def ps_bt2(self):
        self.close()

    def ps_bt3(self):
        self.close()

    def ps_bt4(self):
        self.close()

    def ps_bt5(self):
        self.close()

    def ps_bt6(self):
        self.close()

    def ps_bt7(self):
        try:

#            cursor=eds.opensql()
            rows = self.cursor.fetchone()
            print(str(rows))
#            cursor=cursor.scroll(1,mode='relative')
            eds.tblshow(rows)

        except:
            import traceback
##            traceback.print_exc()
##            print ("Error: unable to fetch data")
            self.statusBar().showMessage('已经是最后一条记录！！！')
            
            reply = QMessageBox.warning(self,"请注意：","已到最后一条记录!!!",QMessageBox.Ok)
##            if reply == QMessageBox.No:
##                event.ignore()
##            else:
##                eds.cursor.close()
##                 #关闭数据库连接
##                eds.conn.close()
##                cursor=eds.opensql()
##                rows = eds.cursor.fetchone()
##            print(str(rows))
##            cursor=cursor.scroll(1,mode='relative')
##                eds.tblshow(rows)


#        return cursor
##cursor.scroll(1,mode='relative') # 相对当前位置移动
##cursor.scroll(2,mode='absolute') # 相对绝对位置移动
##        
##
##
##
##


        
        

        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    eds = Edits()
    cur = eds.opensql()
    #下拉菜单
    eds.action42.triggered.connect(eds.exit_menu)
    eds.action41.triggered.connect(eds.return_menu)
    

    #按钮控件
    eds.pushButton_1.clicked.connect(eds.ps_bt1)
    eds.pushButton_2.clicked.connect(eds.showDialog)
    eds.pushButton_3.clicked.connect(eds.ps_bt3)
    eds.pushButton_4.clicked.connect(eds.ps_bt4)
    eds.pushButton_5.clicked.connect(eds.ps_bt5)
    eds.pushButton_6.clicked.connect(eds.ps_bt6)
    eds.pushButton_7.clicked.connect(eds.ps_bt7)


    eds.lineEdit_1.textChanged.connect(eds.ln1_chg)
    eds.lineEdit_2.textChanged.connect(eds.ln2_chg)
    eds.lineEdit_3.textChanged.connect(eds.ln3_chg)
    eds.lineEdit_4.textChanged.connect(eds.ln4_chg)
    eds.lineEdit_5.textChanged.connect(eds.ln5_chg)
    eds.lineEdit_6.textChanged.connect(eds.ln6_chg)
    
    eds.dateEdit_1.dateChanged.connect(eds.date1_chg)
    eds.dateEdit_2.dateChanged.connect(eds.date2_chg)

    eds.comboBox_1.currentTextChanged.connect(eds.cmb1_chg)
    eds.comboBox_2.currentTextChanged.connect(eds.cmb2_chg)
    eds.comboBox_3.currentTextChanged.connect(eds.cmb3_chg)
    eds.comboBox_4.currentTextChanged.connect(eds.cmb4_chg)
    
    sys.exit(app.exec_())
        

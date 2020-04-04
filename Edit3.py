import sys
import pymysql
##from PyQt5.QtWidgets import QWidget,QMainWindow,QInputDialog,QTextEdit,QAction, QToolTip,QTableWidget,QMessageBox,QDesktopWidget,QPushButton,QApplication,QTableWidget
from PyQt5.QtGui import QIcon,QFont,QColor, QBrush
from PyQt5.QtCore import QCoreApplication,Qt
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
from mwin2 import Ui_MainWindow 
from datetime import datetime

###################################################################################
###################################################################################
class Edits(QMainWindow,Ui_MainWindow):
    ff=open('db_p.txt','r')
    p1=ff.readline().strip('\n')
    p2=ff.readline().strip('\n')
    p3=ff.readline().strip('\n')
    p4=ff.readline().strip('\n')
    p5=ff.readline().strip('\n')
    p6=ff.readline().strip('\n')
 
    conn=pymysql.connect(host=p1,port=int(p2),user=p3,passwd=p4,db=p5,charset='utf8mb4')
    cursor=conn.cursor()
    sql="SELECT * FROM {}".format(p6)
 
    sums=cursor.execute(sql)
    rows = cursor.fetchone()

###################################################################################
    def __init__(self):
###################################################################################
        super(Edits,self).__init__()
        self.initUI()

        self.setupUi(self)
        self.tblshow(self.rows)

        self.showMaximized()       
###################################################################################
    def initUI(self):
###################################################################################
        #定义程序图标
        self.setWindowIcon(QIcon('chanpin12.jpg'))
        QApplication.setStyle(QStyleFactory.create('Windows'))
        #这种静态的方法设置一个用于显示工具提示的字体。使用16px滑体字体。
        QToolTip.setFont(QFont('SansSerif', 12))
        self.statusBar()

##        self.center()


        #定义动作
        homeAction = QAction(QIcon('home.jpg'), '主页', self)
        homeAction.setShortcut('Ctrl+H')
        homeAction.setStatusTip('返回主页')
        homeAction.triggered.connect(self.close)

        contractAction = QAction(QIcon('hetong2.jpg'), '合同管理', self)
        contractAction.setShortcut('Alt+H')
        contractAction.setStatusTip('合同管理')
        contractAction.triggered.connect(self.close)

        paymentAction = QAction(QIcon('zijin1.jpg'), '资金管理', self)
        paymentAction.setShortcut('Alt+Z')
        paymentAction.setStatusTip('资金管理')
        paymentAction.triggered.connect(self.close)

        productAction = QAction(QIcon('present.png'), '产品管理', self)
        productAction.setShortcut('Alt+C')
        productAction.setStatusTip('产品管理')
        productAction.triggered.connect(self.close)
        
        sellerAction = QAction(QIcon('wuliu2.jpg'), '进销管理', self)
        sellerAction.setShortcut('Alt+X')
        sellerAction.setStatusTip('进销管理')
        sellerAction.triggered.connect(self.close)

        channelAction = QAction(QIcon('ditu1.jpg'), '渠道管理', self)
        channelAction.setShortcut('Alt+Q')
        channelAction.setStatusTip('渠道管理')
        channelAction.triggered.connect(self.close)
        
        customerAction = QAction(QIcon('ouster.png'), '客户管理', self)
        customerAction.setShortcut('Alt+K')
        customerAction.setStatusTip('客户管理')
        customerAction.triggered.connect(self.close)

        serviceAction = QAction(QIcon('hezuohuoban2.jpg'), '服务管理', self)
        serviceAction.setShortcut('Alt+F')
        serviceAction.setStatusTip('服务管理')
        serviceAction.triggered.connect(self.close)

        personAction = QAction(QIcon('tuandui8.jpg'), '人员管理', self)
        personAction.setShortcut('Alt+R')
        personAction.setStatusTip('人员管理')
        personAction.triggered.connect(self.close)

        achievementAction = QAction(QIcon('yeji.jpg'), '业绩管理', self)
        achievementAction.setShortcut('Alt+Y')
        achievementAction.setStatusTip('业绩管理')
        achievementAction.triggered.connect(self.close)
        
        storeAction = QAction(QIcon('kufang6.jpg'), '仓储管理', self)
        storeAction.setShortcut('Alt+S')
        storeAction.setStatusTip('仓储管理')
        storeAction.triggered.connect(self.close)

        trafficAction = QAction(QIcon('wuliu3.jpg'), '物流管理', self)
        trafficAction.setShortcut('Alt+W')
        trafficAction.setStatusTip('物流管理')
        trafficAction.triggered.connect(self.close)

        fileAction = QAction(QIcon('file.jpg'), '文件', self)
        fileAction.setShortcut('Ctrl+B')
        fileAction.setStatusTip('文件管理...')
        fileAction.triggered.connect(self.close)

        editAction = QAction(QIcon('edit.jpg'), '编辑数据', self)
        editAction.setShortcut('Ctrl+E')
        editAction.setStatusTip('编辑数据...')
        editAction.triggered.connect(self.close)

        insertAction= QAction(QIcon('add1.jpg'), '新建记录', self)
        insertAction.setShortcut('Ctrl+N')
        insertAction.setStatusTip('新建记录...')
        insertAction.triggered.connect(self.close)
        
        deleteAction= QAction(QIcon('delete.jpg'), '删除数据', self)
        deleteAction.setShortcut('Ctrl+D')
        deleteAction.setStatusTip('删除数据！')
        deleteAction.triggered.connect(self.close)
        
        backupAction= QAction(QIcon('save.jpg'), '备份数据', self)
        backupAction.setShortcut('Ctrl+Alt+B')
        backupAction.setStatusTip('备份数据！')
        backupAction.triggered.connect(self.close)
        
        restoreAction= QAction(QIcon('AndroidSdkPackage.ico'), '恢复数据', self)
        restoreAction.setShortcut('Ctrl+Alt+R')
        restoreAction.setStatusTip('注意：恢复数据将覆盖现在的数据，请谨慎操作！')
        restoreAction.triggered.connect(self.close)

        xlsAction = QAction(QIcon('excel.jpg'), '保存为Excel', self)
        xlsAction.setShortcut('Ctrl+X')
        xlsAction.setStatusTip('保存为Excel文件')
        xlsAction.triggered.connect(self.close)

   
        docAction= QAction(QIcon('word2.png'), '保存为Word', self)
        docAction.setShortcut('Ctrl+W')
        docAction.setStatusTip('保存为Word文件')
        docAction.triggered.connect(self.close)
        
        txtAction= QAction(QIcon('note2.jpg'), '保存为txt', self)
        txtAction.setShortcut('Ctrl+T')
        txtAction.setStatusTip('保存为txt文件')
        txtAction.triggered.connect(self.close)
        
        jpgAction= QAction(QIcon('tuandui6.jpg'), '保存为图片', self)
        jpgAction.setShortcut('Ctrl+J')
        jpgAction.setStatusTip('保存为图片文件')
        jpgAction.triggered.connect(self.close)

        printAction = QAction(QIcon('print.jpg'), '打印', self)
        printAction.setShortcut('Ctrl+P')
        printAction.setStatusTip('打印列表')
        printAction.triggered.connect(self.close)

        helpAction = QAction(QIcon('help.jpg'), '帮助文档', self)
        helpAction.setShortcut('Ctrl+Alt+H')
        helpAction.setStatusTip('帮助帮助文档')
        helpAction.triggered.connect(self.close)

        licenseAction= QAction(QIcon('query.jpg'), '版权信息', self)
        licenseAction.setShortcut('Ctrl+L')
        licenseAction.setStatusTip('版权信息')
        licenseAction.triggered.connect(self.close)

        aboutAction= QAction(QIcon('info1.jpg'), '关于...', self)
        aboutAction.setShortcut('Ctrl+A')
        aboutAction.setStatusTip('关于...')
        aboutAction.triggered.connect(self.close)

        exitAction = QAction(QIcon('exit4.jpg'), '退出系统', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('退出系统')
        exitAction.triggered.connect(self.close)

        shutAction= QAction(QIcon('shut.jpg'), '关闭电脑', self)
        shutAction.setShortcut('Ctrl+Alt+S')
        shutAction.setStatusTip('关闭电脑')
        shutAction.triggered.connect(self.close)

        openAction = QAction(QIcon('open.jpg'), '打开文件', self)
        openAction.setShortcut('Ctrl+O')
        openAction.setStatusTip('打开一个文件')
        openAction.triggered.connect(self.close)

        #定义状态条
        self.statusBar().showMessage('Ready')

        #定义下拉菜单

        menubar = self.menuBar()
        menubar.setStyleSheet("color:rgb(10,10,10,255);font-size:25px;\
                               font-weight;font-family:Roman times;")

        funcMenu = menubar.addMenu('&功能模块(N)')
        funcMenu.addAction(contractAction)
        funcMenu.addSeparator()
        funcMenu.addAction(paymentAction)
        funcMenu.addSeparator()
        funcMenu.addAction(productAction)
        funcMenu.addSeparator()
        funcMenu.addAction(sellerAction)
        funcMenu.addSeparator()
        funcMenu.addAction(channelAction)
        funcMenu.addSeparator()
        funcMenu.addAction(customerAction)
        funcMenu.addSeparator()
        funcMenu.addAction(serviceAction)
        funcMenu.addSeparator()
        funcMenu.addAction(personAction)
        funcMenu.addSeparator()
        funcMenu.addAction(achievementAction)
        funcMenu.addSeparator()
        funcMenu.addAction(storeAction)
        funcMenu.addSeparator()
        funcMenu.addAction(trafficAction)
        
        dataMenu = menubar.addMenu('&数据编辑(E)')
        dataMenu.addAction(editAction)
        dataMenu.addSeparator()
        dataMenu.addAction(insertAction)
        dataMenu.addSeparator()
        dataMenu.addAction(deleteAction)
        dataMenu.addSeparator()
        dataMenu.addAction(backupAction)
        dataMenu.addSeparator()
        dataMenu.addAction(restoreAction)

        fileMenu = menubar.addMenu('&数据输出(P)')
        fileMenu.addAction(xlsAction)
        fileMenu.addSeparator()
        fileMenu.addAction(docAction)
        fileMenu.addSeparator()
        fileMenu.addAction(txtAction)
        fileMenu.addSeparator()
        fileMenu.addAction(jpgAction)
        fileMenu.addSeparator()
        fileMenu.addAction(printAction)

        sysMenu = menubar.addMenu('&系统(S)')
        sysMenu.addAction(homeAction)
        sysMenu.addSeparator()
        sysMenu.addAction(exitAction)
        sysMenu.addSeparator()
        sysMenu.addAction(shutAction)

        helpMenu = menubar.addMenu('&帮助(H)')
        helpMenu.addAction(helpAction)
        helpMenu.addSeparator()
        helpMenu.addAction(licenseAction)
        helpMenu.addSeparator()
        helpMenu.addAction(aboutAction)

        #定义工具条
        toolbar = self.addToolBar('主页')
        toolbar.addAction(homeAction)
        toolbar = self.addToolBar('合同管理')
        toolbar.addAction(contractAction)
        toolbar = self.addToolBar('资金管理')
        toolbar.addAction(paymentAction)
        toolbar = self.addToolBar('产品管理')
        toolbar.addAction(productAction)
        toolbar = self.addToolBar('进销管理')
        toolbar.addAction(sellerAction)
        toolbar = self.addToolBar('渠道管理')
        toolbar.addAction(channelAction)
        toolbar = self.addToolBar('客户管理')
        toolbar.addAction(customerAction)
        toolbar = self.addToolBar('服务管理')
        toolbar.addAction(serviceAction)
        toolbar = self.addToolBar('人员管理')
        toolbar.addAction(personAction)
        toolbar = self.addToolBar('业绩管理')
        toolbar.addAction(achievementAction)        
        toolbar = self.addToolBar('仓储管理')
        toolbar.addAction(storeAction)
        toolbar = self.addToolBar('物流管理')
        toolbar.addAction(trafficAction)
        toolbar = self.addToolBar('编辑')
        toolbar.addAction(editAction)
        toolbar = self.addToolBar('备份')
        toolbar.addAction(backupAction)
        toolbar = self.addToolBar('打印')
        toolbar.addAction(printAction)
        toolbar = self.addToolBar('帮助')
        toolbar.addAction(helpAction)
        toolbar = self.addToolBar('退出')
        toolbar.addAction(exitAction)

        
        #定义主窗口位置和大小
        image = QtGui.QPixmap()
        image.load(r"wangge5.jpg")
        palette1 = QtGui.QPalette()
        palette1.setBrush(self.backgroundRole(), QtGui.QBrush(image)) #背景图片
##        palette1.setColor(self.backgroundRole(), QColor(192,253,123)) #背景颜色
        self.setPalette(palette1)
        self.setAutoFillBackground(True)
        qr = self.frameGeometry()
        self.setGeometry(qr)
        self.setGeometry(100, 100, 300, 300)
        self.setWindowTitle('编辑数据')
        self.show()


###################################################################################
    def opensql(self):
###################################################################################
        conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
        cursor=conn.cursor()
        sql="SELECT * FROM {}".format(self.p6)
        sums=cursor.execute(sql)

##        text=str('总共找到{}条记录').format(sums)
##        print(text)
        return cursor

###################################################################################
    def closesql(self):
###################################################################################
        cursor.close()
        #关闭数据库连接
        conn.close()



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
##         reply = QMessageBox.warning(self, '保存数据',"保存数据吗?", QMessageBox.Yes | 
##            QMessageBox.No, QMessageBox.Yes)
##         if reply == QMessageBox.Yes:
##             eds.ps_bt1()
##         else:
##             event.ignore()
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
        #LCD显示记录数
        lcd1=str(self.cursor.rownumber)+' : '+str(self.sums)
        self.lcdNumber.display(lcd1)
        self.statusBar().showMessage('正在编辑第{}条记录'.format(self.cursor.rownumber))
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
        
        return self.cursor
    
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
        conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
        cursor=conn.cursor()
        sql="SELECT * FROM {}".format(self.p6)
        sums=cursor.execute(sql)

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
            self.statusBar().showMessage('已经保存编辑内容')

        except:
           # Rollback in case there is any error
            conn.rollback()
###################################################################################
    def ps_bt2(self):
###################################################################################
        serial_no1=datetime.now().strftime('%Y%m%d%H%M%S')
        data1=datetime.now().strftime('%Y-%m-%d')

        conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
        cursor=conn.cursor()
        sql="SELECT * FROM {}".format(self.p6)
        sums=cursor.execute(sql)

##        rows = self.cursor.fetchall()
##        new_id=self.cursor.lastrowid

        try:
            cursor.execute("insert into test_table(serial_no,contract_date,contract_no,\
                           product_name,product_type,factory,seller,customer,license,\
                           license_limited,product_location,product_status)\
                           values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(serial_no1,data1,\
                           " "," "," "," "," "," "," ",data1," "," "))

            conn.commit()
            self.sums+=1
            self.statusBar().showMessage('插入一条新的记录')
##            print(serial_no1)
        except:
           # Rollback in case there is any error
            conn.rollback()

        cursor.execute("select * from test_table where serial_no = (%s)",(serial_no1))
        rows = cursor.fetchone()
        eds.tblshow(rows)
###################################################################################
    def ps_bt3(self):
###################################################################################
        conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
        cursor=conn.cursor()
        sql="SELECT * FROM {}".format(self.p6)
        sums=cursor.execute(sql)

        sql = "DELETE FROM {} WHERE SERIAL_NO = '{}'".format(self.p6,self.ln1_chg())

        try:
            cursor.execute(sql)
                # Commit your changes in the database
            conn.commit()
            self.statusBar().showMessage('删除了一条记录！！！')
            self.sums-=1
            eds.ps_bt4()

        except:
           # Rollback in case there is any error
            conn.rollback()


###################################################################################
    def ps_bt4(self):
###################################################################################
        eds.ps_bt1()    
        try:
            rows = self.cursor.fetchone()
            eds.tblshow(rows)

        except:
##            import traceback
##            traceback.print_exc()
##            print ("Error: unable to fetch data")
            self.statusBar().showMessage('已经是最后一条记录！！！')
            reply = QMessageBox.question(self,"请注意：","已到最后一条记录,\
             \n返回第一条记录吗？",QMessageBox.Yes|QMessageBox.No)
            if reply == QMessageBox.Yes:

                self.cursor.close()
                self.conn.close()

                conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
                self.cursor=conn.cursor()
                sql="SELECT * FROM {}".format(self.p6)
                sums=self.cursor.execute(sql)
                
##                self.cursor.scroll(0,mode="absolute")
                rows = self.cursor.fetchone()
##                print(sql)
                eds.tblshow(rows)

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
    #按钮控件
    eds.pushButton_1.setStatusTip('保存当前编辑的内容')
    eds.pushButton_1.setToolTip('保存编辑')
    eds.pushButton_1.clicked.connect(eds.ps_bt1)
    eds.pushButton_2.setStatusTip('新建一条记录')
    eds.pushButton_2.setToolTip('新建记录')
    eds.pushButton_2.clicked.connect(eds.ps_bt2)
    eds.pushButton_3.setStatusTip('删除当前记录，请谨慎操作！')
    eds.pushButton_3.setToolTip('删除记录')
    eds.pushButton_3.clicked.connect(eds.ps_bt3)
    eds.pushButton_4.setStatusTip('保存当前记录内容，并跳转到下一条记录')
    eds.pushButton_4.setToolTip('转到下一条记录')
    eds.pushButton_4.clicked.connect(eds.ps_bt4)
    eds.pushButton_5.setStatusTip('退出当前窗口，请先保存，以免数据丢失！')
    eds.pushButton_5.setToolTip('退出当前窗口！')
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
        

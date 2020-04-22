import sys
##import pymysql
##from PyQt5.QtWidgets import QWidget,QMainWindow,QInputDialog,QTextEdit,QAction, QToolTip,QTableWidget,QMessageBox,QDesktopWidget,QPushButton,QApplication,QTableWidget
from PyQt5.QtGui import QIcon,QFont,QColor, QBrush
from PyQt5.QtCore import QCoreApplication,Qt
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
from HTGL_UI import Ui_MainWindow 
##from datetime import datetime
##from PyQt5.QtCore import QTimer 

#####################################################################################
##ff=open('db_t.txt','r')
##global p1
##global p2
##global p3
##global p4
##global p5
##global p6
##global log1
##p1=ff.readline().strip('\n')
##p2=ff.readline().strip('\n')
##p3=ff.readline().strip('\n')
##p4=ff.readline().strip('\n')
##p5=ff.readline().strip('\n')
##p6=ff.readline().strip('\n')
##log1=False
###################################################################################
class Mains(QMainWindow,Ui_MainWindow):
##    time=datetime.now().strftime('%H:%M:%S')
##    date=datetime.now().strftime('%Y-%m-%d')
##    time1=datetime.now()
##    second = time1.second
###################################################################################
    def __init__(self):
        super(Mains,self).__init__()

        self.initUI()

        self.setupUi(self)

        self.center()       
###################################################################################
    def initUI(self):
        #定义程序图标
        self.setWindowIcon(QIcon('hetong2.jpg'))
        QApplication.setStyle(QStyleFactory.create('Windows'))
        #这种静态的方法设置一个用于显示工具提示的字体。使用16px滑体字体。
        QToolTip.setFont(QFont('SansSerif', 12))
##        self.statusBar()

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
        licenseAction.triggered.connect(self.license)

        aboutAction= QAction(QIcon('info1.jpg'), '关于...', self)
        aboutAction.setShortcut('Ctrl+A')
        aboutAction.setStatusTip('关于...')
        aboutAction.triggered.connect(self.license)

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
        
##        dataMenu = menubar.addMenu('&数据编辑(E)')
##        dataMenu.addAction(editAction)
##        dataMenu.addSeparator()
##        dataMenu.addAction(insertAction)
##        dataMenu.addSeparator()
##        dataMenu.addAction(deleteAction)
##        dataMenu.addSeparator()
##        dataMenu.addAction(backupAction)
##        dataMenu.addSeparator()
##        dataMenu.addAction(restoreAction)

##        fileMenu = menubar.addMenu('&数据输出(P)')
##        fileMenu.addAction(xlsAction)
##        fileMenu.addSeparator()
##        fileMenu.addAction(docAction)
##        fileMenu.addSeparator()
##        fileMenu.addAction(txtAction)
##        fileMenu.addSeparator()
##        fileMenu.addAction(jpgAction)
##        fileMenu.addSeparator()
##        fileMenu.addAction(printAction)

        helpMenu = menubar.addMenu('&帮助(H)')
##        helpMenu.addAction(helpAction)
##        helpMenu.addSeparator()
        helpMenu.addAction(licenseAction)
        helpMenu.addSeparator()
##        helpMenu.addAction(aboutAction)

        sysMenu = menubar.addMenu('&系统(S)')
##        sysMenu.addAction(homeAction)
##        sysMenu.addSeparator()
        sysMenu.addAction(exitAction)
        sysMenu.addSeparator()
##        sysMenu.addAction(shutAction)

##        #定义工具条
##        toolbar = self.addToolBar('主页')
##        toolbar.addAction(homeAction)
##        toolbar = self.addToolBar('合同管理')
##        toolbar.addAction(contractAction)
##        toolbar = self.addToolBar('资金管理')
##        toolbar.addAction(paymentAction)
##        toolbar = self.addToolBar('产品管理')
##        toolbar.addAction(productAction)
##        toolbar = self.addToolBar('进销管理')
##        toolbar.addAction(sellerAction)
##        toolbar = self.addToolBar('渠道管理')
##        toolbar.addAction(channelAction)
##        toolbar = self.addToolBar('客户管理')
##        toolbar.addAction(customerAction)
##        toolbar = self.addToolBar('服务管理')
##        toolbar.addAction(serviceAction)
##        toolbar = self.addToolBar('人员管理')
##        toolbar.addAction(personAction)
##        toolbar = self.addToolBar('业绩管理')
##        toolbar.addAction(achievementAction)        
##        toolbar = self.addToolBar('仓储管理')
##        toolbar.addAction(storeAction)
##        toolbar = self.addToolBar('物流管理')
##        toolbar.addAction(trafficAction)
##        toolbar = self.addToolBar('编辑')
##        toolbar.addAction(editAction)
##        toolbar = self.addToolBar('备份')
##        toolbar.addAction(backupAction)
##        toolbar = self.addToolBar('打印')
##        toolbar.addAction(printAction)
##        toolbar = self.addToolBar('帮助')
##        toolbar.addAction(helpAction)
##        toolbar = self.addToolBar('退出')
##        toolbar.addAction(exitAction)

        
        #定义主窗口位置和大小
##        image = QtGui.QPixmap()
##        image.load(r"wangge5.jpg")
##        palette1 = QtGui.QPalette()
##        palette1.setBrush(self.backgroundRole(), QtGui.QBrush(image)) #背景图片
######        palette1.setColor(self.backgroundRole(), QColor(192,253,123)) #背景颜色
##        self.setPalette(palette1)
##        self.setAutoFillBackground(True)
##        qr = self.frameGeometry()
##        self.setGeometry(qr)
##        self.setGeometry(100, 100, 300, 400)
##        self.setWindowTitle('编辑数据')
        self.show()

        
  
#####################################################################################
##    def opensql(self):
##
##        conn=pymysql.connect(host=p1,port=int(p2),user=p3,passwd=p4,db=p5,charset='utf8mb4')
##        cursor=conn.cursor()
##        sql="SELECT * FROM {}".format(p6)
##        sums=cursor.execute(sql)
##
####        text=str('总共找到{}条记录').format(sums)
####        print(text)
##        return cursor
##
#####################################################################################
##    def closesql(self):
##        cursor.close()
##        #关闭数据库连接
##        conn.close()
##
##

###################################################################################
    def license(self):
        mb = QMessageBox()
        text = mb.about(self,"版权信息！","本软件由Sun设计开发，版权所有！\n感谢您的使用！\n欢迎您给我们提出宝贵意见！\n联系电话：18636112233。") #弹窗
##        dialog.close()

#####################################################################################
##    def showDialog(self):
##        text, ok = QInputDialog.getText(self, 'Input Dialog', 
##            '请输入授权码:')
##        if ok:
##            self.lineEdit_6.setText(str(text))
##
#####################################################################################
    def exit_menu(self):
        self.close()

###################################################################################
    def return_menu(self):
        self.close()
        

###################################################################################
#    def buttonClicked(self):
      
#        sender = self.sender()
#        self.statusBar().showMessage(sender.text() + ' was pressed')
        

###################################################################################
    def center(self):
        #获得窗口
        qr = self.frameGeometry()
        #获得屏幕中心点
        cp = QDesktopWidget().availableGeometry().center()
        #显示到屏幕中心
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        
###################################################################################
#    def keyPressEvent(self, e):
#        #按Esc键退出系统
#        if e.key() == Qt.Key_Escape:
#            self.close()

###################################################################################
    def closeEvent(self, event):
##         reply = QMessageBox.warning(self, '保存数据',"保存数据吗?", QMessageBox.Yes | 
##            QMessageBox.No, QMessageBox.Yes)
##         if reply == QMessageBox.Yes:
##             mns.ps_bt1()
##         else:
##             event.ignore()
##        global log1
##        if log1 != True:
        reply = QMessageBox.warning(self, '退出系统',"确定退出吗?", QMessageBox.No | 
            QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            event.accept()
            self.exit()
        else:
            event.ignore()
                
##        else:
##            return
##        
###################################################################################
###################################################################################
    def ps_bt0(self):
        self.statusBar().showMessage("OK，Let's  GO ！！！")

###################################################################################
##################################################################################
    def ps_bt1(self):
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
        serial_no1=datetime.now().strftime('%Y%m%d%H%M%S')
        date1=datetime.now().strftime('%Y-%m-%d')

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
        mns.tblshow(rows)
###################################################################################
    def ps_bt3(self):
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
            mns.ps_bt4()

        except:
           # Rollback in case there is any error
            conn.rollback()


###################################################################################
    def ps_bt4(self):
        mns.ps_bt1()    
        try:
            rows = self.cursor.fetchone()
            mns.tblshow(rows)

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
                mns.tblshow(rows)

###################################################################################
    def ps_bt5(self):
        self.close()

###################################################################################

###################################################################################
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    mns = Mains()


###################################################################################
    #按钮控件
    mns.pushButton_1.setStatusTip('合同录入')
    mns.pushButton_1.setToolTip('合同录入')
    mns.pushButton_1.setStyleSheet("QPushButton{border-image: url(anniu3a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu3b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu3c.jpg)}")
    mns.pushButton_1.clicked.connect(mns.ps_bt0)
    
    mns.pushButton_2.setStatusTip('合同编辑')
    mns.pushButton_2.setToolTip('合同编辑')
    mns.pushButton_2.setStyleSheet("QPushButton{border-image: url(anniu27a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu27b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu27c.jpg)}")
    mns.pushButton_2.clicked.connect(mns.ps_bt0)
    
    mns.pushButton_3.setStatusTip('合同查询')
    mns.pushButton_3.setToolTip('合同查询')
    mns.pushButton_3.setStyleSheet("QPushButton{border-image: url(anniu11a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu11b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu11c.jpg)}")
    mns.pushButton_3.clicked.connect(mns.ps_bt0)
    
    mns.pushButton_4.setStatusTip('合同作废')
    mns.pushButton_4.setToolTip('合同作废')
    mns.pushButton_4.setStyleSheet("QPushButton{border-image: url(anniu8a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu8b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu8c.jpg)}")
    mns.pushButton_4.clicked.connect(mns.ps_bt0)
    
    mns.pushButton_5.setStatusTip('合同归档')
    mns.pushButton_5.setToolTip('合同归档')
    mns.pushButton_5.setStyleSheet("QPushButton{border-image: url(anniu10a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu10b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu10c.jpg)}")
    mns.pushButton_5.clicked.connect(mns.ps_bt0)

    mns.pushButton_6.setStatusTip('返回主页')
    mns.pushButton_6.setToolTip('返回主页')
    mns.pushButton_6.setStyleSheet("QPushButton{border-image: url(anniu7a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu7b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu7c.jpg)}")
    mns.pushButton_6.clicked.connect(mns.ps_bt0)


###################################################################################
    sys.exit(app.exec_())
###################################################################################
        

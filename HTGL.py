import sys
from PyQt5.QtGui import QIcon,QFont,QColor, QBrush
from PyQt5.QtCore import QCoreApplication,Qt,pyqtSignal
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
from XSGLXT import *
from HTLR import *
###################################################################################
class htgl(QMainWindow):
    sig_c1 = pyqtSignal()
    sig_c2 = pyqtSignal()
    sig_c3 = pyqtSignal()
    sig_c4 = pyqtSignal()
    sig_c5 = pyqtSignal()
    sig_c6 = pyqtSignal()

    def __init__(self):
        super(htgl,self).__init__()

        self.initUI1()

        self.center()       
###################################################################################
    def initUI1(self):
        #定义程序图标
        self.setWindowIcon(QIcon('hetong2.jpg'))
        self.setWindowTitle("合同管理")
        QApplication.setStyle(QStyleFactory.create('Windows'))
        #这种静态的方法设置一个用于显示工具提示的字体。使用16px滑体字体。
        QToolTip.setFont(QFont('SansSerif', 12))

###################################################################################
    #按钮控件
        self.resize(920, 680)
        self.setMinimumSize(QtCore.QSize(920, 680))
        self.centralwidget = QtWidgets.QWidget(self)
        self.gridLayoutWidget_2 = QtWidgets.QWidget(self.centralwidget)
        self.gridLayoutWidget_2.setGeometry(QtCore.QRect(4, 4, 924, 614))

        self.gridLayout_1 = QtWidgets.QGridLayout(self.gridLayoutWidget_2)
        self.gridLayout_1.setContentsMargins(0, 0, 0, 0)
        
        font = QtGui.QFont()
        font.setFamily("华文中宋")
        font.setPointSize(20)
        font.setBold(True)
        font.setWeight(75)
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        
        self.pButton_1 = QtWidgets.QPushButton(self.gridLayoutWidget_2)
        self.pButton_1.setMinimumSize(QtCore.QSize(300, 300))
        self.pButton_1.setMaximumSize(QtCore.QSize(300, 300))
        self.pButton_1.setBaseSize(QtCore.QSize(300, 300))
        self.pButton_1.setFont(font)
        self.pButton_1.setIconSize(QtCore.QSize(300, 300))
        self.pButton_1.setFlat(False)
        self.gridLayout_1.addWidget(self.pButton_1, 0, 0, 1, 1)
        self.pButton_1.setStatusTip('合同录入')
        self.pButton_1.setToolTip('合同录入')
        self.pButton_1.setStyleSheet("QPushButton{border-image: url(anniu3a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu3b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu3c.jpg)}")
        self.pButton_1.clicked.connect(self.slot_btn_c1)

        self.pButton_2 = QtWidgets.QPushButton(self.gridLayoutWidget_2)
        self.pButton_2.setMinimumSize(QtCore.QSize(300, 300))
        self.pButton_2.setMaximumSize(QtCore.QSize(300, 300))
        self.pButton_2.setFont(font)
        self.pButton_2.setIconSize(QtCore.QSize(300, 300))
        self.gridLayout_1.addWidget(self.pButton_2, 0, 1, 1, 1)
        self.pButton_2.setStatusTip('合同编辑')
        self.pButton_2.setToolTip('合同编辑')
        self.pButton_2.setStyleSheet("QPushButton{border-image: url(anniu27a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu27b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu27c.jpg)}")
        self.pButton_2.clicked.connect(self.slot_btn_c2)


        self.pButton_3 = QtWidgets.QPushButton(self.gridLayoutWidget_2)
        self.pButton_3.setMinimumSize(QtCore.QSize(300, 300))
        self.pButton_3.setMaximumSize(QtCore.QSize(300, 300))
        self.pButton_3.setBaseSize(QtCore.QSize(300, 300))
        self.pButton_3.setFont(font)
        self.pButton_3.setIconSize(QtCore.QSize(300, 300))
        self.pButton_3.setFlat(False)
        self.gridLayout_1.addWidget(self.pButton_3, 0, 2, 1, 1)
        self.pButton_3.setStyleSheet("QPushButton{border-image: url(anniu11a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu11b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu11c.jpg)}")
        self.pButton_3.setStatusTip('合同查询')
        self.pButton_3.setToolTip('合同查询')
        self.pButton_3.clicked.connect(self.slot_btn_c3)

        self.pButton_4 = QtWidgets.QPushButton(self.gridLayoutWidget_2)
        self.pButton_4.setMinimumSize(QtCore.QSize(300, 300))
        self.pButton_4.setMaximumSize(QtCore.QSize(300, 300))
        self.pButton_4.setFont(font)
        self.pButton_4.setIconSize(QtCore.QSize(300, 300))
        self.gridLayout_1.addWidget(self.pButton_4, 1, 0, 1, 1)
        self.pButton_4.setStatusTip('合同作废')
        self.pButton_4.setToolTip('合同作废')
        self.pButton_4.setStyleSheet("QPushButton{border-image: url(anniu8a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu8b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu8c.jpg)}")
        self.pButton_4.clicked.connect(self.slot_btn_c4)
 
        self.pButton_5 = QtWidgets.QPushButton(self.gridLayoutWidget_2)
        self.pButton_5.setMinimumSize(QtCore.QSize(300, 300))
        self.pButton_5.setMaximumSize(QtCore.QSize(300, 300))
        self.pButton_5.setFont(font)
        self.pButton_5.setIconSize(QtCore.QSize(300, 300))
        self.gridLayout_1.addWidget(self.pButton_5, 1, 1, 1, 1)
        self.pButton_5.setStatusTip('合同归档')
        self.pButton_5.setToolTip('合同归档')
        self.pButton_5.setStyleSheet("QPushButton{border-image: url(anniu10a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu10b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu10c.jpg)}")
        self.pButton_5.clicked.connect(self.slot_btn_c5)


        
        self.pButton_6 = QtWidgets.QPushButton(self.gridLayoutWidget_2)
        self.pButton_6.setMinimumSize(QtCore.QSize(300, 300))
        self.pButton_6.setMaximumSize(QtCore.QSize(300, 300))
        self.pButton_6.setFont(font)
        self.pButton_6.setIconSize(QtCore.QSize(300, 300))
        self.pButton_6.setFlat(False)
        self.pButton_6.setObjectName("pButton_6")
        self.gridLayout_1.addWidget(self.pButton_6, 1, 2, 1, 1)
        self.pButton_6.setStatusTip('返回主页')
        self.pButton_6.setToolTip('返回主页')
        self.pButton_6.setStyleSheet("QPushButton{border-image: url(anniu7a.jpg)}"
                                   "QPushButton:hover{border-image: url(anniu7b.jpg)}"
                                   "QPushButton:pressed{border-image: url(anniu7c.jpg)}")
        self.pButton_6.clicked.connect(self.slot_btn_c6)
        
        self.setCentralWidget(self.centralwidget)
        self.statusbar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self.statusbar)

        _translate = QtCore.QCoreApplication.translate
        self.pButton_3.setText(_translate("MainWindow", "\n\n\n\n合同查询"))
        self.pButton_4.setText(_translate("MainWindow", "\n\n\n\n合同作废"))
        self.pButton_1.setText(_translate("MainWindow", "\n\n\n\n合同录入"))
        self.pButton_5.setText(_translate("MainWindow", "\n\n\n\n合同归档"))
        self.pButton_2.setText(_translate("MainWindow", "\n\n\n\n合同编辑"))
        self.pButton_6.setText(_translate("MainWindow", "\n\n\n\n返回主页"))

        #定义动作
        homeAction = QAction(QIcon('home.jpg'), '主页', self)
        homeAction.setShortcut('Ctrl+H')
        homeAction.setStatusTip('返回主页')
        homeAction.triggered.connect(self.close)

        contractAction = QAction(QIcon('hetong2.jpg'), '合同管理', self)
        contractAction.setShortcut('Alt+H')
        contractAction.setStatusTip('合同管理')
##        contractAction.triggered.connect(self.slot_btn_1)

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
##        funcMenu.addAction(contractAction)
##        funcMenu.addSeparator()
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
##        self.show()
        self.sig_c1.connect(self.sig_c1_slot)
        self.sig_c2.connect(self.sig_c2_slot)
        self.sig_c3.connect(self.sig_c3_slot)
        self.sig_c4.connect(self.sig_c4_slot)
        self.sig_c5.connect(self.sig_c5_slot)
        self.sig_c6.connect(self.sig_c6_slot)
                
        self.show()
        
###################################################################################
    def slot_btn_c1(self):

        self.sig_c1.emit()

###################################################################################
    def slot_btn_c2(self):

        self.sig_c2.emit()

###################################################################################
    def slot_btn_c3(self):

        self.sig_c3.emit()

###################################################################################
    def slot_btn_c4(self):

        self.sig_c4.emit()

###################################################################################
    def slot_btn_c5(self):

        self.sig_c5.emit()

###################################################################################
    def slot_btn_c6(self):

        self.sig_c6.emit()

 
###################################################################################
    def sig_c1_slot(self):
        self.t = Edits()
        self.t.show()
        self.hide()       
###################################################################################
    def sig_c2_slot(self):
        return
###################################################################################
    def sig_c3_slot(self):
        return
###################################################################################
    def sig_c4_slot(self):
        return
###################################################################################
    def sig_c5_slot(self):
        return
###################################################################################
    def sig_c6_slot(self):

##        self.t = Mains()
##        self.t.show()
        self.hide()
        
  
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
        text = mb.about(self,"版权信息！","本软件代码由Sun设计开发，版权所有！\n软件中使用的图片及图标均从网络获取，\n图片及图标的版权归属原作者所有！\n感谢您使用本软件！\n欢迎您给我们提出宝贵意见！\n敬请关注作者头条认证号：SunAI2020。") #弹窗
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
#####################################################################################
##    def ps_bt0(self):
##        self.statusBar().showMessage("OK，Let's  GO ！！！")
##
#####################################################################################
####################################################################################
##    def ps_bt1(self):
##        conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
##        cursor=conn.cursor()
##        sql="SELECT * FROM {}".format(self.p6)
##        sums=cursor.execute(sql)
##
##        sql = "UPDATE TEST_TABLE SET CONTRACT_DATE = '{}', CONTRACT_NO = '{}',PRODUCT_NAME = '{}',\
##               PRODUCT_TYPE = '{}',FACTORY = '{}',SELLER = '{}',CUSTOMER = '{}', LICENSE = '{}', \
##               LICENSE_LIMITED = '{}', PRODUCT_LOCATION = '{}',PRODUCT_STATUS = '{}' WHERE SERIAL_NO = '{}'"\
##               .format(self.date1_chg(),self.ln2_chg(),\
##              self.ln3_chg(),self.ln4_chg(),self.cmb1_chg(),self.cmb2_chg(),self.ln5_chg(),self.ln6_chg(),\
##              self.date2_chg(),self.cmb3_chg(),self.cmb4_chg(),self.ln1_chg())
##
##        try:
##            cursor.execute(sql)
##            # Commit your changes in the database
##            conn.commit()
##            self.statusBar().showMessage('已经保存编辑内容')
##
##        except:
##           # Rollback in case there is any error
##            conn.rollback()
#####################################################################################
##    def ps_bt2(self):
##        serial_no1=datetime.now().strftime('%Y%m%d%H%M%S')
##        date1=datetime.now().strftime('%Y-%m-%d')
##
##        conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
##        cursor=conn.cursor()
##        sql="SELECT * FROM {}".format(self.p6)
##        sums=cursor.execute(sql)
##
####        rows = self.cursor.fetchall()
####        new_id=self.cursor.lastrowid
##
##        try:
##            cursor.execute("insert into test_table(serial_no,contract_date,contract_no,\
##                           product_name,product_type,factory,seller,customer,license,\
##                           license_limited,product_location,product_status)\
##                           values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(serial_no1,data1,\
##                           " "," "," "," "," "," "," ",data1," "," "))
##
##            conn.commit()
##            self.sums+=1
##            self.statusBar().showMessage('插入一条新的记录')
####            print(serial_no1)
##        except:
##           # Rollback in case there is any error
##            conn.rollback()
##
##        cursor.execute("select * from test_table where serial_no = (%s)",(serial_no1))
##        rows = cursor.fetchone()
##        mns.tblshow(rows)
#####################################################################################
##    def ps_bt3(self):
##        conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
##        cursor=conn.cursor()
##        sql="SELECT * FROM {}".format(self.p6)
##        sums=cursor.execute(sql)
##
##        sql = "DELETE FROM {} WHERE SERIAL_NO = '{}'".format(self.p6,self.ln1_chg())
##
##        try:
##            cursor.execute(sql)
##                # Commit your changes in the database
##            conn.commit()
##            self.statusBar().showMessage('删除了一条记录！！！')
##            self.sums-=1
##            mns.ps_bt4()
##
##        except:
##           # Rollback in case there is any error
##            conn.rollback()
##
##
#####################################################################################
##    def ps_bt4(self):
##        mns.ps_bt1()    
##        try:
##            rows = self.cursor.fetchone()
##            mns.tblshow(rows)
##
##        except:
####            import traceback
####            traceback.print_exc()
####            print ("Error: unable to fetch data")
##            self.statusBar().showMessage('已经是最后一条记录！！！')
##            reply = QMessageBox.question(self,"请注意：","已到最后一条记录,\
##             \n返回第一条记录吗？",QMessageBox.Yes|QMessageBox.No)
##            if reply == QMessageBox.Yes:
##
##                self.cursor.close()
##                self.conn.close()
##
##                conn=pymysql.connect(host=self.p1,port=int(self.p2),user=self.p3,passwd=self.p4,db=self.p5,charset='utf8mb4')
##                self.cursor=conn.cursor()
##                sql="SELECT * FROM {}".format(self.p6)
##                sums=self.cursor.execute(sql)
##                
####                self.cursor.scroll(0,mode="absolute")
##                rows = self.cursor.fetchone()
####                print(sql)
##                mns.tblshow(rows)
##
#####################################################################################
##    def ps_bt5(self):
##        self.close()
##
###################################################################################

###################################################################################
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    htgls =htgl()

    htgls.show()
    sys.exit(app.exec_())
###################################################################################
        

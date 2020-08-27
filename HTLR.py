import sys
import pymysql
from PyQt5.QtGui import QIcon,QFont,QColor, QBrush
from PyQt5.QtCore import QCoreApplication,Qt,pyqtSignal
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
from datetime import datetime
from XSGLXT import *
###################################################################################
global p3
global conn
global cursor
global rows
global sunms
global sql
global now_row
global col0
global col1
global col2
global col3
global col4
global col5
global col6
global col7
global col8
global col9
global col10
global col11
global col12
global col13
global col14
global col15
global col16
global col17
global col18
global col19
global col20
global col21
global col22
global col23
###################################################################################
class Edits(QMainWindow):
    
    sig_e1 = pyqtSignal()
    
###################################################################################
    def __init__(self):
        super(Edits,self).__init__()
        self.opensql()
        self.initUI()

        self.tblshow(rows)
        self.center()
        
###################################################################################
    def initUI(self):
        #定义程序图标
        self.setWindowIcon(QIcon('chanpin12.jpg'))
        QApplication.setStyle(QStyleFactory.create('Windows'))
        #设置用于显示工具提示的字体。使用12px字体。
        QToolTip.setFont(QFont('SansSerif', 12))
        self.statusBar()

###################################################################################
    #按钮控件
        self.resize(1200, 1100)
        self.setMinimumSize(QtCore.QSize(1100, 1100))
##        self.setIconSize(QtCore.QSize(40, 40))
##        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        font = QtGui.QFont()
        font.setPointSize(16)
        font.setBold(True)
        font.setWeight(75)
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        self.centralwidget = QtWidgets.QWidget()
        
        self.formLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.formLayoutWidget.setGeometry(QtCore.QRect(120, 100, 831, 881))
        self.formLayout = QtWidgets.QFormLayout(self.formLayoutWidget)
        self.formLayout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.formLayout.setLabelAlignment(QtCore.Qt.AlignCenter)
        self.formLayout.setFormAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignTop)
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout.setVerticalSpacing(20)
        
###################################################################################
    #标签控件
        self.label_1 = QtWidgets.QLabel(self.centralwidget)
        self.label_1.setGeometry(QtCore.QRect(120, 41, 241, 41))
        self.label_1.setFont(font)
        self.label_1.setStyleSheet("color: rgb(0, 170, 0);")

        self.label_2 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_2.setFont(font)
        self.label_2.setStyleSheet("color: rgb(255, 100,100);")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label_2)


        self.label_3 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_3.setFont(font)
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_3)
        
        self.label_4 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_4.setFont(font)
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_4)
        
        self.label_5 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_5.setFont(font)
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.LabelRole, self.label_5)
        
        self.label_6 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_6.setFont(font)
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.LabelRole, self.label_6)

        self.label_7 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_7.setFont(font)
        self.formLayout.setWidget(5, QtWidgets.QFormLayout.LabelRole, self.label_7)
        
        self.label_8 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_8.setFont(font)
        self.formLayout.setWidget(6, QtWidgets.QFormLayout.LabelRole, self.label_8)
        
        self.label_9 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_9.setFont(font)
        self.formLayout.setWidget(7, QtWidgets.QFormLayout.LabelRole, self.label_9)
        
        self.label_10 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_10.setFont(font)
        self.formLayout.setWidget(8, QtWidgets.QFormLayout.LabelRole, self.label_10)
        
        self.label_11 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_11.setFont(font)
        self.formLayout.setWidget(9, QtWidgets.QFormLayout.LabelRole, self.label_11)
        
        self.label_12 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_12.setFont(font)
        self.formLayout.setWidget(10, QtWidgets.QFormLayout.LabelRole, self.label_12)
        
        self.label_13 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_13.setFont(font)
        self.formLayout.setWidget(11, QtWidgets.QFormLayout.LabelRole, self.label_13)

        self.label_14 = QtWidgets.QLabel(self.centralwidget)
        self.label_14.setGeometry(QtCore.QRect(580, 47, 111, 41))
        self.label_14.setFont(font)
        
        self.label_15 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_15.setFont(font)
        self.formLayout.setWidget(12, QtWidgets.QFormLayout.LabelRole, self.label_15)
        
        self.label_16 = QtWidgets.QLabel(self.formLayoutWidget)
        self.label_16.setFont(font)
        self.formLayout.setWidget(13, QtWidgets.QFormLayout.LabelRole, self.label_16)

        self.label_16.setStyleSheet("color: rgb(155, 10, 10);")
        
###################################################################################
    #文本行控件
        self.lineEdit_1 = QtWidgets.QLineEdit(self.formLayoutWidget)
        self.lineEdit_1.setEnabled(True)
        self.lineEdit_1.setFont(font)
        self.lineEdit_1.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        self.lineEdit_1.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.lineEdit_1.setStyleSheet("color: rgb(155, 10, 10);")
        self.lineEdit_1.setInputMethodHints(QtCore.Qt.ImhNone)
        self.lineEdit_1.setReadOnly(True)
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.lineEdit_1)
        self.lineEdit_1.textChanged.connect(self.ln1_chg)
        
        self.lineEdit_2 = QtWidgets.QLineEdit(self.formLayoutWidget)
        self.lineEdit_2.setFont(font)
        self.lineEdit_2.setClearButtonEnabled(True)
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.FieldRole, self.lineEdit_2)
        self.lineEdit_2.textChanged.connect(self.ln2_chg)
        
        self.lineEdit_3 = QtWidgets.QLineEdit(self.formLayoutWidget)
        self.lineEdit_3.setFont(font)
        self.lineEdit_3.setClearButtonEnabled(True)
        self.formLayout.setWidget(7, QtWidgets.QFormLayout.FieldRole, self.lineEdit_3)
        self.lineEdit_3.textChanged.connect(self.ln3_chg)
        
        self.lineEdit_4 = QtWidgets.QLineEdit(self.formLayoutWidget)
        self.lineEdit_4.setFont(font)
        self.lineEdit_4.setClearButtonEnabled(True)
        self.formLayout.setWidget(8, QtWidgets.QFormLayout.FieldRole, self.lineEdit_4)
        self.lineEdit_4.textChanged.connect(self.ln4_chg)
        
        self.lineEdit_5 = QtWidgets.QLineEdit(self.formLayoutWidget)
        self.lineEdit_5.setFont(font)
        self.lineEdit_5.setClearButtonEnabled(True)
        self.formLayout.setWidget(9, QtWidgets.QFormLayout.FieldRole, self.lineEdit_5)
        self.lineEdit_5.textChanged.connect(self.ln5_chg)
        
        self.lineEdit_6 = QtWidgets.QLineEdit(self.formLayoutWidget)
        self.lineEdit_6.setFont(font)
        self.lineEdit_6.setClearButtonEnabled(True)
        self.formLayout.setWidget(10, QtWidgets.QFormLayout.FieldRole, self.lineEdit_6)
        self.lineEdit_6.textChanged.connect(self.ln6_chg)

        self.lineEdit_7 = QtWidgets.QLineEdit(self.formLayoutWidget)
        self.lineEdit_7.setFont(font)
        self.lineEdit_7.setClearButtonEnabled(True)
        self.formLayout.setWidget(11, QtWidgets.QFormLayout.FieldRole, self.lineEdit_7)
        self.lineEdit_7.textChanged.connect(self.ln7_chg)

        self.lineEdit_8 = QtWidgets.QLineEdit(self.formLayoutWidget)
        self.lineEdit_8.setFont(font)
        self.lineEdit_8.setClearButtonEnabled(True)
        self.formLayout.setWidget(12, QtWidgets.QFormLayout.FieldRole, self.lineEdit_8)
        self.lineEdit_8.textChanged.connect(self.ln8_chg)
        
        self.lineEdit_9 = QtWidgets.QLineEdit(self.formLayoutWidget)
        self.lineEdit_9.setEnabled(True)
        self.lineEdit_9.setFont(font)
        self.lineEdit_9.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        self.lineEdit_9.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.lineEdit_9.setStyleSheet("color: rgb(155, 10, 10);")
        self.lineEdit_9.setInputMethodHints(QtCore.Qt.ImhNone)
        self.lineEdit_9.setReadOnly(True)
        self.formLayout.setWidget(13, QtWidgets.QFormLayout.FieldRole, self.lineEdit_9)
        self.lineEdit_9.textChanged.connect(self.ln9_chg)

        
###################################################################################
    #日期控件
        self.dateEdit_1 = QtWidgets.QDateEdit(self.formLayoutWidget)
        self.dateEdit_1.setFont(font)
        self.dateEdit_1.setDate(QtCore.QDate(2020, 1, 1))
        self.dateEdit_1.setObjectName("dateEdit_1")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.dateEdit_1)
        self.dateEdit_1.dateChanged.connect(self.date1_chg)
      
###################################################################################
    #下拉框控件
        self.comboBox_1 = QtWidgets.QComboBox(self.formLayoutWidget)
        self.comboBox_1.setFont(font)
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.comboBox_1)
        self.comboBox_1.currentTextChanged.connect(self.cmb1_chg)
       
        self.comboBox_2 = QtWidgets.QComboBox(self.formLayoutWidget)
        self.comboBox_2.setFont(font)
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.FieldRole, self.comboBox_2)
        self.comboBox_2.setEditable(True)
        self.comboBox_2.currentTextChanged.connect(self.cmb2_chg)

        self.comboBox_3 = QtWidgets.QComboBox(self.formLayoutWidget)
        self.comboBox_3.setFont(font)
        self.formLayout.setWidget(5, QtWidgets.QFormLayout.FieldRole, self.comboBox_3)
        self.comboBox_3.setEditable(True)
        self.comboBox_3.currentTextChanged.connect(self.cmb3_chg)
        
        self.comboBox_4 = QtWidgets.QComboBox(self.formLayoutWidget)
        self.comboBox_4.setFont(font)
        self.formLayout.setWidget(6, QtWidgets.QFormLayout.FieldRole, self.comboBox_4)
        self.comboBox_4.setEditable(True)
        self.comboBox_4.currentTextChanged.connect(self.cmb4_chg)
    
###################################################################################
    #按钮控件
        self.pushButton_1 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_1.setGeometry(QtCore.QRect(120, 960, 131, 51))
        self.pushButton_1.setFont(font)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap("save.jpg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.pushButton_1.setIcon(icon1)
        self.pushButton_1.setIconSize(QtCore.QSize(40, 40))
        self.pushButton_1.setFlat(False)
        self.pushButton_1.setStatusTip('保存当前编辑的内容')
        self.pushButton_1.setToolTip('保存编辑')
        self.pushButton_1.clicked.connect(self.ps_bt1)        

        self.pushButton_2 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_2.setGeometry(QtCore.QRect(290, 960, 131, 51))
        self.pushButton_2.setFont(font)
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap("add1.jpg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.pushButton_2.setIcon(icon2)
        self.pushButton_2.setIconSize(QtCore.QSize(40, 40))
        self.pushButton_2.setStatusTip('新建一条记录')
        self.pushButton_2.setToolTip('新建记录')
        self.pushButton_2.clicked.connect(self.ps_bt2)

        self.pushButton_3 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_3.setGeometry(QtCore.QRect(460, 960, 131, 51))
        self.pushButton_3.setFont(font)
        icon3 = QtGui.QIcon()
        icon3.addPixmap(QtGui.QPixmap("delete.jpg.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.pushButton_3.setIcon(icon3)
        self.pushButton_3.setIconSize(QtCore.QSize(40, 40))
        self.pushButton_3.setStatusTip('删除当前记录，请谨慎操作！')
        self.pushButton_3.setToolTip('删除记录')
        self.pushButton_3.clicked.connect(self.ps_bt3)

        self.pushButton_4 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_4.setGeometry(QtCore.QRect(640, 960, 141, 51))
        self.pushButton_4.setFont(font)
        icon4 = QtGui.QIcon()
        icon4.addPixmap(QtGui.QPixmap("next1.jpg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.pushButton_4.setIcon(icon4)
        self.pushButton_4.setIconSize(QtCore.QSize(40, 40))
        self.pushButton_4.setStatusTip('保存当前记录内容，并跳转到下一条记录')
        self.pushButton_4.setToolTip('转到下一条记录')
        self.pushButton_4.clicked.connect(self.ps_bt4)

        
        self.pushButton_5 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_5.setGeometry(QtCore.QRect(810, 960, 131, 51))
        self.pushButton_5.setFont(font)
        icon5 = QtGui.QIcon()
        icon5.addPixmap(QtGui.QPixmap("exit4.jpg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.pushButton_5.setIcon(icon5)
        self.pushButton_5.setIconSize(QtCore.QSize(40, 40))
        self.pushButton_5.setStatusTip('退出当前窗口，请先保存，以免数据丢失！')
        self.pushButton_5.setToolTip('退出当前窗口！')
        self.pushButton_5.clicked.connect(self.close)

###################################################################################
    #LCD控件
        self.lcdNumber = QtWidgets.QLCDNumber(self.centralwidget)
        self.lcdNumber.setGeometry(QtCore.QRect(720, 40, 231, 51))
        font.setPointSize(12)
        self.lcdNumber.setFont(font)
        self.lcdNumber.setStyleSheet("color:rgb(0, 0, 255)")
        self.lcdNumber.setFrameShape(QtWidgets.QFrame.WinPanel)
        self.lcdNumber.setFrameShadow(QtWidgets.QFrame.Raised)
        self.lcdNumber.setLineWidth(4)
        self.lcdNumber.setMidLineWidth(1)
        self.lcdNumber.setDigitCount(8)
        self.lcdNumber.setObjectName("lcdNumber")

        
        self.setCentralWidget(self.centralwidget)
        self.statusbar = QtWidgets.QStatusBar()
        font = QtGui.QFont()
        font.setPointSize(12)
        self.statusbar.setFont(font)
        self.setStatusBar(self.statusbar)

        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle(_translate("MainWindow", "编辑"))
        
        self.label_1.setText(_translate("MainWindow", "数据编辑："))
        self.label_2.setText(_translate("MainWindow", "合同 UID："))
        self.label_3.setText(_translate("MainWindow", "合同类型："))
        self.label_4.setText(_translate("MainWindow", "签订日期："))
        self.label_5.setText(_translate("MainWindow", "项目名称："))
        self.label_6.setText(_translate("MainWindow", "甲方："))
        self.label_7.setText(_translate("MainWindow", "乙方："))
        self.label_8.setText(_translate("MainWindow", "丙方："))
        self.label_9.setText(_translate("MainWindow", "合同金额："))
        self.label_10.setText(_translate("MainWindow", "结算方式："))
        self.label_11.setText(_translate("MainWindow", "产品列表："))
        self.label_12.setText(_translate("MainWindow", "产品金额："))
        self.label_13.setText(_translate("MainWindow", "服务项目："))
        self.label_14.setText(_translate("MainWindow", "记录号："))
        self.label_15.setText(_translate("MainWindow", "服务费用："))
        self.label_16.setText(_translate("MainWindow", "合同录入："))
        
        self.pushButton_1.setText(_translate("MainWindow", "保存"))
        self.pushButton_2.setText(_translate("MainWindow", "新増"))
        self.pushButton_3.setText(_translate("MainWindow", "删除"))
        self.pushButton_4.setText(_translate("MainWindow", "下一条"))
        self.pushButton_5.setText(_translate("MainWindow", "退出"))


        #定义动作
        homeAction = QAction(QIcon('home.jpg'), '主页', self)
        homeAction.setShortcut('Ctrl+H')
        homeAction.setStatusTip('返回主页')
        homeAction.triggered.connect(self.slot_btn_e1)

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
        sysMenu.addAction(homeAction)
        sysMenu.addSeparator()
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

        self.sig_e1.connect(self.sig_e1_slot)
                
        self.show()
        
###################################################################################
    def slot_btn_e1(self):

        self.sig_e1.emit()

###################################################################################
    def sig_e1_slot(self):

        self.close()
        self.t = Mains()
        self.t.show()
        

###################################################################################
    def opensql(self):
###################################################################################
        global conn
        global cursor
        global rows
        global sums
        global sql
        global p3
        global now_row
        
        ff=open('db_c.txt','r')
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
        now_row = cursor.rownumber

###################################################################################
    def closesql(self):
###################################################################################
        #关闭数据库连接
        cursor.close()
        conn.close()

###################################################################################
    def license(self):
        mb = QMessageBox()
        text = mb.about(self,"版权信息！","本软件代码由Sun设计开发，版权所有！\n软件中使用的图片及图标均从网络获取，\n图片及图标的版权归属原作者所有！\n感谢您使用本软件！\n欢迎您给我们提出宝贵意见！\n敬请关注作者头条认证号：SunAI2020。") #弹窗

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
        self.sig_e1.emit()
        

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
##      读取数据库记录
        global conn
        global cursor
        global sums
        global sql
        global now_row
        global col0
        global col1
        global col2
        global col3
        global col4
        global col5
        global col6
        global col7
        global col8
        global col9
        global col10
        global col11
        global col12
        global col13
        global col14
        global col15
        global col16
        global col17
        global col18
        global col19
        global col20
        global col21
        global col22
        global col23

        col0=rows[0]
        col1=rows[1]
        col2=rows[2]
        col3=rows[3]
        col4=rows[4]
        col5=rows[5]
        col6=rows[6]
        col7=rows[7]
        col8=rows[8]
        col9=rows[9]
        col10=rows[10]
        col11=rows[11]
        col12=rows[12]
        col13=rows[13]
        col14=rows[14]
        col15=rows[15]
        col16=rows[16]
        col17=rows[17]
        col18=rows[18]
        col19=rows[19]
        col20=rows[20]
        col21=rows[21]
        col22=rows[22]
        col23=rows[23]
        
        #LCD显示记录数
##        now_row = cursor.rownumber
        lcd1=str(now_row)+' : '+str(sums)
        self.lcdNumber.display(lcd1)
        self.statusBar().showMessage('正在编辑第{}条记录'.format(now_row))

        #显示数据列表
        self.lineEdit_1.setText(col0)
        self.lineEdit_2.setText(col3)
        self.lineEdit_3.setText(str(col7)+"元")
        self.lineEdit_4.setText(col8)
        self.lineEdit_5.setText(col10)
        self.lineEdit_6.setText(str(col11)+"元")
        self.lineEdit_7.setText(col12)
        self.lineEdit_8.setText(str(col13)+"元")
        self.lineEdit_9.setText(col14)

        self.dateEdit_1.setDate(col2)
        
        self.comboBox_1.clear()
        col1=rows[1]        
        self.comboBox_1.addItem(col1)
        fl1=open('h_list.txt','r')
        list1=fl1.readlines()
        for it1 in list1:
            if it1.strip('\n') != col1:
                self.comboBox_1.addItem(it1.strip('\n'))
        fl1.close()

        self.comboBox_2.clear()
        col4=rows[4]
        self.comboBox_2.addItem(col4)
        fl2=open('c_list.txt','r')
        list2=fl2.readlines()
        for it2 in list2:
            if it2.strip('\n') != col4:
                self.comboBox_2.addItem(it2.strip('\n'))
        fl2.close()

        self.comboBox_3.clear()
        col5=rows[5]
        self.comboBox_3.addItem(col5)
        fl3=open('c_list.txt','r')
        list3=fl3.readlines()
        for it3 in list3:
            if it3.strip('\n') != col5:
                self.comboBox_3.addItem(it3.strip('\n'))
        fl3.close()

        self.comboBox_4.clear()
        col6=rows[6]
        self.comboBox_4.addItem(col6)
        fl4=open('c_list.txt','r')
        list4=fl4.readlines()
        for it4 in list4:
            if it4.strip('\n') != col6:
                self.comboBox_4.addItem(it4.strip('\n'))
        fl4.close()
    
###################################################################################
    def date1_chg(self):
        global col2
        col2=self.dateEdit_1.date().toString(Qt.ISODate)

###################################################################################
    def ln1_chg(self):
        global col0
        col0=self.lineEdit_1.text()

###################################################################################
    def ln2_chg(self):
        global col3
        col3=self.lineEdit_2.text()

###################################################################################
    def ln3_chg(self):
        global col7
        col7=self.lineEdit_3.text()
        col7=col7.strip("元")
    
###################################################################################
    def ln4_chg(self):
        global col8
        col8=self.lineEdit_4.text()

###################################################################################
    def ln5_chg(self):
        global col9
        col9=self.lineEdit_5.text()

###################################################################################
    def ln6_chg(self):
        global col10
        col10=self.lineEdit_6.text()
        col10=col10.strip("元")
      
###################################################################################
    def ln7_chg(self):
        global col11
        col11=self.lineEdit_7.text()
      
###################################################################################
    def ln8_chg(self):
        global col12
        col12=self.lineEdit_8.text()
        col12=col12.strip("元")
        
###################################################################################
    def ln9_chg(self):
        global col13
        col13=self.lineEdit_9.text()
      
###################################################################################
    def cmb1_chg(self):
        global col1
        col1=self.comboBox_1.currentText()

###################################################################################
    def cmb2_chg(self):
        global col4
        col4=self.comboBox_2.currentText()

###################################################################################
    def cmb3_chg(self):
        global col5
        col5=self.comboBox_3.currentText()

###################################################################################
    def cmb4_chg(self):
        global col6
        col6=self.comboBox_4.currentText()
        
###################################################################################
    def ps_bt1(self):
        global conn
        global cursor
        global sums
        global sql
        global rows
        global now_row
        
##        now_row=cursor.rownumber        
        sql = "UPDATE CONTRACT SET 合同类型 = '{}',签订日期 = '{}',\
               项目名称 = '{}',甲方 = '{}',乙方 = '{}',丙方 = '{}', 合同金额 = '{}',\
               结算方式 = '{}',合同产品 = '{}',产品金额 = '{}',合同服务 = '{}',\
               服务费金额 = '{}',录入人 = '{}' WHERE UID_C = '{}'"\
               .format(str(col1),str(col2),str(col3),str(col4),str(col5),str(col6),\
               str(col7),str(col8),str(col9),str(col10),str(col11),str(col12),str(col13),str(col0))
        try:
            cursor.execute(sql)
            # Commit your changes in the database
            conn.commit()
            recs=cursor.rowcount

            print(recs, " 条记录已更新,记录号：",now_row)
            self.statusBar().showMessage("{}条记录已更新,记录号：{}".format(str(recs),str(now_row)))
##            if recs != 0:
##                sql="SELECT * FROM contract"
##                sums=cursor.execute(sql)
##                sql="SELECT * FROM contract WHERE UID_C = '{}' ".format(col0)
##                cursor.execute(sql)
##                rows=cursor.fetchone()
##                print(col0,rows)
        except:
           # Rollback in case there is any error
            conn.rollback()
##        eds.tblshow(rows)
        print(recs, " 条记录已更新,记录号：",now_row)
###################################################################################
    def ps_bt2(self):
###################################################################################
        global conn
        global cursor
        global sums
        global sql
        global rows
        global now_row
        
        uid1=datetime.now().strftime('%Y%m%d%H%M%S')
        date1=datetime.now().strftime('%Y-%m-%d')

        try:
            cursor.execute("insert into CONTRACT(UID_C,合同类型,签订日期,甲方,乙方,丙方,\
                           合同金额,产品金额,服务费金额,录入人) \
                            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(str(uid1),"请选择...",str(date1),"请选择或输入...",\
                           "请选择或输入...","请选择或输入...","0.00","0.00","0.00",str(p3)))

            conn.commit()
            sums+=1
            self.statusBar().showMessage("新建了一条记录,记录号：{}".format(now_row))
##            print(col0)
        except:
           # Rollback in case there is any error
            conn.rollback()

        cursor.execute("select * from contract where UID_C = (%s)",(str(uid1)))
        rows = cursor.fetchone()
        now_row=sums
        eds.tblshow(rows)
###################################################################################
    def ps_bt3(self):
###################################################################################
        global conn
        global cursor
        global sums
        global sql
        global rows
        global now_row
        
        sql = "DELETE FROM contract WHERE UID_C = '{}'".format(str(col0))

        try:
            cursor.execute(sql)
                # Commit your changes in the database
            conn.commit()
            self.statusBar().showMessage("删除了一条记录,记录号：{}".format(now_row))
            sums-=1

            cursor.fetchone()
            rows=cursor.fetchone()
##            now_row +=1
            print(now_row,rows)
##            eds.tblshow(rows)
            eds.ps_bt4()

        except:
           # Rollback in case there is any error
            conn.rollback()


###################################################################################
    def ps_bt4(self):
###################################################################################
        global conn
        global cursor
        global sums
        global sql
        global rows
        global now_row
        
##        eds.ps_bt1()
        print("sums=",sums)
        print("now_row=",now_row)
        if now_row < sums:
            rows = cursor.fetchone()
            now_row +=1
            print("rows=",rows)
            print("now_row=",now_row)
            self.tblshow(rows)
        else:
##        try:
##            rows = cursor.fetchone()
##            eds.tblshow(rows)
##
##        except:
##            import traceback
##            traceback.print_exc()
##            print ("Error: unable to fetch data")
            self.statusBar().showMessage('已经是最后一条记录！！！')
            reply = QMessageBox.question(self,"请注意：","已到最后一条记录,\
             \n返回第一条记录吗？",QMessageBox.Yes|QMessageBox.No)
            if reply == QMessageBox.Yes:
                
                cursor.scroll(0,mode="absolute")
##                now_row =1
##                rows = cursor.fetchone()
                now_row = cursor.rownumber
                self.ps_bt4()
##                eds.tblshow(rows)

###################################################################################
    def ps_bt5(self):
###################################################################################
        self.close()
        
###################################################################################


###################################################################################
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    eds = Edits()
    
    sys.exit(app.exec_())
###################################################################################
        

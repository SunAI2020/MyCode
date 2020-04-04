import sys
import pymysql
#from PyQt5.QtWidgets import QWidget,QMainWindow,QInputDialog,QTextEdit,QAction, QToolTip,QTableWidget,QMessageBox,QDesktopWidget,QPushButton,QApplication,QTableWidget
from PyQt5.QtGui import QIcon,QFont,QColor, QBrush
from PyQt5.QtCore import QCoreApplication,Qt
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
from product_l2 import Ui_MainWindow as MainWindow1
##from edit_2 import Ui_mainWindow as Form1
from subprocess import Popen, PIPE, STDOUT
from Edit3 import *

from datetime import datetime

###################################################################################
def Center(self):
        
        #获得窗口
    qr = self.frameGeometry()
        #获得屏幕中心点
    cp = QDesktopWidget().availableGeometry().center()
        #显示到屏幕中心
    qr.moveCenter(cp)
    self.move(qr.topLeft())
###################################################################################
        
###################################################################################
class Products(QMainWindow,MainWindow1):
###################################################################################
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
        super(Products,self).__init__()

        self.initUI()
        self.setupUi(self)
        self.showMaximized()
        
##        self.showFullScreen()

        self.opensql()
        self.tbl_show()

        Center

###################################################################################
    def initUI(self):
###################################################################################
        #定义程序图标
        self.setWindowIcon(QIcon('chanpin12.jpg'))
        QApplication.setStyle(QStyleFactory.create('Windows'))
        #这种静态的方法设置一个用于显示工具提示的字体。使用16px滑体字体。
        QToolTip.setFont(QFont('SansSerif', 12))
        self.statusBar()
        Center(self)


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
        menubar.setStyleSheet("color:rgb(10,10,10,255);font-size:30px;\
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
    def tbl_show(self,pages=0):
###################################################################################
        conn=pymysql.connect(host='192.168.3.128',port=3306,user='sun',passwd='123456',db='test_schema',charset='utf8mb4')
        #获取游标
        cursor=conn.cursor()
        sums=cursor.execute("SELECT * FROM test_table")
        #返回受影响的行数
        rows = sums
        if rows <= 0:
            text=str('没有找到数据')
            self.lineEdit_3.setText(str(text))
            QMessageBox.about(self, "No Data", "No Attendance has been recorded yet")

        try:
            items = cursor.fetchall()
            text=str('第{}页').format(pages+1)
            self.lineEdit_5.setText(str(text))
            for i in range(rows):
                row_item = items[i]

                for j in range(12):
                    each_item=items[i][j]
                    item = QTableWidgetItem(str(items[i][j]))
                    self.tableWidget.setItem(i,j,item)
        except:
            import traceback
            traceback.print_exc()
            print ("Error: unable to fetch data")
        return sums

    def tbl_up(self):
        table=Table()
        table.show()
        pts.center()

##    def closesql(self):
##        cursor.close()
##        #关闭数据库连接
##        conn.close()

    def ps_bt1(self):
        text=str('总共找到{}条记录').format(sums)
        self.lineEdit_3.setText(str(text))
        
    def showDialog(self):
        text, ok = QInputDialog.getText(self, 'Input Dialog', 
            '请输入授权码:')
        if ok:
            self.lineEdit_1.setText(str(text))

    def ps_bt5(self):
        self.close()

    def ps_bt6(self):
        self.close()

    def ps_bt7(self):
        self.close()

    def ps_bt8(self):
        self.close()

    def ps_bt9(self):
        self.close()

    def ps_bt10(self):
        self.close()

    def tg_cb1(self,state):
        if state == Qt.Checked:
            pt_cb1='已交付'
        else:
            pt_cb1='未交付'
            
        text=str('查找到：{}的产品，共有{}条记录。').format(pt_cb1,sums)
        self.lineEdit_3.setText(str(text))
        return pt_cb1

    def tg_cb2(self,state):
        if state == Qt.Checked:
            pt_cb2='返修中'
        else:
            pt_cb2='未返修'
            
        text=str('查找到：{}的产品，共有{}条记录。').format(pt_cb2,sums)
        self.lineEdit_3.setText(str(text))
        return pt_cb2

    def tg_cb3(self, state):
        if state == Qt.Checked:
            pt_cb3='授权到期'
        else:
            pt_cb3='授权有效'
            
        text=str('查找到：{}的产品，共有{}条记录。').format(pt_cb3,sums)
        self.lineEdit_3.setText(str(text))
        return pt_cb3

    def tg_cb4(self, state):
        if state == Qt.Checked:
            pt_cb4='库存中'
        else:
            pt_cb4='已出库'
            
        text=str('查找到：{}的产品，共有{}条记录。').format(pt_cb4,sums)
        self.lineEdit_3.setText(str(text))
        return pt_cb4
    
    def tg_cb5(self, state):
        if state == Qt.Checked:
            pt_cb5='已报废'
        else:
            pt_cb5='未报废'
            
        text=str('查找到：{}的产品，共有{}条记录。').format(pt_cb5,sums)
        self.lineEdit_3.setText(str(text))
        return pt_cb5
        
    def exit_menu(self):
        self.close()

    def return_menu(self):
        self.close()

    def edit_it(self):
         reply = QMessageBox.question(self, '进入编辑',"编辑该行数据吗?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.No)
         if reply == QMessageBox.Yes:
             p = Popen([sys.executable, "edit3.py"],stdout=PIPE, stdin=PIPE, stderr=STDOUT)
         else:
             return

#    def buttonClicked(self):
      
#        sender = self.sender()
#        self.statusBar().showMessage(sender.text() + ' was pressed')
        

##    def center(self):
##        
##        #获得窗口
##        qr = self.frameGeometry()
##        #获得屏幕中心点
##        cp = QDesktopWidget().availableGeometry().center()
##        #显示到屏幕中心
##        qr.moveCenter(cp)
##        self.move(qr.topLeft())
        
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


    def generateMenu(self, pos):
    # 计算有多少条数据，默认-1,
        row_num = -1
        for i in self.tableWidget.selectionModel().selection().indexes():
            row_num = i.row()

    # 表格中，在有效数据行支持右键弹出菜单
        if row_num < sums:
             menu = QMenu()
             item1 = menu.addAction(u'编辑该行数据')
             item2 = menu.addAction(u'插入一行')
             item3 = menu.addAction(u'删除该行')
             action = menu.exec_(self.tableWidget.mapToGlobal(pos))
             pts.row_num=row_num
            # 显示选中行的数据文本
             if action == item1:
                 print('你选了选项一，当前行文字内容是：', self.tableWidget.item(row_num, 0).text(),
                      self.tableWidget.item(row_num, 1).text(),
                      self.tableWidget.item(row_num, 2).text())
                 p = Popen([sys.executable, "edit3.py"],stdout=PIPE, stdin=PIPE, stderr=STDOUT)



             if action == item2:
                 print('你选了选项二，当前行文字内容是：', self.tableWidget.item(row_num, 0).text(),
                      self.tableWidget.item(row_num, 1).text(),
                      self.tableWidget.item(row_num, 2).text())
                 eds=Edit3.Edits()
                 eds.__init__(self)
                 eds.tblshow(self,row_num)

             if action == item3:
                 print('你选了选项三，当前行文字内容是：', self.tableWidget.item(row_num, 0).text(),
                      self.tableWidget.item(row_num, 1).text(),
                      self.tableWidget.item(row_num, 2).text())
            
             return row_num


        

        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    pts = Products()

    #显示的数据列表页
    pages=0
    #查找到的记录行数
    sums=pts.tbl_show()
    row_num=0

##    #下拉菜单
##    pts.action42.triggered.connect(pts.exit_menu)
##    pts.action41.triggered.connect(pts.return_menu)

    #按钮控件
    pts.pushButton_1.clicked.connect(pts.ps_bt1)
    pts.pushButton_2.clicked.connect(pts.showDialog)
    pts.pushButton_5.clicked.connect(pts.ps_bt5)
    pts.pushButton_6.clicked.connect(pts.ps_bt6)
    pts.pushButton_7.clicked.connect(pts.ps_bt7)
    pts.pushButton_8.clicked.connect(pts.ps_bt8)
    pts.pushButton_9.clicked.connect(pts.ps_bt9)
    pts.pushButton_10.clicked.connect(pts.ps_bt10)
    
    #复选框控件

    pts.checkBox_1.stateChanged.connect(pts.tg_cb1)
    pts.checkBox_2.stateChanged.connect(pts.tg_cb2)
    pts.checkBox_3.stateChanged.connect(pts.tg_cb3)
    pts.checkBox_4.stateChanged.connect(pts.tg_cb4)
    pts.checkBox_5.stateChanged.connect(pts.tg_cb5)

    # 允许右键产生菜单
    pts.tableWidget.setContextMenuPolicy(Qt.CustomContextMenu)
     # 将右键菜单绑定到槽函数generateMenu
    pts.tableWidget.customContextMenuRequested.connect(pts.generateMenu)

    pts.tableWidget.clicked.connect(pts.edit_it)
    
    sys.exit(app.exec_())
        

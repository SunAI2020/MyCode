import sys
import pymysql
#from PyQt5.QtWidgets import QWidget,QMainWindow,QInputDialog,QTextEdit,QAction, QToolTip,QTableWidget,QMessageBox,QDesktopWidget,QPushButton,QApplication,QTableWidget
from PyQt5.QtGui import QIcon,QFont,QColor, QBrush
from PyQt5.QtCore import QCoreApplication,Qt
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
from sql_ttt import Ui_MainWindow as MainWindow1
from edit_1 import Ui_Form as Form1

from datetime import datetime

class Products(QMainWindow,MainWindow1):
    
    def __init__(self):
        super(Products,self).__init__()

        self.initUI()

        self.setupUi(self)
        self.opensql()
        self.tbl_show()
        self.center()

        
        
    def initUI(self):
        #定义程序图标
        self.setWindowIcon(QIcon('chanpin12.jpg'))

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
        contractAction.setShortcut('Ctrl+Q')
        contractAction.setStatusTip('合同管理')
        contractAction.triggered.connect(self.close)

        paymentAction = QAction(QIcon('zijin2.jpg'), '资金管理', self)
        paymentAction.setShortcut('Ctrl+Q')
        paymentAction.setStatusTip('资金管理')
        paymentAction.triggered.connect(self.close)

        serviceAction = QAction(QIcon('fuwu5.jpg'), '服务管理', self)
        serviceAction.setShortcut('Ctrl+Q')
        serviceAction.setStatusTip('退出系统')
        serviceAction.triggered.connect(self.close)

        personAction = QAction(QIcon('tuandui1.jpg'), '人员管理', self)
        personAction.setShortcut('Ctrl+Q')
        personAction.setStatusTip('退出系统')
        personAction.triggered.connect(self.close)

        storeAction = QAction(QIcon('kufang2.jpg'), '仓储管理', self)
        storeAction.setShortcut('Ctrl+Q')
        storeAction.setStatusTip('退出系统')
        storeAction.triggered.connect(self.close)

        sellerAction = QAction(QIcon('hezuohuoban6.jpg'), '销售管理', self)
        sellerAction.setShortcut('Ctrl+Q')
        sellerAction.setStatusTip('退出系统')
        sellerAction.triggered.connect(self.close)

        customerAction = QAction(QIcon('hezuohuoban5.jpg'), '客户管理', self)
        customerAction.setShortcut('Ctrl+Q')
        customerAction.setStatusTip('退出系统')
        customerAction.triggered.connect(self.close)

        tranceAction = QAction(QIcon('wuliu4.jpg'), '物流管理', self)
        tranceAction.setShortcut('Ctrl+Q')
        tranceAction.setStatusTip('退出系统')
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
        #self.setGeometry(10, 10, 1800, 1400)
#        self.setWindowTitle('产品列表')
        self.show()


    def opensql(self):
        conn=pymysql.connect(host='192.168.3.128',port=3306,user='sun',passwd='123456',db='test_schema',charset='utf8mb4')
        #获取游标
        cursor=conn.cursor()
        #返回受影响的行数
        
        sums=cursor.execute("SELECT * FROM test_table")
        text=str('总共找到{}条记录').format(sums)
        self.lineEdit_3.setText(str(text))


    def tbl_show(self,pages=0):
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

    def closesql(self):
        cursor.close()
        #关闭数据库连接
        conn.close()

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

    def edit_it(self):
        row_num = -1
        for i in self.tableWidget.selectionModel().selection().indexes():
            row_num = i.row()
        print(row_num)
        reply = QMessageBox.question(self, '进入编辑',"编辑该行数据吗?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            edt.show()
#            edt.setupUi.show()
            edt.edit_row(row=i)
        else:
            return

    def generateMenu(self, pos):
    # 计算有多少条数据，默认-1,
        row_num = -1
        for i in self.tableWidget.selectionModel().selection().indexes():
            row_num = i.row()

    # 表格中只有两条有效数据，所以只在前两行支持右键弹出菜单
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

             if action == item2:
                 print('你选了选项二，当前行文字内容是：', self.tableWidget.item(row_num, 0).text(),
                      self.tableWidget.item(row_num, 1).text(),
                      self.tableWidget.item(row_num, 2).text())

             if action == item3:
                 print('你选了选项三，当前行文字内容是：', self.tableWidget.item(row_num, 0).text(),
                      self.tableWidget.item(row_num, 1).text(),
                      self.tableWidget.item(row_num, 2).text())
            
             return row_num

class edit_1(QMainWindow,Form1):
    
    def __init__(self):
        super(edit_1,self).__init__()

        self.initUI()

        self.setupUi(self)
#        self.opensql()
#        self.edit_it()
        self.center()
       
        
    def initUI(self):
        #定义主窗口位置和大小
        qr = self.frameGeometry()
        self.setGeometry(qr)
        self.setGeometry(10, 10, 820, 920)
#        self.setWindowTitle('产品列表')
#        self.show()

    def center(self):
        
        #获得窗口
        qr = self.frameGeometry()
        #获得屏幕中心点
        cp = QDesktopWidget().availableGeometry().center()
        #显示到屏幕中心
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def edit_row(self,row):
        print(row_sum)



        
        

        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    pts = Products()
    edt = edit_1()

    #显示的数据列表页
    pages=0
    #查找到的记录行数
    sums=pts.tbl_show()
    row_num=0

    #下拉菜单
    pts.action42.triggered.connect(pts.exit_menu)
    pts.action41.triggered.connect(pts.return_menu)

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
        

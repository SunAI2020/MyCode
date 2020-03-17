import sys
from PyQt5.QtWidgets import QWidget,QMainWindow, QTextEdit, QAction, QToolTip, QMessageBox,QDesktopWidget,QPushButton,QApplication,QTableWidget
from PyQt5.QtGui import QIcon,QFont
from PyQt5.QtCore import QCoreApplication
from sql_t import Ui_MainWindow 

class Products(QMainWindow,Ui_MainWindow):
    
    def __init__(self):
        super().__init__()
        
        self.initUI()
        self.center()
#        self.initTBL()
        
        
    def initUI(self):
        #定义程序图标
        self.setWindowIcon(QIcon('chanpin13.gif'))

        #这种静态的方法设置一个用于显示工具提示的字体。我们使用16px滑体字体。
        QToolTip.setFont(QFont('SansSerif', 16))
        
        #创建一个提示，我们称之为settooltip()方法。我们可以使用丰富的文本格式
        self.setToolTip('This is a <b>QWidget</b> widget')

#        #文本编辑
#        textEdit = QTextEdit()
#        self.setCentralWidget(textEdit)
        
        #创建一个PushButton并为他设置一个tooltip
        qbtn = QPushButton('Quit', self)
        qbtn.setToolTip('This is a <b>QUIT</b> widget')
        qbtn.clicked.connect(QCoreApplication.instance().quit)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(250, 450)
        #btn.sizeHint()显示默认尺寸
        qbtn.resize(qbtn.sizeHint())
        
        #移动窗口的位置
        qbtn.move(250,270)
        
        btn1 = QPushButton("测试按钮1", self)
        btn1.setToolTip('这是测试按钮1')
        btn1.move(250, 150)
 
        btn2 = QPushButton("测试按钮2", self)
        btn2.setToolTip('这是测试按钮2')
        btn2.move(250, 350)
      
        btn1.clicked.connect(self.buttonClicked)            
        btn2.clicked.connect(self.buttonClicked)

        self.statusBar()

        #定义动作
        homeAction = QAction(QIcon('home.jpg'), '主页', self)
        homeAction.setShortcut('Ctrl+H')
        homeAction.setStatusTip('返回主页')
        homeAction.triggered.connect(self.close)

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

        #定义下拉菜单
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&文件')
        fileMenu.addAction(openAction)
        fileMenu.addAction(saveAction)
        fileMenu.addAction(exitAction)

        EditMenu = menubar.addMenu('&编辑')
        EditMenu.addAction(editAction)

        HelpMenu = menubar.addMenu('&帮助')
        HelpMenu.addAction(helpAction)

        #定义工具条
        toolbar = self.addToolBar('主页')
        toolbar.addAction(homeAction)
        toolbar = self.addToolBar('编辑')
        toolbar.addAction(editAction)
        toolbar = self.addToolBar('保存')
        toolbar.addAction(saveAction)
        toolbar = self.addToolBar('打印')
        toolbar.addAction(printAction)
        toolbar = self.addToolBar('退出')
        toolbar.addAction(exitAction)

        #定义主窗口位置和大小 
        self.setGeometry(100, 100, 1000, 650)
        self.setWindowTitle('产品列表')
        self.show()

    def buttonClicked(self):
      
        sender = self.sender()
        self.statusBar().showMessage(sender.text() + ' was pressed')
        
#    def initTBL(self):
#        #定义表格
#        tbl=QTableWidget()
#        tbl.setColumnCount(4)
#        tbl.setRowCount(5)
#        tbl.setColumnWidth(0, 90)
#        tbl.setColumnWidth(1, 190)
#        tbl.setColumnWidth(2, 95)
#        tbl.setColumnWidth(3, 95)
 #       tbl.setHorizontalHeaderLabels(sListHeader)
 #       tbl.setSectionResizeMode(QHeaderView:ResizeToContents)
 #       tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

#        tbl.setSortingEnabled(True)
        
#        tbl.setGeometry(100,100,500,500)
#        tbl.setWindowTitle('产品列表111')
#        tbl.show()

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


        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    ex = Products()
    
    sys.exit(app.exec_())
        

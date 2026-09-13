#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
员工考勤程序
功能：管理员工信息、记录考勤、生成统计报表
"""

import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime, date

class EmployeeAttendanceSystem:
    def __init__(self, data_file="attendance_data.json"):
        """初始化考勤系统"""
        self.data_file = data_file
        self.data = self.load_data()
    
    def load_data(self):
        """加载数据"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载数据失败: {e}")
                return self.get_default_data()
        else:
            return self.get_default_data()
    
    def get_default_data(self):
        """获取默认数据结构"""
        return {
            "employees": [],
            "attendance_records": []
        }
    
    def save_data(self):
        """保存数据"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存数据失败: {e}")
            return False
    
    # 员工管理
    def add_employee(self, employee):
        """添加员工"""
        # 生成员工ID
        if self.data["employees"]:
            max_id = max(emp["id"] for emp in self.data["employees"])
            employee["id"] = max_id + 1
        else:
            employee["id"] = 1
        
        self.data["employees"].append(employee)
        return self.save_data()
    
    def update_employee(self, employee_id, employee_data):
        """更新员工信息"""
        for i, emp in enumerate(self.data["employees"]):
            if emp["id"] == employee_id:
                self.data["employees"][i].update(employee_data)
                return self.save_data()
        return False
    
    def delete_employee(self, employee_id):
        """删除员工"""
        self.data["employees"] = [emp for emp in self.data["employees"] if emp["id"] != employee_id]
        # 同时删除该员工的考勤记录
        self.data["attendance_records"] = [record for record in self.data["attendance_records"] 
                                         if record["employee_id"] != employee_id]
        return self.save_data()
    
    def get_employee(self, employee_id):
        """获取员工信息"""
        for emp in self.data["employees"]:
            if emp["id"] == employee_id:
                return emp
        return None
    
    def get_all_employees(self):
        """获取所有员工"""
        return self.data["employees"]
    
    # 考勤管理
    def add_attendance_record(self, record):
        """添加考勤记录"""
        # 生成记录ID
        if self.data["attendance_records"]:
            max_id = max(record["id"] for record in self.data["attendance_records"])
            record["id"] = max_id + 1
        else:
            record["id"] = 1
        
        # 检查是否已有当天的考勤记录
        today = date.today().isoformat()
        existing_record = next((r for r in self.data["attendance_records"] 
                              if r["employee_id"] == record["employee_id"] 
                              and r["date"] == today), None)
        
        if existing_record:
            # 更新现有记录
            existing_record.update(record)
        else:
            # 添加新记录
            self.data["attendance_records"].append(record)
        
        return self.save_data()
    
    def get_attendance_records(self, employee_id=None, start_date=None, end_date=None):
        """获取考勤记录"""
        records = self.data["attendance_records"]
        
        if employee_id:
            records = [r for r in records if r["employee_id"] == employee_id]
        
        if start_date:
            records = [r for r in records if r["date"] >= start_date]
        
        if end_date:
            records = [r for r in records if r["date"] <= end_date]
        
        return records
    
    # 统计功能
    def get_attendance_stats(self, employee_id=None, start_date=None, end_date=None):
        """获取考勤统计"""
        records = self.get_attendance_records(employee_id, start_date, end_date)
        
        stats = {
            "total_days": len(records),
            "present": 0,
            "absent": 0,
            "late": 0,
            "leave": 0,
            "overtime": 0
        }
        
        for record in records:
            status = record.get("status", "")
            if status == "present":
                stats["present"] += 1
            elif status == "absent":
                stats["absent"] += 1
            elif status == "late":
                stats["late"] += 1
            elif status == "leave":
                stats["leave"] += 1
            
            if record.get("overtime", 0) > 0:
                stats["overtime"] += record["overtime"]
        
        return stats

class AttendanceGUI:
    def __init__(self, root):
        """初始化GUI"""
        self.root = root
        self.root.title("员工考勤系统")
        self.root.geometry("1200x800")
        
        # 初始化考勤系统
        self.system = EmployeeAttendanceSystem()
        
        # 创建界面
        self.create_widgets()
    
    def create_widgets(self):
        """创建GUI组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部标签页
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 员工管理标签页
        employee_frame = ttk.Frame(notebook)
        notebook.add(employee_frame, text="员工管理")
        
        # 考勤管理标签页
        attendance_frame = ttk.Frame(notebook)
        notebook.add(attendance_frame, text="考勤管理")
        
        # 统计报表标签页
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="统计报表")
        
        # 员工管理界面
        self.create_employee_tab(employee_frame)
        
        # 考勤管理界面
        self.create_attendance_tab(attendance_frame)
        
        # 统计报表界面
        self.create_stats_tab(stats_frame)
    
    def create_employee_tab(self, frame):
        """创建员工管理界面"""
        # 左侧员工列表
        left_frame = ttk.Frame(frame, width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        ttk.Label(left_frame, text="员工列表").pack(pady=5)
        
        # 员工列表树
        columns = ("id", "name", "department", "position")
        self.employee_tree = ttk.Treeview(left_frame, columns=columns, show="headings")
        
        for col in columns:
            self.employee_tree.heading(col, text=col)
            if col == "id":
                self.employee_tree.column(col, width=50)
            else:
                self.employee_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.employee_tree.yview)
        self.employee_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.employee_tree.pack(fill=tk.BOTH, expand=True)
        
        # 员工操作按钮
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="添加员工", command=self.add_employee).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="编辑员工", command=self.edit_employee).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除员工", command=self.delete_employee).pack(side=tk.LEFT, padx=5)
        
        # 右侧员工详情
        right_frame = ttk.Frame(frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ttk.Label(right_frame, text="员工详情").pack(pady=5)
        
        detail_frame = ttk.LabelFrame(right_frame, text="基本信息", padding="10")
        detail_frame.pack(fill=tk.X, pady=5)
        
        # 员工详情表单
        form_frame = ttk.Frame(detail_frame)
        form_frame.pack(fill=tk.X)
        
        ttk.Label(form_frame, text="姓名:", width=10).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.emp_name = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.emp_name, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="部门:", width=10).grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.emp_department = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.emp_department, width=30).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="职位:", width=10).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.emp_position = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.emp_position, width=30).grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="联系电话:", width=10).grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.emp_phone = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.emp_phone, width=30).grid(row=3, column=1, padx=5, pady=5)
        
        # 加载员工列表
        self.load_employees()
        
        # 绑定员工选择事件
        self.employee_tree.bind("<<TreeviewSelect>>", self.on_employee_select)
    
    def create_attendance_tab(self, frame):
        """创建考勤管理界面"""
        # 顶部选择区域
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(top_frame, text="员工:", width=10).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.att_employee = tk.StringVar()
        self.employee_combobox = ttk.Combobox(top_frame, textvariable=self.att_employee, width=20)
        self.employee_combobox.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(top_frame, text="日期:", width=10).grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.att_date = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(top_frame, textvariable=self.att_date, width=15).grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Button(top_frame, text="获取记录", command=self.get_attendance_record).grid(row=0, column=4, padx=5, pady=5)
        
        # 考勤信息区域
        info_frame = ttk.LabelFrame(frame, text="考勤信息", padding="10")
        info_frame.pack(fill=tk.X, pady=5)
        
        form_frame = ttk.Frame(info_frame)
        form_frame.pack(fill=tk.X)
        
        ttk.Label(form_frame, text="状态:", width=10).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.att_status = tk.StringVar(value="present")
        status_values = ["present", "absent", "late", "leave"]
        ttk.Combobox(form_frame, textvariable=self.att_status, values=status_values, width=15).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="上班时间:", width=10).grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.att_check_in = tk.StringVar(value="09:00")
        ttk.Entry(form_frame, textvariable=self.att_check_in, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="下班时间:", width=10).grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        self.att_check_out = tk.StringVar(value="18:00")
        ttk.Entry(form_frame, textvariable=self.att_check_out, width=10).grid(row=1, column=3, padx=5, pady=5)
        
        ttk.Label(form_frame, text="加班小时:", width=10).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.att_overtime = tk.DoubleVar(value=0)
        ttk.Entry(form_frame, textvariable=self.att_overtime, width=10).grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="备注:", width=10).grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.att_note = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.att_note, width=50).grid(row=3, column=1, columnspan=3, padx=5, pady=5)
        
        # 操作按钮
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="保存考勤记录", command=self.save_attendance_record).pack(side=tk.LEFT, padx=5)
        
        # 考勤记录列表
        list_frame = ttk.LabelFrame(frame, text="考勤记录", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("date", "status", "check_in", "check_out", "overtime", "note")
        self.attendance_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        for col in columns:
            self.attendance_tree.heading(col, text=col)
            if col in ["date", "status"]:
                self.attendance_tree.column(col, width=100)
            elif col in ["check_in", "check_out"]:
                self.attendance_tree.column(col, width=80)
            elif col == "overtime":
                self.attendance_tree.column(col, width=80)
            else:
                self.attendance_tree.column(col, width=200)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.attendance_tree.yview)
        self.attendance_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.attendance_tree.pack(fill=tk.BOTH, expand=True)
        
        # 加载员工列表到下拉框
        self.load_employees_to_combobox()
    
    def create_stats_tab(self, frame):
        """创建统计报表界面"""
        # 顶部选择区域
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(top_frame, text="员工:", width=10).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.stats_employee = tk.StringVar()
        self.stats_employee_combobox = ttk.Combobox(top_frame, textvariable=self.stats_employee, width=20)
        self.stats_employee_combobox.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(top_frame, text="开始日期:", width=10).grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.stats_start_date = tk.StringVar(value=(date.today().replace(day=1)).isoformat())
        ttk.Entry(top_frame, textvariable=self.stats_start_date, width=15).grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Label(top_frame, text="结束日期:", width=10).grid(row=0, column=4, padx=5, pady=5, sticky=tk.W)
        self.stats_end_date = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(top_frame, textvariable=self.stats_end_date, width=15).grid(row=0, column=5, padx=5, pady=5)
        
        ttk.Button(top_frame, text="生成报表", command=self.generate_stats).grid(row=0, column=6, padx=5, pady=5)
        
        # 统计结果区域
        result_frame = ttk.LabelFrame(frame, text="统计结果", padding="10")
        result_frame.pack(fill=tk.X, pady=5)
        
        stats_grid = ttk.Frame(result_frame)
        stats_grid.pack(fill=tk.X)
        
        stats_labels = ["总天数", "出勤", "缺勤", "迟到", "请假", "加班小时"]
        self.stats_vars = {}
        
        for i, label in enumerate(stats_labels):
            ttk.Label(stats_grid, text=label + ":", width=10).grid(row=0, column=i*2, padx=5, pady=5, sticky=tk.W)
            var = tk.StringVar(value="0")
            self.stats_vars[label] = var
            ttk.Label(stats_grid, textvariable=var, width=10, relief=tk.SUNKEN).grid(row=0, column=i*2+1, padx=5, pady=5, sticky=tk.W)
        
        # 详细记录区域
        detail_frame = ttk.LabelFrame(frame, text="详细记录", padding="10")
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("date", "status", "check_in", "check_out", "overtime", "note")
        self.stats_tree = ttk.Treeview(detail_frame, columns=columns, show="headings")
        
        for col in columns:
            self.stats_tree.heading(col, text=col)
            if col in ["date", "status"]:
                self.stats_tree.column(col, width=100)
            elif col in ["check_in", "check_out"]:
                self.stats_tree.column(col, width=80)
            elif col == "overtime":
                self.stats_tree.column(col, width=80)
            else:
                self.stats_tree.column(col, width=200)
        
        scrollbar = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=self.stats_tree.yview)
        self.stats_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.stats_tree.pack(fill=tk.BOTH, expand=True)
        
        # 加载员工列表到下拉框
        self.load_employees_to_stats_combobox()
    
    # 员工管理方法
    def load_employees(self):
        """加载员工列表"""
        # 清空现有数据
        for item in self.employee_tree.get_children():
            self.employee_tree.delete(item)
        
        # 添加员工数据
        employees = self.system.get_all_employees()
        for emp in employees:
            self.employee_tree.insert("", tk.END, values=(emp["id"], emp["name"], emp["department"], emp["position"]))
    
    def on_employee_select(self, event):
        """员工选择事件"""
        selected_items = self.employee_tree.selection()
        if selected_items:
            item = selected_items[0]
            values = self.employee_tree.item(item, "values")
            employee_id = values[0]
            employee = self.system.get_employee(employee_id)
            if employee:
                self.emp_name.set(employee.get("name", ""))
                self.emp_department.set(employee.get("department", ""))
                self.emp_position.set(employee.get("position", ""))
                self.emp_phone.set(employee.get("phone", ""))
    
    def add_employee(self):
        """添加员工"""
        # 清空表单
        self.emp_name.set("")
        self.emp_department.set("")
        self.emp_position.set("")
        self.emp_phone.set("")
        
        # 创建添加员工对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("添加员工")
        dialog.geometry("400x300")
        
        # 表单框架
        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(form_frame, text="姓名:", width=10).grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=30).grid(row=0, column=1, padx=5, pady=10)
        
        ttk.Label(form_frame, text="部门:", width=10).grid(row=1, column=0, padx=5, pady=10, sticky=tk.W)
        dept_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=dept_var, width=30).grid(row=1, column=1, padx=5, pady=10)
        
        ttk.Label(form_frame, text="职位:", width=10).grid(row=2, column=0, padx=5, pady=10, sticky=tk.W)
        pos_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=pos_var, width=30).grid(row=2, column=1, padx=5, pady=10)
        
        ttk.Label(form_frame, text="联系电话:", width=10).grid(row=3, column=0, padx=5, pady=10, sticky=tk.W)
        phone_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=phone_var, width=30).grid(row=3, column=1, padx=5, pady=10)
        
        # 按钮框架
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, pady=10)
        
        def save_employee():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("错误", "姓名不能为空")
                return
            
            employee = {
                "name": name,
                "department": dept_var.get().strip(),
                "position": pos_var.get().strip(),
                "phone": phone_var.get().strip()
            }
            
            if self.system.add_employee(employee):
                messagebox.showinfo("成功", "员工添加成功")
                self.load_employees()
                self.load_employees_to_combobox()
                self.load_employees_to_stats_combobox()
                dialog.destroy()
            else:
                messagebox.showerror("错误", "员工添加失败")
        
        ttk.Button(button_frame, text="保存", command=save_employee).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def edit_employee(self):
        """编辑员工"""
        selected_items = self.employee_tree.selection()
        if not selected_items:
            messagebox.showerror("错误", "请选择要编辑的员工")
            return
        
        item = selected_items[0]
        values = self.employee_tree.item(item, "values")
        employee_id = values[0]
        employee = self.system.get_employee(employee_id)
        
        if not employee:
            messagebox.showerror("错误", "员工不存在")
            return
        
        # 创建编辑员工对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑员工")
        dialog.geometry("400x300")
        
        # 表单框架
        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(form_frame, text="姓名:", width=10).grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        name_var = tk.StringVar(value=employee.get("name", ""))
        ttk.Entry(form_frame, textvariable=name_var, width=30).grid(row=0, column=1, padx=5, pady=10)
        
        ttk.Label(form_frame, text="部门:", width=10).grid(row=1, column=0, padx=5, pady=10, sticky=tk.W)
        dept_var = tk.StringVar(value=employee.get("department", ""))
        ttk.Entry(form_frame, textvariable=dept_var, width=30).grid(row=1, column=1, padx=5, pady=10)
        
        ttk.Label(form_frame, text="职位:", width=10).grid(row=2, column=0, padx=5, pady=10, sticky=tk.W)
        pos_var = tk.StringVar(value=employee.get("position", ""))
        ttk.Entry(form_frame, textvariable=pos_var, width=30).grid(row=2, column=1, padx=5, pady=10)
        
        ttk.Label(form_frame, text="联系电话:", width=10).grid(row=3, column=0, padx=5, pady=10, sticky=tk.W)
        phone_var = tk.StringVar(value=employee.get("phone", ""))
        ttk.Entry(form_frame, textvariable=phone_var, width=30).grid(row=3, column=1, padx=5, pady=10)
        
        # 按钮框架
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, pady=10)
        
        def save_employee():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("错误", "姓名不能为空")
                return
            
            employee_data = {
                "name": name,
                "department": dept_var.get().strip(),
                "position": pos_var.get().strip(),
                "phone": phone_var.get().strip()
            }
            
            if self.system.update_employee(employee_id, employee_data):
                messagebox.showinfo("成功", "员工更新成功")
                self.load_employees()
                self.load_employees_to_combobox()
                self.load_employees_to_stats_combobox()
                dialog.destroy()
            else:
                messagebox.showerror("错误", "员工更新失败")
        
        ttk.Button(button_frame, text="保存", command=save_employee).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def delete_employee(self):
        """删除员工"""
        selected_items = self.employee_tree.selection()
        if not selected_items:
            messagebox.showerror("错误", "请选择要删除的员工")
            return
        
        if messagebox.askyesno("确认", "确定要删除所选员工吗？"):
            item = selected_items[0]
            values = self.employee_tree.item(item, "values")
            employee_id = values[0]
            
            if self.system.delete_employee(employee_id):
                messagebox.showinfo("成功", "员工删除成功")
                self.load_employees()
                self.load_employees_to_combobox()
                self.load_employees_to_stats_combobox()
            else:
                messagebox.showerror("错误", "员工删除失败")
    
    # 考勤管理方法
    def load_employees_to_combobox(self):
        """加载员工列表到下拉框"""
        employees = self.system.get_all_employees()
        employee_names = [f"{emp['id']} - {emp['name']}" for emp in employees]
        self.employee_combobox['values'] = employee_names
        if employee_names:
            self.employee_combobox.current(0)
    
    def get_attendance_record(self):
        """获取考勤记录"""
        # 解析员工ID
        employee_text = self.att_employee.get()
        if not employee_text:
            messagebox.showerror("错误", "请选择员工")
            return
        
        employee_id = int(employee_text.split(" - ")[0])
        att_date = self.att_date.get()
        
        # 获取记录
        records = self.system.get_attendance_records(employee_id, att_date, att_date)
        if records:
            record = records[0]
            self.att_status.set(record.get("status", "present"))
            self.att_check_in.set(record.get("check_in", "09:00"))
            self.att_check_out.set(record.get("check_out", "18:00"))
            self.att_overtime.set(record.get("overtime", 0))
            self.att_note.set(record.get("note", ""))
        else:
            # 重置表单
            self.att_status.set("present")
            self.att_check_in.set("09:00")
            self.att_check_out.set("18:00")
            self.att_overtime.set(0)
            self.att_note.set("")
        
        # 加载该员工的所有考勤记录
        self.load_attendance_records(employee_id)
    
    def load_attendance_records(self, employee_id):
        """加载考勤记录"""
        # 清空现有数据
        for item in self.attendance_tree.get_children():
            self.attendance_tree.delete(item)
        
        # 添加记录数据
        records = self.system.get_attendance_records(employee_id)
        for record in sorted(records, key=lambda x: x["date"], reverse=True):
            self.attendance_tree.insert("", tk.END, values=(
                record.get("date", ""),
                record.get("status", ""),
                record.get("check_in", ""),
                record.get("check_out", ""),
                record.get("overtime", 0),
                record.get("note", "")
            ))
    
    def save_attendance_record(self):
        """保存考勤记录"""
        # 解析员工ID
        employee_text = self.att_employee.get()
        if not employee_text:
            messagebox.showerror("错误", "请选择员工")
            return
        
        employee_id = int(employee_text.split(" - ")[0])
        att_date = self.att_date.get()
        
        record = {
            "employee_id": employee_id,
            "date": att_date,
            "status": self.att_status.get(),
            "check_in": self.att_check_in.get(),
            "check_out": self.att_check_out.get(),
            "overtime": self.att_overtime.get(),
            "note": self.att_note.get()
        }
        
        if self.system.add_attendance_record(record):
            messagebox.showinfo("成功", "考勤记录保存成功")
            self.load_attendance_records(employee_id)
        else:
            messagebox.showerror("错误", "考勤记录保存失败")
    
    # 统计报表方法
    def load_employees_to_stats_combobox(self):
        """加载员工列表到统计下拉框"""
        employees = self.system.get_all_employees()
        employee_names = [f"{emp['id']} - {emp['name']}" for emp in employees]
        self.stats_employee_combobox['values'] = employee_names
        if employee_names:
            self.stats_employee_combobox.current(0)
    
    def generate_stats(self):
        """生成统计报表"""
        # 解析员工ID
        employee_text = self.stats_employee.get()
        if not employee_text:
            messagebox.showerror("错误", "请选择员工")
            return
        
        employee_id = int(employee_text.split(" - ")[0])
        start_date = self.stats_start_date.get()
        end_date = self.stats_end_date.get()
        
        # 获取统计数据
        stats = self.system.get_attendance_stats(employee_id, start_date, end_date)
        
        # 更新统计结果
        self.stats_vars["总天数"].set(str(stats["total_days"]))
        self.stats_vars["出勤"].set(str(stats["present"]))
        self.stats_vars["缺勤"].set(str(stats["absent"]))
        self.stats_vars["迟到"].set(str(stats["late"]))
        self.stats_vars["请假"].set(str(stats["leave"]))
        self.stats_vars["加班小时"].set(str(stats["overtime"]))
        
        # 加载详细记录
        self.load_stats_records(employee_id, start_date, end_date)
    
    def load_stats_records(self, employee_id, start_date, end_date):
        """加载统计记录"""
        # 清空现有数据
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        
        # 添加记录数据
        records = self.system.get_attendance_records(employee_id, start_date, end_date)
        for record in sorted(records, key=lambda x: x["date"]):
            self.stats_tree.insert("", tk.END, values=(
                record.get("date", ""),
                record.get("status", ""),
                record.get("check_in", ""),
                record.get("check_out", ""),
                record.get("overtime", 0),
                record.get("note", "")
            ))

if __name__ == '__main__':
    root = tk.Tk()
    app = AttendanceGUI(root)
    root.mainloop()

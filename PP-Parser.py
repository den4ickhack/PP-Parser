#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import time
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import subprocess
import threading
import socket
from urllib.parse import urlencode, quote_plus
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import platform
import json
import sys

def get_data_path(filename):
    """Получить правильный путь к файлам данных в собранном приложении"""
    if getattr(sys, 'frozen', False):
        # Если приложение собрано - используем папку с exe
        base_path = os.path.dirname(sys.executable)
    else:
        # Если запуск из исходного кода - используем папку со скриптом
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, filename)

BASE_URL_SPEED = "https://servicedesk.service-online.live/traders-speed"
BASE_URL_ADS = "https://servicedesk.service-online.live/trader/ads"
BASE_URL_CONVERSION = "https://servicedesk.service-online.live/trader-conversions"
BASE_URL_DEALS = "https://servicedesk.service-online.live/trader/deals"
BASE_URL_BANK_STATEMENTS = "https://servicedesk.service-online.live/trader/bank-statements"
LINES_PER_PAGE = 20
DEBUGGING_PORT = 9222

def load_service_providers():
    try:
        file_path = get_data_path("service_providers.txt")
        
        if not os.path.exists(file_path):
            # Создаем файл, если он не существует
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("# Service Providers list\n")
            return {}
        
        providers = {}
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '|' in line and not line.startswith('#'):
                    sp_id, sp_name = line.split('|', 1)
                    providers[int(sp_id.strip())] = sp_name.strip()
        
        return providers
        
    except Exception as e:
        print(f"Не удалось загрузить список СП: {str(e)}")
        return {}

SERVICE_PROVIDERS = load_service_providers()

def load_employee_groups():
    try:
        file_path = get_data_path("employee_groups.json")
        
        if not os.path.exists(file_path):
            # Создаем файл с группами по умолчанию
            default_groups = {
                "Помаз-Браташ-Радионова-Журавский": [687, 612, 827, 963, 711, 767, 734, 768, 684, 239, 80, 81, 278, 910, 126, 964, 501, 314, 583, 956, 352, 947, 975, 337],
                "Сазыкина-Каменева-Радионова-Журавский": [315, 790, 894, 381, 976, 922, 778, 844, 949, 944, 659, 857, 376, 686, 801, 364, 593, 979],
                "Перетрухин-Цыганков-Мамедов-Рябенкова": [855, 742, 493, 376, 737, 552, 897, 394, 810, 784, 858, 785, 952, 924, 656, 972, 921, 966],
                "Талгат-Юхновец-Мамедов-Болотов": [898, 893, 899, 550, 737, 920, 833, 722, 806, 530, 800, 745, 888]
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_groups, f, ensure_ascii=False, indent=2)
            return default_groups
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    except Exception as e:
        print(f"Не удалось загрузить группы сотрудников: {str(e)}")
        return {}

def save_employee_groups(groups):
    try:
        file_path = get_data_path("employee_groups.json")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Не удалось сохранить группы сотрудников: {str(e)}")
        return False

EMPLOYEE_GROUPS = load_employee_groups()

def is_chrome_ready(port=DEBUGGING_PORT, host='127.0.0.1', timeout=1):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def get_or_connect_chrome():
    if not is_chrome_ready():
        return None
    
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUGGING_PORT}")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.current_url
        return driver
    except:
        return None

def open_folder(path):
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except:
        return False

def find_sp_in_table(soup, sp_name):
    table = soup.find('table')
    if not table:
        return sp_name
    
    all_text = table.get_text()
    
    for name_part in sp_name.split('|'):
        name_part = name_part.strip()
        if name_part and name_part in all_text:
            return name_part
    
    return sp_name

def find_total_row(rows, sp_name, actual_sp_name):
    total_patterns = [
        f"Total ({actual_sp_name})",
        f"Total ({sp_name})",
    ]
    
    for row in rows:
        cells = row.find_all(['td', 'th'])
        cell_texts = [cell.get_text(strip=True) for cell in cells]
        
        for pattern in total_patterns:
            if pattern in cell_texts:
                return cells
    return None

def create_deal_data(cells):
    invoice_element = cells[1].find('a')
    return {
        'id': cells[0].get_text(strip=True),
        'invoice': invoice_element.get_text(strip=True) if invoice_element else "N/A",
        'trader': cells[3].get_text(strip=True),
        'amount': cells[7].get_text(strip=True),
        'currency': cells[4].get_text(strip=True),
        'payment_system': cells[8].get_text(strip=True),
        'type': cells[9].get_text(strip=True),
        'status': cells[15].get_text(strip=True) if len(cells) > 15 else "Pending Arbitration",
        'created_at': cells[18].get_text(strip=True) if len(cells) > 18 else ""
    }

class ModernSPFrame(ttk.Frame):
    def __init__(self, parent, sp_vars, log_callback):
        super().__init__(parent)
        self.sp_vars = sp_vars
        self.log_callback = log_callback
        self.all_sp_ids = list(SERVICE_PROVIDERS.keys())
        self.filtered_sp_ids = self.all_sp_ids.copy()
        
        self.name_filter_var = tk.StringVar()
        self.employee_group_var = tk.StringVar(value="Все группы")
        
        self.filter_update_job = None
        
        self.setup_ui()
        self.setup_filter_bindings()
    
    def setup_ui(self):
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        filter_frame = ttk.LabelFrame(main_container, text="🔍 Фильтры", padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        filter_row = ttk.Frame(filter_frame)
        filter_row.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_row, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        self.name_entry = ttk.Entry(filter_row, textvariable=self.name_filter_var, width=20)
        self.name_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(filter_row, text="Группа:").pack(side=tk.LEFT, padx=(0, 5))
        employee_groups = ["Все группы"] + list(EMPLOYEE_GROUPS.keys())
        self.employee_combo = ttk.Combobox(filter_row, textvariable=self.employee_group_var, 
                                     values=employee_groups, width=20, state="readonly")
        self.employee_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(filter_row, text="🧹 Сбросить", 
                  command=self.clear_filters).pack(side=tk.LEFT, padx=(0, 10))
        
        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(control_frame, text="✅ Выбрать все", 
                  command=self.select_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(control_frame, text="❌ Снять все", 
                  command=self.deselect_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(control_frame, text="⭐ Выбрать отфильтрованные", 
                  command=self.select_filtered).pack(side=tk.LEFT, padx=(0, 5))
        
        # Информация о количестве СП перенесена в эту строку
        self.filter_info_var = tk.StringVar(value=f"Всего СП: {len(self.all_sp_ids)}")
        ttk.Label(control_frame, textvariable=self.filter_info_var, 
                 font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=(0, 10))
        
        sp_display_frame = ttk.LabelFrame(main_container, text="Service Providers", padding=5)
        sp_display_frame.pack(fill=tk.BOTH, expand=True)
        
        self.setup_sp_treeview(sp_display_frame)
    
    def setup_filter_bindings(self):
        self.name_entry.bind('<KeyRelease>', self.schedule_filter_update)
        self.employee_combo.bind('<<ComboboxSelected>>', self.schedule_filter_update)
    
    def setup_sp_treeview(self, parent):
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("selected", "id", "name", "group")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=12)
        
        self.tree.heading("selected", text="✅")
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Название СП")
        self.tree.heading("group", text="Группа")
        
        self.tree.column("selected", width=60, anchor="center")
        self.tree.column("id", width=50, anchor="center")
        self.tree.column("name", width=250, anchor="w")
        self.tree.column("group", width=150, anchor="w")
        
        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        self.tree.bind('<Button-1>', self.on_tree_click)
        
        self.refresh_tree()
    
    def get_sp_group(self, sp_id):
        # Ищем СП во всех группах
        for group, sp_ids in EMPLOYEE_GROUPS.items():
            if sp_id in sp_ids:
                return group
        return "Не распределен"
    
    def should_show_sp(self, sp_id, sp_name, filters):
        name_match = not filters['name'] or filters['name'] in sp_name.lower()
        
        group_match = True
        if filters['employee_group'] != "Все группы":
            sp_group = self.get_sp_group(sp_id)
            group_match = sp_group == filters['employee_group']
        
        return all([name_match, group_match])
    
    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        filters = {
            'name': self.name_filter_var.get().lower().strip(),
            'employee_group': self.employee_group_var.get()
        }
        
        self.filtered_sp_ids = []
        visible_count = 0
        selected_count = 0
        
        for sp_id, sp_name in SERVICE_PROVIDERS.items():
            should_show = self.should_show_sp(sp_id, sp_name, filters)
            is_selected = self.sp_vars[sp_id].get()
            
            if is_selected:
                selected_count += 1
            
            if should_show:
                group = self.get_sp_group(sp_id)
                selected_mark = "✅ ВЫБРАН" if is_selected else "☐ Выбрать"
                self.tree.insert("", "end", iid=str(sp_id), 
                               values=(selected_mark, sp_id, sp_name, group))
                self.filtered_sp_ids.append(sp_id)
                visible_count += 1
        
        self.filter_info_var.set(f"Показано: {visible_count} из {len(self.all_sp_ids)} | Выбрано: {selected_count}")
        
        if visible_count == 0:
            self.log_callback("ℹ️ Нет СП, соответствующих фильтрам")
    
    def update_tree_item(self, item_id, is_selected):
        if self.tree.exists(str(item_id)):
            selected_mark = "✅ ВЫБРАН" if is_selected else "☐ Выбрать"
            values = self.tree.item(str(item_id))['values']
            self.tree.item(str(item_id), values=(selected_mark, values[1], values[2], values[3]))
    
    def on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        
        if item:
            sp_id = int(item)
            current_state = self.sp_vars[sp_id].get()
            self.sp_vars[sp_id].set(not current_state)
            self.update_tree_item(sp_id, not current_state)
            self.update_selection_counter()
    
    def update_selection_counter(self):
        selected_count = sum(1 for var in self.sp_vars.values() if var.get())
        visible_count = len(self.filtered_sp_ids)
        self.filter_info_var.set(f"Показано: {visible_count} из {len(self.all_sp_ids)} | Выбрано: {selected_count}")
    
    def schedule_filter_update(self, event=None):
        if self.filter_update_job:
            self.after_cancel(self.filter_update_job)
        self.filter_update_job = self.after(300, self.refresh_tree)
    
    def clear_filters(self):
        self.name_filter_var.set("")
        self.employee_group_var.set("Все группы")
        self.refresh_tree()
        self.log_callback("🧹 Все фильтры сброшены")
    
    def select_all(self):
        for var in self.sp_vars.values():
            var.set(True)
        self.refresh_tree()
        self.log_callback("✅ Выбраны все СП")
    
    def deselect_all(self):
        for var in self.sp_vars.values():
            var.set(False)
        self.refresh_tree()
        self.log_callback("❌ Выбор снят со всех СП")
    
    def select_filtered(self):
        for var in self.sp_vars.values():
            var.set(False)
        
        for sp_id in self.filtered_sp_ids:
            self.sp_vars[sp_id].set(True)
        
        self.refresh_tree()
        self.log_callback(f"⭐ Выбраны отфильтрованные СП: {len(self.filtered_sp_ids)}")
    
    def update_service_providers(self, new_service_providers, new_sp_vars):
        """Обновить список СП в интерфейсе"""
        self.sp_vars = new_sp_vars
        self.all_sp_ids = list(new_service_providers.keys())
        self.filtered_sp_ids = self.all_sp_ids.copy()
        self.refresh_tree()
        self.log_callback(f"🔄 Список СП обновлен: {len(self.all_sp_ids)} providers")
    
    def refresh_groups_display(self):
        """Обновить отображение групп для всех СП"""
        # Обновляем значения в комбобоксе фильтра
        employee_groups = ["Все группы"] + list(EMPLOYEE_GROUPS.keys())
        self.employee_combo['values'] = employee_groups
        
        # Обновляем дерево
        self.refresh_tree()

class TimeFrame(ttk.LabelFrame):
    def __init__(self, parent, log_callback):
        super().__init__(parent, text="🕒 Временные промежутки", padding=10)
        self.log_callback = log_callback
        
        now = datetime.datetime.now()
        
        self.speed_from_var = tk.StringVar(value=self.calculate_from_time(now, 'speed').strftime("%Y-%m-%d %H:%M:%S"))
        self.speed_to_var = tk.StringVar(value="")
        self.conversion_from_var = tk.StringVar(value=self.calculate_from_time(now, 'conversion').strftime("%Y-%m-%d %H:%M:%S"))
        self.conversion_to_var = tk.StringVar(value="")
        self.arbitrage_from_var = tk.StringVar(value=self.calculate_from_time(now, 'arbitrage').strftime("%Y-%m-%d %H:%M:%S"))
        self.arbitrage_to_var = tk.StringVar(value="")
        
        self.setup_ui()
    
    def calculate_from_time(self, now: datetime.datetime, time_type: str) -> datetime.datetime:
        if time_type == 'arbitrage':
            return (now - datetime.timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        if now.hour < 3:
            return (now - datetime.timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
        elif now.hour < 8:
            return (now - datetime.timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
        elif now.hour < 20:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return now.replace(hour=15, minute=0, second=0, microsecond=0)
    
    def setup_ui(self):
        time_grid = ttk.Frame(self)
        time_grid.pack(fill=tk.X)
        
        # Заголовки
        ttk.Label(time_grid, text="", width=8).grid(row=0, column=0, padx=2, pady=2)
        ttk.Label(time_grid, text="От", width=15).grid(row=0, column=1, padx=2, pady=2)
        ttk.Label(time_grid, text="До", width=15).grid(row=0, column=2, padx=2, pady=2)
        ttk.Label(time_grid, text="", width=10).grid(row=0, column=3, padx=2, pady=2)  # Пустая колонка для кнопок
        
        # Скорость
        ttk.Label(time_grid, text="Скорость:").grid(row=1, column=0, padx=2, pady=2, sticky=tk.W)
        ttk.Entry(time_grid, textvariable=self.speed_from_var, width=15).grid(row=1, column=1, padx=2, pady=2)
        ttk.Entry(time_grid, textvariable=self.speed_to_var, width=15).grid(row=1, column=2, padx=2, pady=2)
        
        # Конверсия
        ttk.Label(time_grid, text="Конверсия:").grid(row=2, column=0, padx=2, pady=2, sticky=tk.W)
        ttk.Entry(time_grid, textvariable=self.conversion_from_var, width=15).grid(row=2, column=1, padx=2, pady=2)
        ttk.Entry(time_grid, textvariable=self.conversion_to_var, width=15).grid(row=2, column=2, padx=2, pady=2)
        
        # Арбитражи
        ttk.Label(time_grid, text="Арбитражи:").grid(row=3, column=0, padx=2, pady=2, sticky=tk.W)
        ttk.Entry(time_grid, textvariable=self.arbitrage_from_var, width=15).grid(row=3, column=1, padx=2, pady=2)
        ttk.Entry(time_grid, textvariable=self.arbitrage_to_var, width=15).grid(row=3, column=2, padx=2, pady=2)
        
        # Кнопки управления временем - теперь в той же строке что и поля
        button_frame = ttk.Frame(time_grid)
        button_frame.grid(row=1, column=3, rowspan=3, padx=10, pady=2, sticky=tk.N)
        
        ttk.Button(button_frame, text="🔄 Сбросить время", command=self.reset_time).pack(side=tk.TOP, pady=(0, 5))
        ttk.Button(button_frame, text="⏰ Текущее время", command=self.set_current_time).pack(side=tk.TOP)
    
    def reset_time(self):
        now = datetime.datetime.now()
        
        self.speed_from_var.set(self.calculate_from_time(now, 'speed').strftime("%Y-%m-%d %H:%M:%S"))
        self.speed_to_var.set("")
        self.conversion_from_var.set(self.calculate_from_time(now, 'conversion').strftime("%Y-%m-%d %H:%M:%S"))
        self.conversion_to_var.set("")
        self.arbitrage_from_var.set(self.calculate_from_time(now, 'arbitrage').strftime("%Y-%m-%d %H:%M:%S"))
        self.arbitrage_to_var.set("")
        
        self.log_callback("🕒 Время сброшено к оригинальным значениям")
    
    def set_current_time(self):
        now = datetime.datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        if not self.speed_to_var.get():
            self.speed_to_var.set(current_time)
        if not self.conversion_to_var.get():
            self.conversion_to_var.set(current_time)
        if not self.arbitrage_to_var.get():
            self.arbitrage_to_var.set(current_time)
        
        self.log_callback(f"⏰ Установлено текущее время: {current_time}")

class GroupManagementFrame(ttk.LabelFrame):
    def __init__(self, parent, log_callback, main_app):
        super().__init__(parent, text="👥 Управление группами", padding=10)
        self.log_callback = log_callback
        self.main_app = main_app
        self.setup_ui()
    
    def setup_ui(self):
        # Верхняя панель с управлением группами
        group_control_frame = ttk.Frame(self)
        group_control_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(group_control_frame, text="Группа:").pack(side=tk.LEFT, padx=(0, 5))
        self.group_var = tk.StringVar()
        self.group_combo = ttk.Combobox(group_control_frame, textvariable=self.group_var, 
                                       values=list(EMPLOYEE_GROUPS.keys()), width=25, state="readonly")
        self.group_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.group_combo.bind('<<ComboboxSelected>>', self.on_group_selected)
        
        ttk.Button(group_control_frame, text="➕ Новая", 
                  command=self.add_new_group).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(group_control_frame, text="✏️ Переим.", 
                  command=self.rename_group).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(group_control_frame, text="🗑️ Удалить", 
                  command=self.delete_group).pack(side=tk.LEFT, padx=(0, 5))
        
        # Панель управления СП в группе
        sp_management_frame = ttk.Frame(self)
        sp_management_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(sp_management_frame, text="➕ Назначить группу", 
                  command=self.assign_selected_to_group).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(sp_management_frame, text="🧹 Убрать из групп", 
                  command=self.remove_from_all_groups).pack(side=tk.LEFT, padx=(0, 10))
    
    def on_group_selected(self, event=None):
        pass
    
    def add_new_group(self):
        new_name = simpledialog.askstring("Новая группа", "Введите название новой группы:")
        if not new_name:
            return
        
        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("Внимание", "Название группы не может быть пустым!")
            return
        
        if new_name in EMPLOYEE_GROUPS:
            messagebox.showwarning("Внимание", "Группа с таким названием уже существует!")
            return
        
        EMPLOYEE_GROUPS[new_name] = []
        if save_employee_groups(EMPLOYEE_GROUPS):
            self.group_combo['values'] = list(EMPLOYEE_GROUPS.keys())
            self.group_var.set(new_name)
            # Обновляем комбобокс в основном интерфейсе
            self.main_app.sp_frame.refresh_groups_display()
            # Принудительно обновляем дерево
            self.main_app.sp_frame.refresh_tree()
            self.log_callback(f"✅ Добавлена новая группа: {new_name}")
    
    def rename_group(self):
        old_name = self.group_var.get()
        if not old_name:
            messagebox.showwarning("Внимание", "Выберите группу для переименования!")
            return
        
        new_name = simpledialog.askstring("Переименование группы", 
                                         f"Введите новое название для группы '{old_name}':",
                                         initialvalue=old_name)
        if not new_name:
            return
        
        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("Внимание", "Название группы не может быть пустым!")
            return
        
        if new_name in EMPLOYEE_GROUPS:
            messagebox.showwarning("Внимание", "Группа с таким названием уже существует!")
            return
        
        EMPLOYEE_GROUPS[new_name] = EMPLOYEE_GROUPS.pop(old_name)
        if save_employee_groups(EMPLOYEE_GROUPS):
            self.group_combo['values'] = list(EMPLOYEE_GROUPS.keys())
            self.group_var.set(new_name)
            # Обновляем комбобокс в основном интерфейсе
            self.main_app.sp_frame.refresh_groups_display()
            # Принудительно обновляем дерево
            self.main_app.sp_frame.refresh_tree()
            self.log_callback(f"✏️ Группа переименована: {old_name} -> {new_name}")
    
    def delete_group(self):
        group_name = self.group_var.get()
        if not group_name:
            messagebox.showwarning("Внимание", "Выберите группу для удаления!")
            return
        
        result = messagebox.askyesno("Подтверждение", 
                                   f"Вы уверены, что хотите удалить группу '{group_name}'?")
        if not result:
            return
        
        # Сохраняем количество СП в группе для лога
        sp_count = len(EMPLOYEE_GROUPS[group_name])
        
        del EMPLOYEE_GROUPS[group_name]
        if save_employee_groups(EMPLOYEE_GROUPS):
            self.group_combo['values'] = list(EMPLOYEE_GROUPS.keys())
            self.group_var.set("")
            # Обновляем комбобокс в основном интерфейсе
            self.main_app.sp_frame.refresh_groups_display()
            # Принудительно обновляем дерево
            self.main_app.sp_frame.refresh_tree()
            self.log_callback(f"🗑️ Удалена группа '{group_name}' с {sp_count} СП")
    
    def assign_selected_to_group(self):
        """Назначить выбранные СП в указанную группу (удаляя из других групп)"""
        group_name = self.group_var.get()
        if not group_name:
            messagebox.showwarning("Внимание", "Выберите группу!")
            return
        
        if self.main_app and hasattr(self.main_app, 'get_selected_sps'):
            selected_sps = self.main_app.get_selected_sps()
            if not selected_sps:
                messagebox.showwarning("Внимание", "Не выбран ни один СП!")
                return
            
            assigned_count = 0
            moved_count = 0
            
            for sp_id in selected_sps.keys():
                # Проверяем, в какой группе сейчас СП
                current_group = None
                for group, sp_ids in EMPLOYEE_GROUPS.items():
                    if sp_id in sp_ids:
                        current_group = group
                        break
                
                # Удаляем СП из всех других групп
                for other_group_name, sp_ids in EMPLOYEE_GROUPS.items():
                    if other_group_name != group_name and sp_id in sp_ids:
                        EMPLOYEE_GROUPS[other_group_name].remove(sp_id)
                
                # Добавляем СП в целевую группу, если его там еще нет
                if sp_id not in EMPLOYEE_GROUPS[group_name]:
                    EMPLOYEE_GROUPS[group_name].append(sp_id)
                    if current_group and current_group != group_name:
                        moved_count += 1
                    else:
                        assigned_count += 1
            
            # Всегда сохраняем и обновляем интерфейс, даже если ничего не изменилось
            if save_employee_groups(EMPLOYEE_GROUPS):
                # ОБНОВЛЯЕМ ОТОБРАЖЕНИЕ ГРУПП В ОСНОВНОМ ИНТЕРФЕЙСЕ
                self.main_app.sp_frame.refresh_groups_display()
                # ПРИНУДИТЕЛЬНО ОБНОВЛЯЕМ ДЕРЕВО
                self.main_app.sp_frame.refresh_tree()
                
                message_parts = []
                if assigned_count > 0:
                    message_parts.append(f"добавлено {assigned_count}")
                if moved_count > 0:
                    message_parts.append(f"перемещено {moved_count}")
                
                if assigned_count > 0 or moved_count > 0:
                    self.log_callback(f"✅ {', '.join(message_parts)} СП в группу '{group_name}'")
                else:
                    self.log_callback(f"ℹ️ Все выбранные СП уже находятся в группе '{group_name}'")
        else:
            messagebox.showerror("Ошибка", "Не удалось получить доступ к списку выбранных СП!")
    
    def remove_from_all_groups(self):
        """Убрать выбранные СП из всех групп"""
        if self.main_app and hasattr(self.main_app, 'get_selected_sps'):
            selected_sps = self.main_app.get_selected_sps()
            if not selected_sps:
                messagebox.showwarning("Внимание", "Не выбран ни один СП!")
                return
            
            removed_count = 0
            
            for sp_id in selected_sps.keys():
                # Удаляем СП из всех групп
                for group_name, sp_ids in EMPLOYEE_GROUPS.items():
                    if sp_id in sp_ids:
                        EMPLOYEE_GROUPS[group_name].remove(sp_id)
                        removed_count += 1
            
            # Всегда сохраняем и обновляем интерфейс
            if save_employee_groups(EMPLOYEE_GROUPS):
                # ОБНОВЛЯЕМ ОТОБРАЖЕНИЕ ГРУПП В ОСНОВНОМ ИНТЕРФЕЙСЕ
                self.main_app.sp_frame.refresh_groups_display()
                # ПРИНУДИТЕЛЬНО ОБНОВЛЯЕМ ДЕРЕВО
                self.main_app.sp_frame.refresh_tree()
                
                if removed_count > 0:
                    self.log_callback(f"🧹 Убрано {removed_count} СП из всех групп")
                else:
                    self.log_callback("ℹ️ Выбранные СП не состоят ни в одной группе")
        else:
            messagebox.showerror("Ошибка", "Не удалось получить доступ к списку выбранных СП!")

class PayportApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Payport SP Parser v10.8")
        self.root.geometry("1400x900")
        self.root.minsize(1000, 700)
        
        # Сначала инициализируем основные переменные
        self.sp_vars = {sp_id: tk.BooleanVar(value=True) for sp_id in SERVICE_PROVIDERS.keys()}
        self.auto_no_incidents_var = tk.BooleanVar(value=True)
        
        self.stop_processing = False
        self.processing_thread = None
        self.driver = None
        self.chrome_process = None
        self.last_reports_folder = None
        
        # Инициализируем log_text как None
        self.log_text = None
        
        self.setup_ui()
        self.setup_sp_management()
    
    def setup_ui(self):
        style = ttk.Style()
        style.configure("TButton", padding=6)
        style.configure("TLabelframe", padding=10)
        style.configure("TLabelframe.Label", font=("Arial", 10, "bold"))
        
        # Создаем основной контейнер с прокруткой
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Создаем панель с вкладками вместо PanedWindow
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Левая вкладка - основные функции
        left_tab = ttk.Frame(notebook)
        notebook.add(left_tab, text="📊 Основные функции")
        
        # Правая вкладка - логи
        right_tab = ttk.Frame(notebook)
        notebook.add(right_tab, text="📝 Логи выполнения")
        
        # СНАЧАЛА настраиваем правую панель с логами
        self.setup_right_panel(right_tab)
        
        # ПОТОМ левую панель
        self.setup_left_panel(left_tab)
        
        # Настройка весов для масштабирования
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(0, weight=1)
        
    def setup_left_panel(self, parent):
        # Используем grid с весами для правильного масштабирования
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=0)  # Время
        parent.rowconfigure(1, weight=0)  # Управление СП и группы
        parent.rowconfigure(2, weight=1)  # СП получают наибольший вес
        parent.rowconfigure(3, weight=0)  # Управление обработкой
        
        # Временные промежутки - на самый верх
        self.time_frame = TimeFrame(parent, self.log)
        self.time_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # Блок управления СП и группами - рядом
        management_frame = ttk.Frame(parent)
        management_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        management_frame.columnconfigure(0, weight=1)
        management_frame.columnconfigure(1, weight=1)
        
        # Управление СП - слева
        self.sp_management_frame = ttk.LabelFrame(management_frame, text="🔧 Управление СП", padding=10)
        self.sp_management_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.setup_sp_management_ui()
        
        # Управление группами - справа (ПЕРЕДАЕМ self КАК main_app)
        self.group_frame = GroupManagementFrame(management_frame, self.log, self)
        self.group_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        
        # Список СП - под блоком управления
        self.sp_frame = ModernSPFrame(parent, self.sp_vars, self.log)
        self.sp_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        
        # Управление обработкой - внизу
        control_frame = ttk.LabelFrame(parent, text="🚀 Управление обработкой", padding=10)
        control_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        
        settings_frame = ttk.Frame(control_frame)
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.auto_no_incidents_cb = ttk.Checkbutton(
            settings_frame, 
            text="Автоматически заполнять 'Инцидентов не найдено' в пункте 6",
            variable=self.auto_no_incidents_var
        )
        self.auto_no_incidents_cb.pack(side=tk.LEFT)
        
        btn_container = ttk.Frame(control_frame)
        btn_container.pack(fill=tk.X)
        
        self.start_button = ttk.Button(btn_container, text="▶️ Запуск обработки", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_button = ttk.Button(btn_container, text="⏹️ Остановить", command=self.stop_processing_command, state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.open_folder_button = ttk.Button(btn_container, text="📁 Открыть папку отчетов", command=self.open_last_reports_folder, state="disabled")
        self.open_folder_button.pack(side=tk.LEFT)
        
        self.progress = ttk.Progressbar(control_frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(10, 0))
        
        self.status_var = tk.StringVar(value="Готов к работе")
        status_label = ttk.Label(control_frame, textvariable=self.status_var, font=("Arial", 9))
        status_label.pack(pady=(5, 0))
    
    def setup_right_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        
        log_frame = ttk.LabelFrame(parent, text="📝 Логи выполнения", padding=10)
        log_frame.grid(row=0, column=0, sticky="nsew")
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=60, font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        
        log_control = ttk.Frame(log_frame)
        log_control.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        
        ttk.Button(log_control, text="🧹 Очистить логи", command=self.clear_logs).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(log_control, text="💾 Сохранить логи", command=self.save_logs).pack(side=tk.LEFT)
    
    def setup_sp_management(self):
        """Настройка управления СП - теперь это отдельный метод для инициализации переменных"""
        pass
    
    def setup_sp_management_ui(self):
        """Настройка UI управления СП"""
        # Поля для ввода нового СП
        input_frame = ttk.Frame(self.sp_management_frame)
        input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(input_frame, text="ID:").pack(side=tk.LEFT, padx=(0, 5))
        self.new_sp_id_var = tk.StringVar()
        self.new_sp_id_entry = ttk.Entry(input_frame, textvariable=self.new_sp_id_var, width=8)
        self.new_sp_id_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(input_frame, text="Название:").pack(side=tk.LEFT, padx=(0, 5))
        self.new_sp_name_var = tk.StringVar()
        self.new_sp_name_entry = ttk.Entry(input_frame, textvariable=self.new_sp_name_var, width=30)
        self.new_sp_name_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Кнопки управления
        btn_frame = ttk.Frame(self.sp_management_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="➕ Добавить СП", command=self.add_service_provider).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="➖ Удалить выбранные", command=self.delete_selected_providers).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="🔄 Обновить из файла", command=self.reload_service_providers).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="📝 Открыть файл СП", command=self.open_service_providers_file).pack(side=tk.LEFT)
    
    def add_service_provider(self):
        """Добавить нового Service Provider"""
        sp_id = self.new_sp_id_var.get().strip()
        sp_name = self.new_sp_name_var.get().strip()
        
        if not sp_id or not sp_name:
            messagebox.showerror("Ошибка", "Заполните ID и название СП!")
            return
        
        try:
            sp_id_int = int(sp_id)
        except ValueError:
            messagebox.showerror("Ошибка", "ID должен быть числом!")
            return
        
        # Проверяем, существует ли уже такой ID
        if sp_id_int in SERVICE_PROVIDERS:
            result = messagebox.askyesno("Подтверждение", 
                                       f"СП с ID {sp_id_int} уже существует:\n{SERVICE_PROVIDERS[sp_id_int]}\nЗаменить?")
            if not result:
                return
        
        # Добавляем в файл
        try:
            file_path = get_data_path("service_providers.txt")
            
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{sp_id_int}|{sp_name}")
            
            # Обновляем глобальные переменные
            SERVICE_PROVIDERS[sp_id_int] = sp_name
            self.sp_vars[sp_id_int] = tk.BooleanVar(value=True)
            
            # Обновляем интерфейс
            self.sp_frame.update_service_providers(SERVICE_PROVIDERS, self.sp_vars)
            
            # Очищаем поля ввода
            self.new_sp_id_var.set("")
            self.new_sp_name_var.set("")
            
            self.log(f"✅ Добавлен СП: {sp_name} (ID {sp_id_int})")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось добавить СП: {str(e)}")
    
    def delete_selected_providers(self):
        """Удалить выбранные Service Providers"""
        selected_sps = self.get_selected_sps()
        if not selected_sps:
            messagebox.showwarning("Внимание", "Не выбран ни один Service Provider для удаления!")
            return
        
        sp_list = "\n".join([f"ID {sp_id}: {sp_name}" for sp_id, sp_name in selected_sps.items()])
        result = messagebox.askyesno("Подтверждение удаления", 
                                   f"Вы уверены, что хотите удалить следующие СП?\n\n{sp_list}")
        
        if not result:
            return
        
        try:
            file_path = get_data_path("service_providers.txt")
            
            # Читаем текущий файл
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Записываем обратно все строки, кроме удаляемых СП
            with open(file_path, 'w', encoding='utf-8') as f:
                for line in lines:
                    line = line.strip()
                    if line and '|' in line:
                        current_id, current_name = line.split('|', 1)
                        current_id = current_id.strip()
                        try:
                            if int(current_id) not in selected_sps:
                                f.write(line + '\n')
                        except ValueError:
                            f.write(line + '\n')
            
            # Обновляем глобальные переменные
            for sp_id in selected_sps.keys():
                if sp_id in SERVICE_PROVIDERS:
                    del SERVICE_PROVIDERS[sp_id]
                if sp_id in self.sp_vars:
                    del self.sp_vars[sp_id]
            
            # Обновляем интерфейс
            self.sp_frame.update_service_providers(SERVICE_PROVIDERS, self.sp_vars)
            
            self.log(f"✅ Удалено СП: {len(selected_sps)} шт.")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось удалить СП: {str(e)}")
    
    def reload_service_providers(self):
        """Перезагрузить список СП из файла"""
        global SERVICE_PROVIDERS
        
        try:
            new_providers = load_service_providers()
            if new_providers is not None:
                SERVICE_PROVIDERS = new_providers
                
                # Обновляем sp_vars
                self.sp_vars = {sp_id: tk.BooleanVar(value=True) for sp_id in SERVICE_PROVIDERS.keys()}
                
                # Обновляем интерфейс
                self.sp_frame.update_service_providers(SERVICE_PROVIDERS, self.sp_vars)
                
                self.log("✅ Список СП обновлен из файла")
            else:
                self.log("❌ Ошибка при загрузке списка СП")
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить список СП: {str(e)}")
    
    def open_service_providers_file(self):
        """Открыть файл service_providers.txt для редактирования"""
        try:
            file_path = get_data_path("service_providers.txt")
            
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
                
            self.log("📝 Открыт файл service_providers.txt для редактирования")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл: {str(e)}")
    
    def open_last_reports_folder(self):
        if self.last_reports_folder and os.path.exists(self.last_reports_folder):
            if open_folder(self.last_reports_folder):
                self.log(f"📁 Открыта папка с отчетами: {self.last_reports_folder}")
            else:
                self.log(f"❌ Не удалось открыть папку: {self.last_reports_folder}")
        else:
            # Ищем в папке REPORTS
            reports_main_folder = "REPORTS"
            if os.path.exists(reports_main_folder):
                reports_folders = [f for f in os.listdir(reports_main_folder) if f.startswith('reports_') and os.path.isdir(os.path.join(reports_main_folder, f))]
                if reports_folders:
                    latest_folder = max(reports_folders, key=lambda x: os.path.getctime(os.path.join(reports_main_folder, x)))
                    latest_folder_path = os.path.join(reports_main_folder, latest_folder)
                    if open_folder(latest_folder_path):
                        self.log(f"📁 Открыта последняя папка с отчетами: {latest_folder_path}")
                    else:
                        self.log(f"❌ Не удалось открыть папку: {latest_folder_path}")
                else:
                    messagebox.showwarning("Внимание", "В папке REPORTS не найдены отчеты!")
            else:
                messagebox.showwarning("Внимание", "Папка с отчетами не найдена!")
    
    def log(self, message):
        """Безопасный метод логирования с проверкой инициализации log_text"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        # Если log_text еще не инициализирован, выводим в консоль
        if not hasattr(self, 'log_text') or self.log_text is None:
            print(formatted_message, end='')
            return
        
        try:
            self.log_text.insert(tk.END, formatted_message)
            self.log_text.see(tk.END)
            self.root.update_idletasks()
        except Exception as e:
            # Если что-то пошло не так с log_text, выводим в консоль
            print(f"Ошибка записи в log_text: {e}")
            print(formatted_message, end='')
    
    def clear_logs(self):
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.delete(1.0, tk.END)
        self.log("🧹 Логи очищены")
    
    def save_logs(self):
        try:
            # Сохраняем логи в папку с программой
            filename = f"logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get(1.0, tk.END))
            self.log(f"💾 Логи сохранены в файл: {filename}")
        except Exception as e:
            self.log(f"❌ Ошибка сохранения логов: {str(e)}")
    
    def get_selected_sps(self):
        return {sp_id: SERVICE_PROVIDERS[sp_id] for sp_id, var in self.sp_vars.items() if var.get()}
    
    def get_time_params(self):
        return {
            'speed': {
                'from_date': self.time_frame.speed_from_var.get(),
                'to_date': self.time_frame.speed_to_var.get()
            },
            'conversion': {
                'from_date': self.time_frame.conversion_from_var.get(),
                'to_date': self.time_frame.conversion_to_var.get()
            },
            'arbitrage': {
                'from_date': self.time_frame.arbitrage_from_var.get(),
                'to_date': self.time_frame.arbitrage_to_var.get()
            }
        }
    
    def start_processing(self):
        if self.processing_thread and self.processing_thread.is_alive():
            messagebox.showwarning("Внимание", "Обработка уже запущена!")
            return
            
        selected_sps = self.get_selected_sps()
        if not selected_sps:
            messagebox.showwarning("Внимание", "Не выбран ни один Service Provider!")
            return
        
        time_params = self.get_time_params()
        
        try:
            for param_type, params in time_params.items():
                if params['from_date']:
                    datetime.datetime.strptime(params['from_date'], "%Y-%m-%d %H:%M:%S")
                if params['to_date']:
                    datetime.datetime.strptime(params['to_date'], "%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            messagebox.showerror("Ошибка", f"Неверный формат времени!\nИспользуйте: ГГГГ-ММ-ДД ЧЧ:ММ:СС\n\nОшибка: {str(e)}")
            return
        
        result = messagebox.askyesno("Подтверждение", f"Будет обработано {len(selected_sps)} Service Providers.\n\nПродолжить?")
        if not result:
            return
        
        self.stop_processing = False
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.open_folder_button.config(state="disabled")
        
        self.processing_thread = threading.Thread(target=self.process_sps, args=(selected_sps, time_params))
        self.processing_thread.daemon = True
        self.processing_thread.start()
    
    def stop_processing_command(self):
        self.stop_processing = True
        self.log("🛑 Запрошена остановка обработки...")
        self.update_status("Останавливается...")
    
    def update_progress(self, value):
        self.progress['value'] = value
        self.root.update_idletasks()
    
    def update_status(self, status):
        self.status_var.set(status)
        self.root.update_idletasks()
    
    def process_sps(self, selected_sps, time_params):
        try:
            self.log("=" * 60)
            self.log("🚀 Начинаем обработку выбранных СП")
            self.log(f"📋 Выбрано СП: {len(selected_sps)}")
            
            if not self.driver:
                self.update_status("Запуск Chrome...")
                self.driver, self.chrome_process = self.start_chrome_automatically()
                
                if not self.driver:
                    self.log("❌ Не удалось запустить Chrome")
                    self.reset_ui_after_processing()
                    return
                
                self.log("✅ Chrome успешно запущен")
            else:
                self.log("✅ Используем существующий браузер")
            
            now = datetime.datetime.now()
            
            # Создаем основную папку REPORTS если ее нет
            reports_main_folder = "REPORTS"
            os.makedirs(reports_main_folder, exist_ok=True)
            
            # Создаем подпапку для текущего запуска
            reports_folder = os.path.join(reports_main_folder, f"reports_{now.strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(reports_folder, exist_ok=True)
            
            original_dir = os.getcwd()
            os.chdir(reports_folder)
            self.last_reports_folder = os.getcwd()
            self.log(f"📁 Отчеты будут сохранены в папку: {reports_folder}")
            
            processed_count = 0
            total_count = len(selected_sps)
            
            for i, (sp_id, sp_name) in enumerate(selected_sps.items()):
                if self.stop_processing:
                    self.log("🛑 Обработка остановлена пользователем")
                    break
                    
                try:
                    self.update_status(f"Обработка {sp_name}... ({i+1}/{total_count})")
                    self.update_progress((i / total_count) * 100)
                    
                    self.log(f"\n🔗 Обрабатываем {sp_name} (ID {sp_id})")
                    
                    filename = process_single_sp_gui(
                        self.driver, 
                        sp_id, 
                        sp_name, 
                        time_params, 
                        self.log,
                        self.auto_no_incidents_var.get()
                    )
                    
                    processed_count += 1
                    self.log(f"✅ Завершена обработка {sp_name}")
                    
                except Exception as e:
                    self.log(f"❌ Ошибка при обработке {sp_name}: {str(e)}")
                    continue
            
            os.chdir(original_dir)
            
            self.update_progress(100)
            
            if self.stop_processing:
                self.update_status("Обработка остановлена")
                self.log(f"🛑 Обработка остановлена. Обработано: {processed_count}/{total_count}")
            else:
                self.update_status("Обработка завершена")
                self.log(f"\n🎉 Готово! Обработано СП: {processed_count}/{total_count}")
                self.log(f"📁 Отчеты сохранены в папке: {reports_folder}")
            
        except Exception as e:
            error_message = str(e)
            self.log(f"❌ Критическая ошибка: {error_message}")
            self.root.after(0, lambda msg=error_message: messagebox.showerror("Ошибка", f"Произошла критическая ошибка:\n{msg}"))
        finally:
            self.reset_ui_after_processing()
    
    def start_chrome_automatically(self):
        try:
            self.log("🔍 Проверяем запущенный Chrome...")
            driver = get_or_connect_chrome()
            if driver:
                self.log("✅ Подключились к существующему Chrome")
                return driver, None

            self.log("🔄 Запускаем новый Chrome...")
            
            chrome_cmd = [
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                f"--remote-debugging-port={DEBUGGING_PORT}",
                f"--user-data-dir=C:\\temp\\chrome_debug",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-translate"
            ]
            
            self.log("🚀 Запускаем процесс Chrome...")
            process = subprocess.Popen(chrome_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            self.log("⏳ Ожидаем запуск Chrome (макс 15 сек)...")
            start_time = time.time()
            
            for i in range(30):
                if self.stop_processing:
                    self.log("🛑 Запуск Chrome прерван")
                    try:
                        process.terminate()
                        process.wait(timeout=2)
                    except:
                        pass
                    return None, None
                
                time.sleep(0.5)
                
                driver = get_or_connect_chrome()
                if driver:
                    elapsed = time.time() - start_time
                    self.log(f"✅ Chrome запущен за {elapsed:.1f} сек")
                    return driver, process
                
                if i % 4 == 0:
                    self.log(f"⏳ Ожидание... ({i//2}/15 сек)")

            self.log("❌ Chrome не запустился за 15 секунд")
            try:
                process.terminate()
                process.wait(timeout=2)
            except:
                pass
            return None, None
            
        except Exception as e:
            self.log(f"❌ Ошибка при запуске Chrome: {str(e)}")
            return None, None
    
    def reset_ui_after_processing(self):
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.open_folder_button.config(state="normal")
        self.stop_processing = False
        self.update_status("Готов к работе")
        self.update_progress(0)

def build_speed_url(time_params: dict, sp_ids: list[int]) -> str:
    params = {
        "from_date": time_params['speed']['from_date'],
        "to_date": time_params['speed']['to_date'],
        "lines_per_page": LINES_PER_PAGE,
    }

    query = urlencode(params, quote_via=quote_plus)
    for sp_id in sp_ids:
        query += f"&service_provider_ids[]={sp_id}"

    return f"{BASE_URL_SPEED}?{query}"

def build_ads_url(sp_id: int) -> str:
    params = {
        "service_provider_id[]": sp_id,
        "status[]": 1,
    }
    
    query = urlencode(params, quote_via=quote_plus)
    return f"{BASE_URL_ADS}?{query}"

def build_conversion_url(time_params: dict, sp_ids: list[int]) -> str:
    params = {
        "from_date": time_params['conversion']['from_date'],
        "to_date": time_params['conversion']['to_date'],
        "lines_per_page": LINES_PER_PAGE,
    }

    query = urlencode(params, quote_via=quote_plus)
    for sp_id in sp_ids:
        query += f"&service_provider_ids[]={sp_id}"

    return f"{BASE_URL_CONVERSION}?{query}"

def build_arbitrage_url(time_params: dict, sp_id: int) -> str:
    params = {
        "from_date": time_params['arbitrage']['from_date'],
        "to_date": time_params['arbitrage']['to_date'],
        "fiat_id[]": 3,
        "status[]": 5,
        "service_provider[]": sp_id,
    }
    
    query = urlencode(params, quote_via=quote_plus)
    return f"{BASE_URL_DEALS}?{query}"

def build_bank_statements_url(sp_id: int) -> str:
    params = {
        "service_provider[]": sp_id,
    }
    
    query = urlencode(params, quote_via=quote_plus)
    return f"{BASE_URL_BANK_STATEMENTS}?{query}"

def wait_for_table_loaded(driver, timeout=60):
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            table = WebDriverWait(driver, 1).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            
            rows = table.find_elements(By.TAG_NAME, "tr")
            if len(rows) > 1:
                data_cells = table.find_elements(By.TAG_NAME, "td")
                if len(data_cells) > 0:
                    return True
            
            header_cells = table.find_elements(By.TAG_NAME, "th")
            if len(header_cells) > 5:
                return False
            
        except Exception:
            pass
        
        time.sleep(1)
    
    return False

def get_current_page_html(driver):
    try:
        if wait_for_table_loaded(driver):
            return driver.page_source
        else:
            return driver.page_source
    except Exception as e:
        return None

def parse_speed_data(html_content: str, sp_name: str) -> dict:
    soup = BeautifulSoup(html_content, 'html.parser')
    results = {
        'total_mean_time': "0",
        'total_deals': "0",
        'arbitrage_count': "0",
        'traders': []
    }
    
    table = soup.find('table')
    if not table:
        return results
    
    rows = table.find_all('tr')
    actual_sp_name = find_sp_in_table(soup, sp_name)
    
    total_cells = find_total_row(rows, sp_name, actual_sp_name)
    
    if total_cells and len(total_cells) >= 7:
        results['total_deals'] = total_cells[3].get_text(strip=True)
        results['total_mean_time'] = total_cells[4].get_text(strip=True)
        results['arbitrage_count'] = total_cells[5].get_text(strip=True)
    
    traders_dict = {}
    current_trader = None
    
    for row in rows:
        cells = row.find_all(['td', 'th'])
        
        if len(cells) > 1 and cells[0].get_text(strip=True) == "" and "Total (" in cells[1].get_text():
            trader_name = cells[1].get_text(strip=True).replace("Total (", "").replace(")", "")
            
            if trader_name not in traders_dict:
                traders_dict[trader_name] = {
                    'name': trader_name,
                    'sell_time': "0",
                    'buy_time': "0", 
                    'total_deals': cells[3].get_text(strip=True) if len(cells) > 3 else "0"
                }
            current_trader = trader_name
        
        elif current_trader and len(cells) >= 7:
            op_type = cells[2].get_text(strip=True)
            if op_type == 'Sell':
                traders_dict[current_trader]['sell_time'] = cells[4].get_text(strip=True)
            elif op_type == 'Buy':
                traders_dict[current_trader]['buy_time'] = cells[4].get_text(strip=True)
    
    results['traders'] = list(traders_dict.values())
    
    return results

def parse_ads_data(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, 'html.parser')
    results = {
        'sell_methods': set(),
        'buy_methods': set(),
        'sell_count': 0,
        'buy_count': 0,
        'ads_count': 0,
        'is_active': True
    }
    
    table = soup.find('table')
    if not table:
        results['is_active'] = False
        return results
    
    rows = table.find_all('tr')[1:]
    
    if len(rows) == 0:
        results['is_active'] = False
        return results
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 10:
            op_type = cells[9].get_text(strip=True)
            payment_method = cells[7].get_text(strip=True)
            
            if op_type == 'Sell':
                results['sell_methods'].add(payment_method)
                results['sell_count'] += 1
            elif op_type == 'Buy':
                results['buy_methods'].add(payment_method)
                results['buy_count'] += 1
            
            results['ads_count'] += 1
    
    if results['ads_count'] == 0:
        results['is_active'] = False
    
    results['sell_methods'] = list(results['sell_methods'])
    results['buy_methods'] = list(results['buy_methods'])
    
    return results

def parse_conversion_data(html_content: str, sp_name: str) -> dict:
    soup = BeautifulSoup(html_content, 'html.parser')
    results = {
        'conversion_percent': "0",
        'paid_count': "0",
        'cancelled_count': "0",
        'total_count': "0"
    }
    
    table = soup.find('table')
    if not table:
        return results
    
    rows = table.find_all('tr')
    actual_sp_name = find_sp_in_table(soup, sp_name)
    
    total_cells = find_total_row(rows, sp_name, actual_sp_name)
    
    if total_cells and len(total_cells) >= 10:
        results['paid_count'] = total_cells[4].get_text(strip=True)
        results['cancelled_count'] = total_cells[5].get_text(strip=True)
        results['total_count'] = total_cells[6].get_text(strip=True)
        results['conversion_percent'] = total_cells[9].get_text(strip=True)
    
    return results

def parse_arbitrage_data(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, 'html.parser')
    results = {
        'arbitrage_count': 0,
        'arbitrage_deals': []
    }
    
    table = soup.find('table')
    if not table:
        return results
    
    rows = table.find_all('tr')[1:]
    
    if len(rows) == 0:
        return results
    
    arbitrage_rows = table.find_all('tr', class_='deal-disputed')
    
    for row in arbitrage_rows:
        cells = row.find_all('td')
        
        if len(cells) >= 10:
            deal_data = create_deal_data(cells)
            results['arbitrage_deals'].append(deal_data)
            results['arbitrage_count'] += 1
    
    if results['arbitrage_count'] == 0:
        all_rows = table.find_all('tr')[1:]
        
        for row in all_rows:
            cells = row.find_all('td')
            if len(cells) > 15:
                status = cells[15].get_text(strip=True)
                if 'arbitration' in status.lower():
                    deal_data = create_deal_data(cells)
                    results['arbitrage_deals'].append(deal_data)
                    results['arbitrage_count'] += 1
    
    return results

def parse_bank_statements_data(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, 'html.parser')
    results = {
        'trader_dates': {},
        'latest_overall': None
    }
    
    table = soup.find('table')
    if not table:
        return results
    
    rows = table.find_all('tr')[1:]
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 10:
            trader = cells[3].get_text(strip=True)
            date_str = cells[9].get_text(strip=True)
            
            try:
                date_only = date_str.split(' ')[0]
                date_obj = datetime.datetime.strptime(date_only, "%d.%m.%Y").date()
                
                if trader not in results['trader_dates'] or date_obj > results['trader_dates'][trader]:
                    results['trader_dates'][trader] = date_obj
                    
                if not results['latest_overall'] or date_obj > results['latest_overall']:
                    results['latest_overall'] = date_obj
                    
            except (ValueError, IndexError):
                continue
    
    return results

def format_bank_statements_info(bank_data: dict) -> str:
    if not bank_data['trader_dates']:
        return "Выписок не найдено"
    
    sorted_traders = sorted(bank_data['trader_dates'].items(), key=lambda x: x[1], reverse=True)
    
    formatted = []
    for trader, date in sorted_traders:
        date_str = date.strftime("%d.%m.%Y")
        formatted.append(f"{trader} - {date_str}")
    
    return ", ".join(formatted)

def generate_report(sp_name: str, speed_data: dict, ads_data: dict, conversion_data: dict, arbitrage_data: dict, bank_data: dict, auto_no_incidents: bool) -> str:
    report = []
    
    report.append(f"Отчет по СП: {sp_name}")
    report.append("=" * 50)
    
    report.append(f"1. Скорость:")
    report.append(f"- Общая: {speed_data['total_mean_time']} мин. ({speed_data['total_deals']} сделок)")
    
    for trader in speed_data['traders']:
        report.append(f"- {trader['name']}: sell {trader['sell_time']}, buy {trader['buy_time']} ({trader['total_deals']} сделок)")
    
    if not ads_data.get('is_active', True):
        report.append("2. **СП НЕ АКТИВЕН**")
    else:
        sell_methods = ", ".join(ads_data['sell_methods']) if ads_data['sell_methods'] else "-"
        buy_methods = ", ".join(ads_data['buy_methods']) if ads_data['buy_methods'] else "-"
        report.append(f"2. Активны:\nSell - {sell_methods}\nBuy - {buy_methods}")
    
    conversion_value = conversion_data['conversion_percent']
    if conversion_value.endswith('%'):
        conversion_value = conversion_value[:-1]
    report.append(f"3. Конверсия {conversion_value}%.")
    
    report.append("4. -")
    
    arbitrage_details = []
    for deal in arbitrage_data['arbitrage_deals']:
        arbitrage_details.append(f"ID {deal['id']} (Invoice {deal['invoice']})")
    
    if arbitrage_details:
        report.append(f"5. Арбитражи - {arbitrage_data['arbitrage_count']} шт.\n   " + "\n   ".join(arbitrage_details))
    else:
        report.append(f"5. Арбитражи - {arbitrage_data['arbitrage_count']} шт.")
    
    if auto_no_incidents:
        report.append("6. Инцидентов не найдено")
    else:
        report.append("6. -")
    
    if not ads_data.get('is_active', True):
        report.append("7. **СП НЕ АКТИВЕН**")
    else:
        has_sell = ads_data['sell_count'] > 0
        has_buy = ads_data['buy_count'] > 0
        
        if has_sell and has_buy:
            status = "sell и buy"
        elif has_sell:
            status = "sell"
        elif has_buy:
            status = "buy"
        else:
            status = "не активен"
        
        report.append(f"7. СП в работе на {status}, {ads_data['ads_count']} объявлений")
    
    bank_info = format_bank_statements_info(bank_data)
    report.append(f"8. {bank_info}")
    
    return "\n".join(report)

def save_report_to_txt(sp_name: str, report: str):
    safe_name = "".join(c for c in sp_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"{safe_name}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    return filename

def process_single_sp_gui(driver, sp_id: int, sp_name: str, time_params: dict, log_func, auto_no_incidents: bool):
    log_func(f"🔗 Обрабатываем {sp_name} (ID {sp_id})")
    
    speed_url = build_speed_url(time_params, [sp_id])
    log_func(f"📊 Страница скорости: {speed_url}")
    
    log_func("🌐 Открываю страницу скорости...")
    driver.get(speed_url)

    speed_html = get_current_page_html(driver)
    speed_data = {}
    
    if speed_html:
        speed_data = parse_speed_data(speed_html, sp_name)
        log_func(f"✅ Данные скорости получены: {speed_data['total_deals']} сделок, время: {speed_data['total_mean_time']} мин.")
        log_func(f"👥 Найдено трейдеров: {len(speed_data['traders'])}")
    else:
        log_func("❌ Не удалось получить данные скорости")
        speed_data = {'total_mean_time': '0', 'total_deals': '0', 'arbitrage_count': '0', 'traders': []}
    
    ads_url = build_ads_url(sp_id)
    log_func(f"📋 Страница объявлений: {ads_url}")
    
    log_func("🌐 Открываю страницу объявлений...")
    driver.get(ads_url)

    ads_html = get_current_page_html(driver)
    ads_data = {}

    if ads_html:
        ads_data = parse_ads_data(ads_html)
        if not ads_data['is_active']:
            log_func("❌ СП НЕ АКТИВЕН - объявлений не найдено")
        else:
            log_func(f"✅ Данные объявлений получены: {ads_data['ads_count']} объявлений")
            log_func(f"📊 Sell объявлений: {ads_data['sell_count']}, Buy объявлений: {ads_data['buy_count']}")
    else:
        log_func("❌ Не удалось получить данные объявлений")
        ads_data = {
            'sell_methods': [], 
            'buy_methods': [], 
            'sell_count': 0, 
            'buy_count': 0, 
            'ads_count': 0,
            'is_active': False
        }
    
    conversion_url = build_conversion_url(time_params, [sp_id])
    log_func(f"📈 Страница конверсии: {conversion_url}")
    
    log_func("🌐 Открываю страницу конверсии...")
    driver.get(conversion_url)

    conversion_html = get_current_page_html(driver)
    conversion_data = {}
    
    if conversion_html:
        conversion_data = parse_conversion_data(conversion_html, sp_name)
        log_func(f"✅ Данные конверсии получены: {conversion_data['conversion_percent']}%")
    else:
        log_func("❌ Не удалось получить данные конверсии")
        conversion_data = {'conversion_percent': '0', 'paid_count': '0', 'cancelled_count': '0', 'total_count': '0'}
    
    arbitrage_url = build_arbitrage_url(time_params, sp_id)
    log_func(f"⚖️ Страница арбитражей: {arbitrage_url}")
    
    log_func("🌐 Открываю страницу арбитражей...")
    driver.get(arbitrage_url)

    arbitrage_html = get_current_page_html(driver)
    arbitrage_data = {}
    
    if arbitrage_html:
        arbitrage_data = parse_arbitrage_data(arbitrage_html)
        log_func(f"✅ Данные арбитражей получены: {arbitrage_data['arbitrage_count']} сделок")
    else:
        log_func("❌ Не удалось получить данные арбитражей")
        arbitrage_data = {'arbitrage_count': 0, 'arbitrage_deals': []}
    
    bank_statements_url = build_bank_statements_url(sp_id)
    log_func(f"🏦 Страница банковских выписок: {bank_statements_url}")
    
    log_func("🌐 Открываю страницу банковских выписок...")
    driver.get(bank_statements_url)

    bank_html = get_current_page_html(driver)
    bank_data = {}
    
    if bank_html:
        bank_data = parse_bank_statements_data(bank_html)
        bank_info = format_bank_statements_info(bank_data)
        log_func(f"✅ Данные выписок получены: {len(bank_data['trader_dates'])} трейдеров")
        log_func(f"📅 Информация о выписках: {bank_info}")
    else:
        log_func("❌ Не удалось получить данные банковских выписок")
        bank_data = {'trader_dates': {}, 'latest_overall': None}
    
    report = generate_report(sp_name, speed_data, ads_data, conversion_data, arbitrage_data, bank_data, auto_no_incidents)
    filename = save_report_to_txt(sp_name, report)
    
    log_func(f"💾 Отчет сохранен в файл: {filename}")
    
    return filename

def main():
    root = tk.Tk()
    app = PayportApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
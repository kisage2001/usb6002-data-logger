"""
USB-6002 Data Acquisition System
High-performance data logger with real-time monitoring
 
Developer: Tsutsumi Hiroki
Institution: Tokyo National College of Technology
Version: 1.3
Date: 2025-05-27
 
Changes from v1.1:
- [Fix] Active channel states (checkboxes) are now saved to config.json and
        restored on next launch.
- [Fix] Bulk-change in ConfigEditor now covers Unit, Y Min, and Y Max in
        addition to Conversion Factor.
- [Fix] Hold/Resume: the DAQ buffer is now drained during Hold so that
        resuming does not flood the plot with accumulated samples.
"""
 
import nidaqmx
from nidaqmx.constants import TerminalConfiguration, AcquisitionType, READ_ALL_AVAILABLE
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib
matplotlib.use('TkAgg')
import pandas as pd
import numpy as np
import datetime
import os
import collections
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from PIL import Image
import io
 
# バージョン情報
__version__ = "1.3"
__author__ = "Tsutsumi Hiroki"
__date__ = "2025-05-27"
__institution__ = "Tokyo National College of Technology"
 
# デフォルト設定ファイルのパス
CONFIG_FILE = "config.json"
 
# カラーパレット（論文用：色覚多様性対応）
COLORS = ['#E41A1C', '#377EB8', '#4DAF4A', '#984EA3',
          '#FF7F00', '#A65628', '#F781BF', '#999999']
 
 
class ConfigEditor(tk.Toplevel):
    """設定エディタウィンドウ"""
    def __init__(self, parent, config):
        super().__init__(parent)
        self.title("Configuration Editor")
        self.geometry("800x650")
        self.config = config
        self.result = None
 
        # メインフレーム
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
 
        # ノートブック（タブ）
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
 
        # チャンネル設定タブ
        channel_frame = ttk.Frame(notebook, padding="10")
        notebook.add(channel_frame, text="Channels")
 
        # グラフ設定タブ
        graph_frame = ttk.Frame(notebook, padding="10")
        notebook.add(graph_frame, text="Graph Settings")
 
        # === チャンネル設定タブの内容 ===
        canvas = tk.Canvas(channel_frame)
        scrollbar = ttk.Scrollbar(channel_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
 
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
 
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
 
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
 
        # ------------------------------------------------------------------ #
        # row=0: カラムヘッダー
        # row=1: 一括変更入力（各列の真下に配置）
        # row=2〜: チャンネルごとの設定値
        # ------------------------------------------------------------------ #
 
        # --- row 0: ヘッダー ---
        COL_CH     = 0
        COL_NAME   = 1
        COL_FACTOR = 2
        COL_UNIT   = 3
        COL_YMIN   = 4
        COL_YMAX   = 5
 
        WIDTHS = {
            COL_CH:     4,
            COL_NAME:   20,
            COL_FACTOR: 15,
            COL_UNIT:   10,
            COL_YMIN:   10,
            COL_YMAX:   10,
        }
 
        headers = {
            COL_CH:     "CH",
            COL_NAME:   "Name",
            COL_FACTOR: "Conv. Factor",
            COL_UNIT:   "Unit",
            COL_YMIN:   "Y Min",
            COL_YMAX:   "Y Max",
        }
        for col, text in headers.items():
            ttk.Label(scrollable_frame, text=text,
                      font=('Arial', 10, 'bold')).grid(
                row=0, column=col, padx=5, pady=(8, 2), sticky=tk.W)
 
        # --- row 1: 一括変更行 ---
        # CH列: ラベル
        ttk.Label(scrollable_frame, text="ALL",
                  font=('Arial', 9, 'italic'),
                  foreground='gray').grid(
            row=1, column=COL_CH, padx=5, pady=2)
 
        # Name列: 一括変更なし（空白）
 
        # Conv. Factor
        self.bulk_factor_var = tk.StringVar(value="")
        bulk_factor_frame = ttk.Frame(scrollable_frame)
        bulk_factor_frame.grid(row=1, column=COL_FACTOR, padx=5, pady=2, sticky=tk.W)
        ttk.Entry(bulk_factor_frame, textvariable=self.bulk_factor_var,
                  width=WIDTHS[COL_FACTOR] - 5).pack(side=tk.LEFT)
        ttk.Button(bulk_factor_frame, text="▶", width=2,
                   command=self.apply_bulk_factor).pack(side=tk.LEFT, padx=(2, 0))
 
        # Unit
        self.bulk_unit_var = tk.StringVar(value="")
        bulk_unit_frame = ttk.Frame(scrollable_frame)
        bulk_unit_frame.grid(row=1, column=COL_UNIT, padx=5, pady=2, sticky=tk.W)
        ttk.Entry(bulk_unit_frame, textvariable=self.bulk_unit_var,
                  width=WIDTHS[COL_UNIT] - 3).pack(side=tk.LEFT)
        ttk.Button(bulk_unit_frame, text="▶", width=2,
                   command=self.apply_bulk_unit).pack(side=tk.LEFT, padx=(2, 0))
 
        # Y Min
        self.bulk_ymin_var = tk.StringVar(value="")
        bulk_ymin_frame = ttk.Frame(scrollable_frame)
        bulk_ymin_frame.grid(row=1, column=COL_YMIN, padx=5, pady=2, sticky=tk.W)
        ttk.Entry(bulk_ymin_frame, textvariable=self.bulk_ymin_var,
                  width=WIDTHS[COL_YMIN] - 3).pack(side=tk.LEFT)
        ttk.Button(bulk_ymin_frame, text="▶", width=2,
                   command=self.apply_bulk_ymin).pack(side=tk.LEFT, padx=(2, 0))
 
        # Y Max
        self.bulk_ymax_var = tk.StringVar(value="")
        bulk_ymax_frame = ttk.Frame(scrollable_frame)
        bulk_ymax_frame.grid(row=1, column=COL_YMAX, padx=5, pady=2, sticky=tk.W)
        ttk.Entry(bulk_ymax_frame, textvariable=self.bulk_ymax_var,
                  width=WIDTHS[COL_YMAX] - 3).pack(side=tk.LEFT)
        ttk.Button(bulk_ymax_frame, text="▶", width=2,
                   command=self.apply_bulk_ymax).pack(side=tk.LEFT, padx=(2, 0))
 
        # 区切り線
        ttk.Separator(scrollable_frame, orient='horizontal').grid(
            row=2, column=0, columnspan=6, sticky=tk.EW, padx=5, pady=4)
 
        # チャンネル設定の入力フィールド
        self.channel_entries = []
        for i, ch in enumerate(config['channels']):
            row = i + 3  # header(0) + bulk(1) + separator(2)
 
            ttk.Label(scrollable_frame, text=f"CH{ch['id']}").grid(
                row=row, column=0, padx=5, pady=2)
 
            name_var = tk.StringVar(value=ch['name'])
            ttk.Entry(scrollable_frame, textvariable=name_var,
                      width=20).grid(row=row, column=1, padx=5, pady=2)
 
            factor_var = tk.DoubleVar(value=ch['conversion_factor'])
            ttk.Entry(scrollable_frame, textvariable=factor_var,
                      width=15).grid(row=row, column=2, padx=5, pady=2)
 
            unit_var = tk.StringVar(value=ch['unit'])
            ttk.Entry(scrollable_frame, textvariable=unit_var,
                      width=10).grid(row=row, column=3, padx=5, pady=2)
 
            ymin_var = tk.DoubleVar(value=ch['y_min'])
            ttk.Entry(scrollable_frame, textvariable=ymin_var,
                      width=10).grid(row=row, column=4, padx=5, pady=2)
 
            ymax_var = tk.DoubleVar(value=ch['y_max'])
            ttk.Entry(scrollable_frame, textvariable=ymax_var,
                      width=10).grid(row=row, column=5, padx=5, pady=2)
 
            self.channel_entries.append({
                'id': ch['id'],
                'name': name_var,
                'factor': factor_var,
                'unit': unit_var,
                'ymin': ymin_var,
                'ymax': ymax_var
            })
 
        # === グラフ設定タブの内容 ===
        font_frame = ttk.LabelFrame(graph_frame, text="Font Settings", padding="10")
        font_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)
 
        ttk.Label(font_frame, text="Font Family:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.font_family_var = tk.StringVar(
            value=config['graph'].get('font_family', 'Arial'))
        font_family_combo = ttk.Combobox(
            font_frame, textvariable=self.font_family_var, width=20)
        font_family_combo['values'] = (
            'Arial', 'Times New Roman', 'Helvetica', 'Courier New',
            'Verdana', 'Georgia', 'Comic Sans MS', 'DejaVu Sans',
            'Liberation Sans', 'Noto Sans')
        font_family_combo.grid(row=0, column=1, padx=5, pady=5)
 
        ttk.Label(font_frame, text="Title Font Size:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.title_fontsize_var = tk.IntVar(
            value=config['graph']['font_size_title'])
        ttk.Spinbox(font_frame, from_=8, to=32,
                    textvariable=self.title_fontsize_var,
                    width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
 
        ttk.Label(font_frame, text="Axis Label Font Size:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.label_fontsize_var = tk.IntVar(
            value=config['graph']['font_size_label'])
        ttk.Spinbox(font_frame, from_=8, to=24,
                    textvariable=self.label_fontsize_var,
                    width=10).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
 
        ttk.Label(font_frame, text="Tick Label Font Size:").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.tick_fontsize_var = tk.IntVar(
            value=config['graph']['font_size_tick'])
        ttk.Spinbox(font_frame, from_=6, to=20,
                    textvariable=self.tick_fontsize_var,
                    width=10).grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
 
        ttk.Label(font_frame, text="Legend Font Size:").grid(
            row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.legend_fontsize_var = tk.IntVar(
            value=config['graph']['font_size_legend'])
        ttk.Spinbox(font_frame, from_=6, to=20,
                    textvariable=self.legend_fontsize_var,
                    width=10).grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
 
        other_frame = ttk.LabelFrame(graph_frame, text="Other Settings", padding="10")
        other_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)
 
        ttk.Label(other_frame, text="Graph Title:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.graph_title_var = tk.StringVar(value=config['graph']['title'])
        ttk.Entry(other_frame, textvariable=self.graph_title_var,
                  width=40).grid(row=0, column=1, padx=5, pady=5)
 
        ttk.Label(other_frame, text="X-axis Label:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.xlabel_var = tk.StringVar(value=config['graph']['xlabel'])
        ttk.Entry(other_frame, textvariable=self.xlabel_var,
                  width=40).grid(row=1, column=1, padx=5, pady=5)
 
        ttk.Label(other_frame, text="Y-axis Label:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.ylabel_var = tk.StringVar(
            value=config['graph'].get('ylabel', 'Voltage (V)'))
        ttk.Entry(other_frame, textvariable=self.ylabel_var,
                  width=40).grid(row=2, column=1, padx=5, pady=5)
 
        ttk.Label(other_frame, text="Show Grid:").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.grid_var = tk.BooleanVar(value=config['graph']['grid'])
        ttk.Checkbutton(other_frame, variable=self.grid_var).grid(
            row=3, column=1, sticky=tk.W, padx=5, pady=5)
 
        ttk.Label(other_frame, text="Line Width:").grid(
            row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.linewidth_var = tk.DoubleVar(value=config['graph']['line_width'])
        ttk.Spinbox(other_frame, from_=0.5, to=5.0, increment=0.5,
                    textvariable=self.linewidth_var,
                    width=10).grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
 
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="OK",
                   command=self.ok_clicked).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel",
                   command=self.cancel_clicked).pack(side=tk.RIGHT)
 
    # ---------------------------------------------------------------------- #
    # 一括変更ヘルパー
    # ---------------------------------------------------------------------- #
    def apply_bulk_factor(self):
        """変換係数を全チャンネルに一括適用"""
        try:
            value = float(self.bulk_factor_var.get())
            for entry in self.channel_entries:
                entry['factor'].set(value)
            messagebox.showinfo("Success",
                                f"Conversion factor {value} applied to all channels.")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")
 
    def apply_bulk_unit(self):
        """単位を全チャンネルに一括適用"""
        value = self.bulk_unit_var.get().strip()
        if not value:
            messagebox.showerror("Error", "Please enter a unit string.")
            return
        for entry in self.channel_entries:
            entry['unit'].set(value)
        messagebox.showinfo("Success",
                            f"Unit '{value}' applied to all channels.")
 
    def apply_bulk_ymin(self):
        """Y Min を全チャンネルに一括適用"""
        try:
            value = float(self.bulk_ymin_var.get())
            for entry in self.channel_entries:
                entry['ymin'].set(value)
            messagebox.showinfo("Success",
                                f"Y Min {value} applied to all channels.")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")
 
    def apply_bulk_ymax(self):
        """Y Max を全チャンネルに一括適用"""
        try:
            value = float(self.bulk_ymax_var.get())
            for entry in self.channel_entries:
                entry['ymax'].set(value)
            messagebox.showinfo("Success",
                                f"Y Max {value} applied to all channels.")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")
 
    # ---------------------------------------------------------------------- #
    def ok_clicked(self):
        try:
            for i, entry in enumerate(self.channel_entries):
                self.config['channels'][i]['name'] = entry['name'].get()
                self.config['channels'][i]['conversion_factor'] = entry['factor'].get()
                self.config['channels'][i]['unit'] = entry['unit'].get()
                self.config['channels'][i]['y_min'] = entry['ymin'].get()
                self.config['channels'][i]['y_max'] = entry['ymax'].get()
 
            self.config['graph']['font_family'] = self.font_family_var.get()
            self.config['graph']['font_size_title'] = self.title_fontsize_var.get()
            self.config['graph']['font_size_label'] = self.label_fontsize_var.get()
            self.config['graph']['font_size_tick'] = self.tick_fontsize_var.get()
            self.config['graph']['font_size_legend'] = self.legend_fontsize_var.get()
            self.config['graph']['title'] = self.graph_title_var.get()
            self.config['graph']['xlabel'] = self.xlabel_var.get()
            self.config['graph']['ylabel'] = self.ylabel_var.get()
            self.config['graph']['grid'] = self.grid_var.get()
            self.config['graph']['line_width'] = self.linewidth_var.get()
 
            self.result = self.config
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input:\n{e}")
 
    def cancel_clicked(self):
        self.result = None
        self.destroy()
 
 
# ========================================================================== #
class DAQApplication:
    def __init__(self, root):
        self.root = root
        self.root.title(f"USB-6002 Data Acquisition System v{__version__}")
        self.root.geometry("1400x900")
 
        # 設定の読み込み
        self.config = self.load_config()
 
        # 初期化
        self.task = None
        self.is_recording = False
        self.is_paused = False
        self.recorded_data = None
        self.recording_count = 0
        self.target_samples = 0
        self.update_id = None
        self.legend = None
 
        self.update_counter = 0
        self.draw_interval = 2
 
        self.channel_name_vars = []
        self.channel_factor_vars = []
 
        # ------------------------------------------------------------------ #
        # [Fix 1] active_channels を config から復元
        # ------------------------------------------------------------------ #
        saved_active = self.config.get('active_channels', [True] * 8)
        # チャンネル数が変わっていても対応できるよう長さを揃える
        self.active_channels = (saved_active + [True] * 8)[:8]
 
        self.current_values = [0.0] * 8
 
        self.create_widgets()
        self.setup_graph()
        self.start_task()
        self.update_plot()
 
    # ---------------------------------------------------------------------- #
    # 設定読み込み
    # ---------------------------------------------------------------------- #
    def load_config(self):
        default_config = {
            "device": {
                "device_name": "Dev1",
                "sampling_rate": 1000,
                "samples_per_channel": 100,
                "terminal_config": "RSE"
            },
            "channels": [
                {"id": i, "name": f"CH{i}", "conversion_factor": 1.0,
                 "unit": "V", "y_min": -10, "y_max": 10}
                for i in range(8)
            ],
            # [Fix 1] active_channels をデフォルト設定に追加
            "active_channels": [True] * 8,
            "graph": {
                "title": "Real-time Monitoring",
                "xlabel": "Time [s]",
                "ylabel": "Voltage (V)",
                "time_window": 5.0,
                "grid": True,
                "line_width": 1.5,
                "font_family": "Arial",
                "font_size_title": 18,
                "font_size_label": 16,
                "font_size_tick": 14,
                "font_size_legend": 12,
                "legend_position": "upper right",
                "legend_columns": 2
            }
        }
 
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                    elif isinstance(default_config[key], dict):
                        for subkey in default_config[key]:
                            if subkey not in config[key]:
                                config[key][subkey] = default_config[key][subkey]
                return config
            except Exception as e:
                print(f"Warning: Failed to load config file: {e}")
                return default_config
        return default_config
 
    # ---------------------------------------------------------------------- #
    # UI 構築
    # ---------------------------------------------------------------------- #
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
 
        control_frame = ttk.Frame(main_frame, width=320)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 60))
        control_frame.pack_propagate(False)
 
        header_frame = ttk.Frame(control_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_frame, text="USB-6002 DAQ",
                  font=('Arial', 16, 'bold')).pack()
        ttk.Label(header_frame, text=f"v{__version__}",
                  font=('Arial', 9), foreground='gray').pack()
 
        status_frame = ttk.LabelFrame(control_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        self.status_label = ttk.Label(status_frame, text="Monitoring...",
                                      font=('Arial', 12, 'bold'), foreground='green')
        self.status_label.pack()
        self.progress_label = ttk.Label(status_frame, text="", font=('Arial', 9))
        self.progress_label.pack()
 
        button_frame = ttk.LabelFrame(control_frame, text="Controls", padding="10")
        button_frame.pack(fill=tk.X, pady=(0, 10))
        self.record_btn = ttk.Button(button_frame, text="🔴 Record",
                                     command=self.start_recording)
        self.record_btn.pack(fill=tk.X, pady=2)
        self.hold_btn = ttk.Button(button_frame, text="⏸ Hold",
                                   command=self.toggle_hold)
        self.hold_btn.pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="⚙ Settings",
                   command=self.open_settings).pack(fill=tk.X, pady=2)
 
        export_frame = ttk.LabelFrame(control_frame, text="Graph Export", padding="10")
        export_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(export_frame, text="📋 Copy to Clipboard",
                   command=self.copy_to_clipboard).pack(fill=tk.X, pady=2)
        ttk.Button(export_frame, text="💾 Save Figure...",
                   command=self.save_figure).pack(fill=tk.X, pady=2)
        ttk.Button(export_frame, text="📊 Quick Export",
                   command=self.quick_export_menu).pack(fill=tk.X, pady=2)
        ttk.Button(export_frame, text="🔄 Clear All Data",
                   command=self.clear_all_data).pack(fill=tk.X, pady=2)
 
        channel_frame = ttk.LabelFrame(control_frame, text="Active Channels",
                                       padding="10")
        channel_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
 
        canvas = tk.Canvas(channel_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(channel_frame, orient="vertical",
                                  command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
 
        hdr = ttk.Frame(scrollable_frame)
        hdr.pack(fill=tk.X, pady=(0, 5))
        for col, (txt, w) in enumerate(
                [("On", 3), ("Name", 10), ("Factor", 8), ("Current", 12)]):
            ttk.Label(hdr, text=txt, font=('Arial', 9, 'bold'),
                      width=w).grid(row=0, column=col, padx=2)
 
        self.channel_vars = []
        self.channel_name_vars = []
        self.channel_factor_vars = []
        self.value_labels = []
 
        for i, ch in enumerate(self.config['channels']):
            ch_row = ttk.Frame(scrollable_frame)
            ch_row.pack(fill=tk.X, pady=2)
 
            # [Fix 1] 保存済みのアクティブ状態をチェックボックスの初期値に使用
            var = tk.BooleanVar(value=self.active_channels[i])
            ttk.Checkbutton(ch_row, variable=var,
                            command=self.update_active_channels,
                            width=3).grid(row=0, column=0, padx=2)
            self.channel_vars.append(var)
 
            name_var = tk.StringVar(value=ch['name'])
            self.channel_name_vars.append(name_var)
            name_entry = ttk.Entry(ch_row, textvariable=name_var, width=10)
            name_entry.grid(row=0, column=1, padx=2)
            name_entry.bind('<Return>', lambda e, idx=i: self.update_channel_name(idx))
            name_entry.bind('<FocusOut>', lambda e, idx=i: self.update_channel_name(idx))
 
            factor_var = tk.DoubleVar(value=ch['conversion_factor'])
            self.channel_factor_vars.append(factor_var)
            factor_entry = ttk.Entry(ch_row, textvariable=factor_var, width=8)
            factor_entry.grid(row=0, column=2, padx=2)
            factor_entry.bind('<Return>',
                              lambda e, idx=i: self.update_channel_factor(idx))
            factor_entry.bind('<FocusOut>',
                              lambda e, idx=i: self.update_channel_factor(idx))
 
            value_frame = ttk.Frame(ch_row)
            value_frame.grid(row=0, column=3, padx=2)
            tk.Canvas(value_frame, width=10, height=10,
                      highlightthickness=0, bg=COLORS[i]).pack(
                side=tk.LEFT, padx=(0, 3))
            val_label = ttk.Label(value_frame,
                                  text=f"+0.000 {ch['unit']}",
                                  font=('Courier', 9), foreground=COLORS[i])
            val_label.pack(side=tk.LEFT)
            self.value_labels.append(val_label)
 
        self.graph_frame = ttk.Frame(main_frame)
        self.graph_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
 
    # ---------------------------------------------------------------------- #
    # グラフ初期設定
    # ---------------------------------------------------------------------- #
    def setup_graph(self):
        graph_cfg = self.config['graph']
        font_family = graph_cfg.get('font_family', 'Arial')
 
        plt.rcParams['font.family'] = font_family
        plt.rcParams['font.size'] = graph_cfg.get('font_size_tick', 10)
 
        self.fig, self.ax = plt.subplots(figsize=(12, 7))
        self.fig.set_facecolor('white')
        self.ax.set_facecolor('white')
 
        y_min = min(ch['y_min'] for ch in self.config['channels'])
        y_max = max(ch['y_max'] for ch in self.config['channels'])
        self.ax.set_ylim(y_min, y_max)
        self.ax.set_xlim(0, graph_cfg.get('time_window', 5.0))
 
        self.ax.set_xlabel(graph_cfg['xlabel'],
                           fontsize=graph_cfg['font_size_label'],
                           fontweight='bold', fontfamily=font_family)
        self.ax.set_ylabel(graph_cfg.get('ylabel', 'Voltage (V)'),
                           fontsize=graph_cfg['font_size_label'],
                           fontweight='bold', fontfamily=font_family)
        self.ax.grid(graph_cfg['grid'], alpha=0.3, linestyle='--', linewidth=0.8)
 
        for spine in self.ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.5)
            spine.set_color('black')
 
        self.lines = []
        for i, ch in enumerate(self.config['channels']):
            line, = self.ax.plot([], [],
                                 linewidth=graph_cfg['line_width'],
                                 color=COLORS[i],
                                 label=ch['name'],
                                 alpha=0.8,
                                 animated=False)
            self.lines.append(line)
 
        self.update_legend()
        self.ax.set_title(graph_cfg['title'],
                          fontsize=graph_cfg['font_size_title'],
                          fontweight='bold', fontfamily=font_family, pad=15)
        self.fig.tight_layout(pad=2.0, rect=[0.02, 0, 1, 1])
 
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
 
        toolbar_frame = ttk.Frame(self.graph_frame)
        toolbar_frame.pack(fill=tk.X)
        NavigationToolbar2Tk(self.canvas, toolbar_frame).update()
 
        self.setup_context_menu()
 
    def update_legend(self):
        if hasattr(self, 'legend') and self.legend:
            self.legend.remove()
 
        active_lines, active_labels = [], []
        for i, ch in enumerate(self.config['channels']):
            if self.active_channels[i]:
                active_lines.append(self.lines[i])
                active_labels.append(ch['name'])
 
        if active_lines:
            graph_cfg = self.config['graph']
            self.legend = self.ax.legend(
                active_lines, active_labels,
                loc=graph_cfg.get('legend_position', 'upper right'),
                fontsize=graph_cfg['font_size_legend'],
                prop={'family': graph_cfg.get('font_family', 'Arial')},
                framealpha=0.9, edgecolor='black',
                ncol=min(graph_cfg.get('legend_columns', 2), len(active_lines)),
                columnspacing=1.0)
 
    # ---------------------------------------------------------------------- #
    # 右クリックメニュー
    # ---------------------------------------------------------------------- #
    def setup_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
 
        copy_menu = tk.Menu(self.context_menu, tearoff=0)
        copy_menu.add_command(label="PNG (High Quality)",
                              command=lambda: self.copy_to_clipboard('png'))
        copy_menu.add_command(label="JPEG (Compressed)",
                              command=lambda: self.copy_to_clipboard('jpeg'))
        copy_menu.add_separator()
        copy_menu.add_command(label="PNG (Screen Quality)",
                              command=lambda: self.copy_to_clipboard('png', dpi=100))
        self.context_menu.add_cascade(label="📋 Copy as...", menu=copy_menu)
 
        save_menu = tk.Menu(self.context_menu, tearoff=0)
        for fmt in ['png', 'jpeg', 'tiff', 'pdf', 'svg']:
            label_map = {'png': 'PNG (High-Res)', 'jpeg': 'JPEG',
                         'tiff': 'TIFF', 'pdf': 'PDF (Vector)', 'svg': 'SVG (Vector)'}
            save_menu.add_command(label=label_map[fmt],
                                  command=lambda f=fmt: self.save_figure_format(f))
        self.context_menu.add_cascade(label="💾 Save as...", menu=save_menu)
 
        self.canvas.get_tk_widget().bind("<Button-3>", self.show_context_menu)
 
    def show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
 
    # ---------------------------------------------------------------------- #
    # クリップボード・保存
    # ---------------------------------------------------------------------- #
    def copy_to_clipboard(self, format='png', dpi=150):
        try:
            self.canvas.draw()
            self.root.update()
            buf = io.BytesIO()
            self.fig.savefig(buf, format=format, dpi=dpi, bbox_inches='tight',
                             facecolor='white', edgecolor='none')
            buf.seek(0)
            img = Image.open(buf)
            try:
                import win32clipboard
                output = io.BytesIO()
                img.convert('RGB').save(output, 'BMP')
                data = output.getvalue()[14:]
                output.close()
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                win32clipboard.CloseClipboard()
                messagebox.showinfo("Success",
                                    f"Graph copied to clipboard as {format.upper()}!")
            except ImportError:
                messagebox.showinfo(
                    "Info",
                    "pywin32 module recommended for clipboard functionality.\n"
                    "Install with: pip install pywin32")
            buf.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard:\n{e}")
 
    def save_figure_format(self, format):
        format_extensions = {
            'png': [("PNG Image", "*.png")],
            'jpeg': [("JPEG Image", "*.jpg"), ("JPEG Image", "*.jpeg")],
            'tiff': [("TIFF Image", "*.tiff"), ("TIFF Image", "*.tif")],
            'pdf': [("PDF Document", "*.pdf")],
            'svg': [("SVG Vector", "*.svg")]
        }
        default_ext = {'png': '.png', 'jpeg': '.jpg', 'tiff': '.tiff',
                       'pdf': '.pdf', 'svg': '.svg'}
        filename = filedialog.asksaveasfilename(
            defaultextension=default_ext[format],
            filetypes=format_extensions[format],
            initialfile=f"Figure_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        if filename:
            dpi = 300 if format in ['png', 'jpeg', 'tiff'] else None
            self.fig.savefig(filename, dpi=dpi, bbox_inches='tight',
                             facecolor='white', edgecolor='none')
            messagebox.showinfo("Success", f"Figure saved!\n{filename}")
 
    def quick_export_menu(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Copy as PNG",
                         command=lambda: self.copy_to_clipboard('png'))
        menu.add_command(label="Copy as JPEG",
                         command=lambda: self.copy_to_clipboard('jpeg'))
        menu.add_separator()
        menu.add_command(label="Save as PNG...",
                         command=lambda: self.save_figure_format('png'))
        menu.add_command(label="Save as PDF...",
                         command=lambda: self.save_figure_format('pdf'))
        btn = self.root.focus_get()
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        menu.tk_popup(x, y)
 
    def clear_all_data(self):
        if not messagebox.askyesno("Confirm",
                                   "Clear all channel data?\n"
                                   "This will reset all graph data.",
                                   icon='warning'):
            return
        try:
            for i in range(8):
                self.display_buffer[i].clear()
                self.lines[i].set_data([], [])
                self.current_values[i] = 0.0
                self.value_labels[i].config(
                    text=f"+0.000 {self.config['channels'][i]['unit']}")
            self.canvas.draw_idle()
            messagebox.showinfo("Success", "All channel data has been cleared.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear data:\n{e}")
 
    # ---------------------------------------------------------------------- #
    # チャンネル操作
    # ---------------------------------------------------------------------- #
    def update_channel_name(self, channel_idx):
        new_name = self.channel_name_vars[channel_idx].get()
        self.config['channels'][channel_idx]['name'] = new_name
        self.lines[channel_idx].set_label(new_name)
        self.update_legend()
        self.canvas.draw_idle()
 
    def update_channel_factor(self, channel_idx):
        try:
            new_factor = self.channel_factor_vars[channel_idx].get()
            self.config['channels'][channel_idx]['conversion_factor'] = new_factor
        except tk.TclError:
            self.channel_factor_vars[channel_idx].set(
                self.config['channels'][channel_idx]['conversion_factor'])
 
    def update_active_channels(self):
        self.active_channels = [var.get() for var in self.channel_vars]
        for i, active in enumerate(self.active_channels):
            self.lines[i].set_alpha(0.8 if active else 0.1)
        self.update_legend()
        self.canvas.draw_idle()
 
    def open_settings(self):
        editor = ConfigEditor(self.root, self.config)
        self.root.wait_window(editor)
        if editor.result:
            self.config = editor.result
            self.canvas.get_tk_widget().destroy()
            self.setup_graph()
 
    # ---------------------------------------------------------------------- #
    # 録画
    # ---------------------------------------------------------------------- #
    def start_recording(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Recording Settings")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()
 
        ttk.Label(dialog, text="Recording Duration (seconds):",
                  font=('Arial', 11)).pack(pady=10)
        duration_var = tk.DoubleVar(value=10.0)
        duration_entry = ttk.Entry(dialog, textvariable=duration_var,
                                   font=('Arial', 12), width=15)
        duration_entry.pack(pady=5)
        duration_entry.focus()
 
        def start():
            try:
                duration = duration_var.get()
                if duration <= 0:
                    raise ValueError("Duration must be positive")
                self.target_samples = int(
                    duration * self.config['device']['sampling_rate'])
                self.recording_count = 0
                num_active = sum(self.active_channels)
                self.recorded_data = [[] for _ in range(num_active)]
                self.is_recording = True
                self.record_btn.config(state=tk.DISABLED)
                self.status_label.config(text="Recording...", foreground='red')
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid input:\n{e}")
 
        ttk.Button(dialog, text="Start", command=start).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack()
 
    # ---------------------------------------------------------------------- #
    # DAQ タスク
    # ---------------------------------------------------------------------- #
    def start_task(self):
        try:
            self.task = nidaqmx.Task()
            for i, (ch, active) in enumerate(
                    zip(self.config['channels'], self.active_channels)):
                if active:
                    channel_name = (f"{self.config['device']['device_name']}"
                                    f"/ai{ch['id']}")
                    term_config = TerminalConfiguration.RSE
                    if self.config['device']['terminal_config'] == "DIFF":
                        term_config = TerminalConfiguration.DIFFERENTIAL
                    elif self.config['device']['terminal_config'] == "NRSE":
                        term_config = TerminalConfiguration.NRSE
                    self.task.ai_channels.add_ai_voltage_chan(
                        channel_name,
                        terminal_config=term_config,
                        min_val=-10.0, max_val=10.0)
 
            self.task.timing.cfg_samp_clk_timing(
                rate=self.config['device']['sampling_rate'],
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=self.config['device']['samples_per_channel'])
            self.task.start()
 
            buffer_size = int(
                self.config['graph'].get('time_window', 5.0) *
                self.config['device']['sampling_rate'])
            self.display_buffer = [
                collections.deque(maxlen=buffer_size) for _ in range(8)]
 
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start DAQ task:\n{e}")
 
    # ---------------------------------------------------------------------- #
    # [Fix 3] Hold/Resume: Hold 中もバッファを読み捨てる
    # ---------------------------------------------------------------------- #
    def update_plot(self):
        """グラフの更新（20 ms 周期）"""
 
        if self.is_paused:
            # Hold 中: NI-DAQmx の内部バッファが溢れないよう読み捨てる。
            # 表示バッファ・録画バッファへの書き込みは行わない。
            try:
                self.task.read(number_of_samples_per_channel=READ_ALL_AVAILABLE)
            except Exception:
                pass
            self.update_id = self.root.after(20, self.update_plot)
            return
 
        try:
            data = self.task.read(
                number_of_samples_per_channel=READ_ALL_AVAILABLE)
 
            if not data or (isinstance(data, list) and len(data[0]) == 0):
                self.update_id = self.root.after(20, self.update_plot)
                return
 
            if not isinstance(data[0], list):
                data = [[d] for d in data]
 
            num_new = len(data[0])
            active_ch_indices = [
                i for i, active in enumerate(self.active_channels) if active]
 
            for data_idx, ch_idx in enumerate(active_ch_indices):
                ch_config = self.config['channels'][ch_idx]
                converted_data = [
                    v * ch_config['conversion_factor'] for v in data[data_idx]]
                self.display_buffer[ch_idx].extend(converted_data)
                self.current_values[ch_idx] = converted_data[-1]
                self.value_labels[ch_idx].config(
                    text=f"{self.current_values[ch_idx]:+.3f} {ch_config['unit']}")
 
            if self.is_recording:
                for data_idx in range(len(active_ch_indices)):
                    self.recorded_data[data_idx].extend(data[data_idx])
                self.recording_count += num_new
                progress = min(
                    100,
                    int(self.recording_count / self.target_samples * 100))
                self.progress_label.config(
                    text=(f"Progress: {progress}% "
                          f"({self.recording_count}/{self.target_samples} samples)"))
                if self.recording_count >= self.target_samples:
                    self.finish_recording()
 
            self.update_counter += 1
            if self.update_counter >= self.draw_interval:
                self.update_counter = 0
                for ch_idx in active_ch_indices:
                    buf = self.display_buffer[ch_idx]
                    if buf:
                        time_data = np.linspace(
                            0, self.config['graph'].get('time_window', 5.0),
                            len(buf))
                        self.lines[ch_idx].set_data(time_data, list(buf))
                for ch_idx in range(8):
                    if not self.active_channels[ch_idx]:
                        self.lines[ch_idx].set_data([], [])
                self.canvas.draw_idle()
 
        except Exception as e:
            print(f"Error in update_plot: {e}")
 
        self.update_id = self.root.after(20, self.update_plot)
 
    # ---------------------------------------------------------------------- #
    def finish_recording(self):
        self.is_recording = False
        self.record_btn.config(state=tk.NORMAL)
        if not self.is_paused:
            self.status_label.config(text="Monitoring...", foreground='green')
        self.progress_label.config(text="")
        self.save_data()
 
    # ---------------------------------------------------------------------- #
    # [Fix 3] Hold / Resume
    # ---------------------------------------------------------------------- #
    def toggle_hold(self):
        """Hold と Resume を切り替える"""
        self.is_paused = not self.is_paused
 
        if self.is_paused:
            self.hold_btn.config(text="▶ Resume")
            self.status_label.config(text="Hold", foreground='orange')
        else:
            # Resume: 表示バッファをクリアして再スタート（古いデータが混入しない）
            for buf in self.display_buffer:
                buf.clear()
            self.hold_btn.config(text="⏸ Hold")
            self.status_label.config(text="Monitoring...", foreground='green')
 
    # ---------------------------------------------------------------------- #
    # データ保存
    # ---------------------------------------------------------------------- #
    def save_data(self):
        try:
            active_ch_indices = [
                i for i, active in enumerate(self.active_channels) if active]
            df_data = {}
            for data_idx, ch_idx in enumerate(active_ch_indices):
                ch_config = self.config['channels'][ch_idx]
                voltage_data = self.recorded_data[data_idx][:self.target_samples]
                df_data[f"{ch_config['name']}_V"] = voltage_data
                df_data[f"{ch_config['name']}_{ch_config['unit']}"] = [
                    v * ch_config['conversion_factor'] for v in voltage_data]
            df = pd.DataFrame(df_data)
            t_axis = [t / self.config['device']['sampling_rate']
                      for t in range(self.target_samples)]
            df.insert(0, "Time[s]", t_axis)
            df = df.round(6)
 
            save_dir = r"C:\PRG\data"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            now_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = os.path.join(save_dir, f"USB6002_Data_{now_str}.xlsx")
            df.to_excel(save_path, index=False)
            messagebox.showinfo("Success", f"Data saved successfully!\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data:\n{e}")
 
    def save_figure(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG Image (High-Res)", "*.png"),
                ("JPEG Image", "*.jpg"),
                ("TIFF Image", "*.tiff"),
                ("PDF Vector", "*.pdf"),
                ("SVG Vector", "*.svg")],
            initialfile=f"Figure_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        if filename:
            self.fig.savefig(filename, dpi=300, bbox_inches='tight',
                             facecolor='white', edgecolor='none')
            messagebox.showinfo("Success", f"Figure saved!\n{filename}")
 
    # ---------------------------------------------------------------------- #
    # 終了処理
    # ---------------------------------------------------------------------- #
    def cleanup(self):
        if self.update_id:
            self.root.after_cancel(self.update_id)
            self.update_id = None
        if self.task:
            try:
                self.task.stop()
                self.task.close()
            except Exception:
                pass
            self.task = None
 
    def on_closing(self):
        # ------------------------------------------------------------------ #
        # [Fix 1] active_channels を config に書き込んでから保存
        # ------------------------------------------------------------------ #
        self.config['active_channels'] = [
            var.get() for var in self.channel_vars]
 
        # チャンネル名・変換係数（メインパネルで直接編集された値）も反映
        for i in range(8):
            try:
                self.config['channels'][i]['name'] = \
                    self.channel_name_vars[i].get()
                self.config['channels'][i]['conversion_factor'] = \
                    self.channel_factor_vars[i].get()
            except Exception:
                pass
 
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")
 
        self.cleanup()
        self.root.quit()
        self.root.destroy()
 
 
# ========================================================================== #
def main():
    root = tk.Tk()
    app = DAQApplication(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
 
 
if __name__ == "__main__":
    main()

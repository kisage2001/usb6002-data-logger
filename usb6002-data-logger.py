"""
USB-6002 Data Acquisition System
High-performance data logger with real-time monitoring

Developer: Tsutsumi Hiroki
Institution: Tokyo National College of Technology
Version: 1.1
Date: 2025-05-25

Features:
- 8-channel simultaneous data acquisition
- Real-time visualization
- Physical quantity conversion
- Data recording (Excel output)
- Configuration management
- Hold/Resume functionality
- Enhanced graph copy/export functionality (right-click menu & buttons)
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
__version__ = "1.1"
__author__ = "Tsutsumi Hiroki"
__date__ = "2025-05-25"
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
        self.geometry("800x600")
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
        # スクロール可能なフレーム
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
        
        # チャンネル設定のヘッダー
        headers = ["CH", "Name", "Conversion Factor", "Unit", "Y Min", "Y Max"]
        for col, header in enumerate(headers):
            ttk.Label(scrollable_frame, text=header, font=('Arial', 10, 'bold')).grid(
                row=0, column=col, padx=5, pady=5, sticky=tk.W)
        
        # 一括変更用のフレーム（ヘッダーの下）
        bulk_frame = ttk.LabelFrame(scrollable_frame, text="Bulk Change (All Channels)", padding="5")
        bulk_frame.grid(row=1, column=0, columnspan=6, padx=5, pady=10, sticky=tk.EW)
        
        ttk.Label(bulk_frame, text="Conversion Factor:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.bulk_factor_var = tk.StringVar(value="")
        bulk_factor_entry = ttk.Entry(bulk_frame, textvariable=self.bulk_factor_var, width=15)
        bulk_factor_entry.grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(bulk_frame, text="Apply to All", 
                   command=self.apply_bulk_factor).grid(row=0, column=2, padx=5, pady=2)
        
        # チャンネル設定の入力フィールド
        self.channel_entries = []
        for i, ch in enumerate(config['channels']):
            row = i + 2  # 一括変更フレームの分だけ下にずらす
            
            # チャンネル番号
            ttk.Label(scrollable_frame, text=f"CH{ch['id']}").grid(
                row=row, column=0, padx=5, pady=2)
            
            # 名前
            name_var = tk.StringVar(value=ch['name'])
            name_entry = ttk.Entry(scrollable_frame, textvariable=name_var, width=20)
            name_entry.grid(row=row, column=1, padx=5, pady=2)
            
            # 変換係数
            factor_var = tk.DoubleVar(value=ch['conversion_factor'])
            factor_entry = ttk.Entry(scrollable_frame, textvariable=factor_var, width=15)
            factor_entry.grid(row=row, column=2, padx=5, pady=2)
            
            # 単位
            unit_var = tk.StringVar(value=ch['unit'])
            unit_entry = ttk.Entry(scrollable_frame, textvariable=unit_var, width=10)
            unit_entry.grid(row=row, column=3, padx=5, pady=2)
            
            # Y Min
            ymin_var = tk.DoubleVar(value=ch['y_min'])
            ymin_entry = ttk.Entry(scrollable_frame, textvariable=ymin_var, width=10)
            ymin_entry.grid(row=row, column=4, padx=5, pady=2)
            
            # Y Max
            ymax_var = tk.DoubleVar(value=ch['y_max'])
            ymax_entry = ttk.Entry(scrollable_frame, textvariable=ymax_var, width=10)
            ymax_entry.grid(row=row, column=5, padx=5, pady=2)
            
            self.channel_entries.append({
                'id': ch['id'],
                'name': name_var,
                'factor': factor_var,
                'unit': unit_var,
                'ymin': ymin_var,
                'ymax': ymax_var
            })
        
        # === グラフ設定タブの内容 ===
        # フォント設定フレーム
        font_frame = ttk.LabelFrame(graph_frame, text="Font Settings", padding="10")
        font_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)
        
        # フォントファミリー
        ttk.Label(font_frame, text="Font Family:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.font_family_var = tk.StringVar(value=config['graph'].get('font_family', 'Arial'))
        font_family_combo = ttk.Combobox(font_frame, textvariable=self.font_family_var, width=20)
        font_family_combo['values'] = ('Arial', 'Times New Roman', 'Helvetica', 'Courier New', 
                                        'Verdana', 'Georgia', 'Comic Sans MS', 'DejaVu Sans', 
                                        'Liberation Sans', 'Noto Sans')
        font_family_combo.grid(row=0, column=1, padx=5, pady=5)
        
        # タイトルフォントサイズ
        ttk.Label(font_frame, text="Title Font Size:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.title_fontsize_var = tk.IntVar(value=config['graph']['font_size_title'])
        title_fontsize_spin = ttk.Spinbox(font_frame, from_=8, to=32, textvariable=self.title_fontsize_var, width=10)
        title_fontsize_spin.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # ラベルフォントサイズ
        ttk.Label(font_frame, text="Axis Label Font Size:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.label_fontsize_var = tk.IntVar(value=config['graph']['font_size_label'])
        label_fontsize_spin = ttk.Spinbox(font_frame, from_=8, to=24, textvariable=self.label_fontsize_var, width=10)
        label_fontsize_spin.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 目盛りフォントサイズ
        ttk.Label(font_frame, text="Tick Label Font Size:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.tick_fontsize_var = tk.IntVar(value=config['graph']['font_size_tick'])
        tick_fontsize_spin = ttk.Spinbox(font_frame, from_=6, to=20, textvariable=self.tick_fontsize_var, width=10)
        tick_fontsize_spin.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 凡例フォントサイズ
        ttk.Label(font_frame, text="Legend Font Size:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.legend_fontsize_var = tk.IntVar(value=config['graph']['font_size_legend'])
        legend_fontsize_spin = ttk.Spinbox(font_frame, from_=6, to=20, textvariable=self.legend_fontsize_var, width=10)
        legend_fontsize_spin.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        
        # その他設定フレーム
        other_frame = ttk.LabelFrame(graph_frame, text="Other Settings", padding="10")
        other_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)
        
        # グラフタイトル
        ttk.Label(other_frame, text="Graph Title:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.graph_title_var = tk.StringVar(value=config['graph']['title'])
        title_entry = ttk.Entry(other_frame, textvariable=self.graph_title_var, width=40)
        title_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # X軸ラベル
        ttk.Label(other_frame, text="X-axis Label:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.xlabel_var = tk.StringVar(value=config['graph']['xlabel'])
        xlabel_entry = ttk.Entry(other_frame, textvariable=self.xlabel_var, width=40)
        xlabel_entry.grid(row=1, column=1, padx=5, pady=5)
        
        # グリッド表示
        ttk.Label(other_frame, text="Show Grid:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.grid_var = tk.BooleanVar(value=config['graph']['grid'])
        grid_check = ttk.Checkbutton(other_frame, variable=self.grid_var)
        grid_check.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 線の太さ
        ttk.Label(other_frame, text="Line Width:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.linewidth_var = tk.DoubleVar(value=config['graph']['line_width'])
        linewidth_spin = ttk.Spinbox(other_frame, from_=0.5, to=5.0, increment=0.5, 
                                      textvariable=self.linewidth_var, width=10)
        linewidth_spin.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="OK", command=self.ok_clicked).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.RIGHT)
        
    def apply_bulk_factor(self):
        """一括で変換係数を適用"""
        try:
            factor = float(self.bulk_factor_var.get())
            for entry in self.channel_entries:
                entry['factor'].set(factor)
            messagebox.showinfo("Success", f"Applied conversion factor {factor} to all channels")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number")
    
    def ok_clicked(self):
        """OK ボタンクリック"""
        try:
            # チャンネル設定の更新
            for i, entry in enumerate(self.channel_entries):
                self.config['channels'][i]['name'] = entry['name'].get()
                self.config['channels'][i]['conversion_factor'] = entry['factor'].get()
                self.config['channels'][i]['unit'] = entry['unit'].get()
                self.config['channels'][i]['y_min'] = entry['ymin'].get()
                self.config['channels'][i]['y_max'] = entry['ymax'].get()
            
            # グラフ設定の更新
            self.config['graph']['font_family'] = self.font_family_var.get()
            self.config['graph']['font_size_title'] = self.title_fontsize_var.get()
            self.config['graph']['font_size_label'] = self.label_fontsize_var.get()
            self.config['graph']['font_size_tick'] = self.tick_fontsize_var.get()
            self.config['graph']['font_size_legend'] = self.legend_fontsize_var.get()
            self.config['graph']['title'] = self.graph_title_var.get()
            self.config['graph']['xlabel'] = self.xlabel_var.get()
            self.config['graph']['grid'] = self.grid_var.get()
            self.config['graph']['line_width'] = self.linewidth_var.get()
            
            self.result = self.config
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input:\n{e}")
    
    def cancel_clicked(self):
        """Cancel ボタンクリック"""
        self.result = None
        self.destroy()


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
        self.legend = None  # 凡例オブジェクト
        
        # 描画最適化用カウンター
        self.update_counter = 0
        self.draw_interval = 2  # 2回に1回描画（描画頻度を半分に）
        
        # チャンネル設定用変数
        self.channel_name_vars = []
        self.channel_factor_vars = []
        
        # アクティブチャンネル（デフォルトで全チャンネル有効）
        self.active_channels = [True] * 8
        
        # 現在値の保持（変換済み値）
        self.current_values = [0.0] * 8
        
        # UIの構築
        self.create_widgets()
        self.setup_graph()
        
        # データ取得の開始
        self.start_task()
        self.update_plot()
        
    def load_config(self):
        """設定ファイルの読み込み"""
        default_config = {
            "device": {
                "device_name": "Dev1",
                "sampling_rate": 1000,
                "samples_per_channel": 100,
                "terminal_config": "RSE"
            },
            "channels": [
                {"id": 0, "name": "CH0", "conversion_factor": 1.0, "unit": "V", "y_min": -10, "y_max": 10},
                {"id": 1, "name": "CH1", "conversion_factor": 1.0, "unit": "V", "y_min": -10, "y_max": 10},
                {"id": 2, "name": "CH2", "conversion_factor": 1.0, "unit": "V", "y_min": -10, "y_max": 10},
                {"id": 3, "name": "CH3", "conversion_factor": 1.0, "unit": "V", "y_min": -10, "y_max": 10},
                {"id": 4, "name": "CH4", "conversion_factor": 1.0, "unit": "V", "y_min": -10, "y_max": 10},
                {"id": 5, "name": "CH5", "conversion_factor": 1.0, "unit": "V", "y_min": -10, "y_max": 10},
                {"id": 6, "name": "CH6", "conversion_factor": 1.0, "unit": "V", "y_min": -10, "y_max": 10},
                {"id": 7, "name": "CH7", "conversion_factor": 1.0, "unit": "V", "y_min": -10, "y_max": 10}
            ],
            "graph": {
                "title": "Real-time Monitoring",
                "xlabel": "Time [s]",
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
                    # デフォルト値とマージ（新しいキーに対応）
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
        else:
            return default_config
    
    def create_widgets(self):
        """UIコンポーネントの作成"""
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === 左側：コントロールパネル ===
        control_frame = ttk.Frame(main_frame, width=320)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 60))
        control_frame.pack_propagate(False)
        
        # ヘッダー
        header_frame = ttk.Frame(control_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="USB-6002 DAQ", 
                 font=('Arial', 16, 'bold')).pack()
        ttk.Label(header_frame, text=f"v{__version__}", 
                 font=('Arial', 9), foreground='gray').pack()
        
        # ステータス表示
        status_frame = ttk.LabelFrame(control_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Monitoring...", 
                                     font=('Arial', 12, 'bold'), foreground='green')
        self.status_label.pack()
        
        self.progress_label = ttk.Label(status_frame, text="", font=('Arial', 9))
        self.progress_label.pack()
        
        # コントロールボタン
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
        
        # グラフ操作ボタン（新規追加）
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
        
        # チャンネル選択
        channel_frame = ttk.LabelFrame(control_frame, text="Active Channels", padding="10")
        channel_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # スクロール可能なチャンネルリスト
        canvas = tk.Canvas(channel_frame, highlightthickness=0)
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
        
        # ヘッダー
        header_frame = ttk.Frame(scrollable_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(header_frame, text="On", font=('Arial', 9, 'bold'), width=3).grid(
            row=0, column=0, padx=2)
        ttk.Label(header_frame, text="Name", font=('Arial', 9, 'bold'), width=10).grid(
            row=0, column=1, padx=2)
        ttk.Label(header_frame, text="Factor", font=('Arial', 9, 'bold'), width=8).grid(
            row=0, column=2, padx=2)
        ttk.Label(header_frame, text="Current", font=('Arial', 9, 'bold'), width=12).grid(
            row=0, column=3, padx=2)
        
        self.channel_vars = []
        self.channel_name_vars = []
        self.channel_factor_vars = []
        self.value_labels = []
        
        for i, ch in enumerate(self.config['channels']):
            # チャンネル行のフレーム
            ch_row = ttk.Frame(scrollable_frame)
            ch_row.pack(fill=tk.X, pady=2)
            
            # チェックボックス
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(ch_row, variable=var,
                               command=self.update_active_channels, width=3)
            cb.grid(row=0, column=0, padx=2)
            self.channel_vars.append(var)
            
            # チャンネル名入力欄
            name_var = tk.StringVar(value=ch['name'])
            self.channel_name_vars.append(name_var)
            name_entry = ttk.Entry(ch_row, textvariable=name_var, width=10)
            name_entry.grid(row=0, column=1, padx=2)
            name_entry.bind('<Return>', lambda e, idx=i: self.update_channel_name(idx))
            name_entry.bind('<FocusOut>', lambda e, idx=i: self.update_channel_name(idx))
            
            # 変換係数入力欄
            factor_var = tk.DoubleVar(value=ch['conversion_factor'])
            self.channel_factor_vars.append(factor_var)
            factor_entry = ttk.Entry(ch_row, textvariable=factor_var, width=8)
            factor_entry.grid(row=0, column=2, padx=2)
            factor_entry.bind('<Return>', lambda e, idx=i: self.update_channel_factor(idx))
            factor_entry.bind('<FocusOut>', lambda e, idx=i: self.update_channel_factor(idx))
            
            # 現在値表示（カラーインジケータ付き）
            value_frame = ttk.Frame(ch_row)
            value_frame.grid(row=0, column=3, padx=2)
            
            # カラーインジケータ
            color_canvas = tk.Canvas(value_frame, width=10, height=10, 
                                    highlightthickness=0, bg=COLORS[i])
            color_canvas.pack(side=tk.LEFT, padx=(0, 3))
            
            # 値ラベル
            val_label = ttk.Label(value_frame, text=f"+0.000 {ch['unit']}", 
                                 font=('Courier', 9), foreground=COLORS[i])
            val_label.pack(side=tk.LEFT)
            self.value_labels.append(val_label)
        
        # === 右側：グラフ表示 ===
        self.graph_frame = ttk.Frame(main_frame)
        self.graph_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
    def setup_graph(self):
        """グラフの初期設定"""
        # フォント設定
        graph_cfg = self.config['graph']
        font_family = graph_cfg.get('font_family', 'Arial')
        
        plt.rcParams['font.family'] = font_family
        plt.rcParams['font.size'] = graph_cfg.get('font_size_tick', 10)
        
        # Figure作成（1つのグラフに全チャンネル重ねて表示）
        self.fig, self.ax = plt.subplots(figsize=(12, 7))
        
        # 描画の最適化設定
        self.fig.set_facecolor('white')
        self.ax.set_facecolor('white')
        
        # Y軸範囲の設定
        y_min = min([ch['y_min'] for ch in self.config['channels']])
        y_max = max([ch['y_max'] for ch in self.config['channels']])
        self.ax.set_ylim(y_min, y_max)
        
        # X軸範囲の設定
        self.ax.set_xlim(0, graph_cfg.get('time_window', 5.0))
        
        # 軸ラベル
        self.ax.set_xlabel(graph_cfg['xlabel'], 
                          fontsize=graph_cfg['font_size_label'],
                          fontweight='bold',
                          fontfamily=font_family)
        self.ax.set_ylabel('Voltage (V)', 
                          fontsize=graph_cfg['font_size_label'],
                          fontweight='bold',
                          fontfamily=font_family)
        
        # グリッド
        self.ax.grid(graph_cfg['grid'], alpha=0.3, linestyle='--', linewidth=0.8)
        
        # 四方を枠で囲む
        for spine in self.ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.5)
            spine.set_color('black')
        
        # 各チャンネルのライン（アニメーション最適化）
        self.lines = []
        for i, ch in enumerate(self.config['channels']):
            line, = self.ax.plot([], [], 
                               linewidth=graph_cfg['line_width'],
                               color=COLORS[i], 
                               label=ch['name'], 
                               alpha=0.8,
                               animated=False)  # animatedをFalseに設定
            self.lines.append(line)
        
        # 凡例
        self.update_legend()
        
        # タイトル
        self.ax.set_title(graph_cfg['title'], 
                         fontsize=graph_cfg['font_size_title'], 
                         fontweight='bold', 
                         fontfamily=font_family, 
                         pad=15)
        
        # レイアウト調整（グラフが左のコントロールパネルに隠れないよう余白を追加）
        self.fig.tight_layout(pad=2.0, rect=[0.02, 0, 1, 1])
        
        # Tkinter Canvasに埋め込み
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # ツールバーフレーム
        toolbar_frame = ttk.Frame(self.graph_frame)
        toolbar_frame.pack(fill=tk.X)
        
        # ツールバーの追加
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.update()
        
        # 右クリックメニューの設定
        self.setup_context_menu()
    
    def update_legend(self):
        """アクティブなチャンネルのみ凡例に表示"""
        if hasattr(self, 'legend') and self.legend:
            self.legend.remove()
        
        active_lines = []
        active_labels = []
        for i, ch in enumerate(self.config['channels']):
            if self.active_channels[i]:
                active_lines.append(self.lines[i])
                active_labels.append(ch['name'])
        
        if active_lines:
            graph_cfg = self.config['graph']
            font_family = graph_cfg.get('font_family', 'Arial')
            legend_pos = graph_cfg.get('legend_position', 'upper right')
            legend_cols = graph_cfg.get('legend_columns', 2)
            
            self.legend = self.ax.legend(active_lines, active_labels,
                                        loc=legend_pos, 
                                        fontsize=graph_cfg['font_size_legend'],
                                        prop={'family': font_family},
                                        framealpha=0.9, 
                                        edgecolor='black',
                                        ncol=min(legend_cols, len(active_lines)), 
                                        columnspacing=1.0)
        
    def setup_context_menu(self):
        """右クリックメニューの設定"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        
        # コピーサブメニュー
        copy_menu = tk.Menu(self.context_menu, tearoff=0)
        copy_menu.add_command(label="PNG (High Quality)", 
                             command=lambda: self.copy_to_clipboard('png'))
        copy_menu.add_command(label="JPEG (Compressed)", 
                             command=lambda: self.copy_to_clipboard('jpeg'))
        copy_menu.add_separator()
        copy_menu.add_command(label="PNG (Screen Quality)", 
                             command=lambda: self.copy_to_clipboard('png', dpi=100))
        
        self.context_menu.add_cascade(label="📋 Copy as...", menu=copy_menu)
        
        # 保存サブメニュー
        save_menu = tk.Menu(self.context_menu, tearoff=0)
        save_menu.add_command(label="PNG (High-Res)", 
                             command=lambda: self.save_figure_format('png'))
        save_menu.add_command(label="JPEG", 
                             command=lambda: self.save_figure_format('jpeg'))
        save_menu.add_command(label="TIFF", 
                             command=lambda: self.save_figure_format('tiff'))
        save_menu.add_command(label="PDF (Vector)", 
                             command=lambda: self.save_figure_format('pdf'))
        save_menu.add_command(label="SVG (Vector)", 
                             command=lambda: self.save_figure_format('svg'))
        
        self.context_menu.add_cascade(label="💾 Save as...", menu=save_menu)
        
        # 右クリックイベントのバインド
        self.canvas.get_tk_widget().bind("<Button-3>", self.show_context_menu)
        
    def show_context_menu(self, event):
        """右クリックメニューの表示"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
    
    def copy_to_clipboard(self, format='png', dpi=150):
        """グラフをクリップボードにコピー"""
        try:
            # 一時的に画面を更新
            self.canvas.draw()
            self.root.update()
            
            # メモリ上の画像として保存
            buf = io.BytesIO()
            self.fig.savefig(buf, format=format, dpi=dpi, bbox_inches='tight',
                           facecolor='white', edgecolor='none')
            buf.seek(0)
            
            # PIL Imageとして読み込み
            img = Image.open(buf)
            
            # クリップボードにコピー
            try:
                import win32clipboard
                output = io.BytesIO()
                img.convert('RGB').save(output, 'BMP')
                data = output.getvalue()[14:]  # BMPヘッダーを除去
                output.close()
                
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                win32clipboard.CloseClipboard()
                
                messagebox.showinfo("Success", f"Graph copied to clipboard as {format.upper()}!")
            except ImportError:
                # win32clipboardが使えない場合はPILのgrabを試す
                img_temp = img.copy()
                img_temp.save('temp_clipboard.png')
                from PIL import ImageGrab
                img_loaded = Image.open('temp_clipboard.png')
                # ここでクリップボードにコピー
                messagebox.showinfo("Info", 
                    "pywin32 module recommended for clipboard functionality.\n"
                    "Install with: pip install pywin32")
            
            buf.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard:\n{e}")
    
    def save_figure_format(self, format):
        """指定形式でグラフを保存"""
        format_extensions = {
            'png': [("PNG Image", "*.png")],
            'jpeg': [("JPEG Image", "*.jpg"), ("JPEG Image", "*.jpeg")],
            'tiff': [("TIFF Image", "*.tiff"), ("TIFF Image", "*.tif")],
            'pdf': [("PDF Document", "*.pdf")],
            'svg': [("SVG Vector", "*.svg")]
        }
        
        default_ext = {
            'png': '.png',
            'jpeg': '.jpg',
            'tiff': '.tiff',
            'pdf': '.pdf',
            'svg': '.svg'
        }
        
        filename = filedialog.asksaveasfilename(
            defaultextension=default_ext[format],
            filetypes=format_extensions[format],
            initialfile=f"Figure_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        if filename:
            dpi = 300 if format in ['png', 'jpeg', 'tiff'] else None
            self.fig.savefig(filename, dpi=dpi, bbox_inches='tight', 
                           facecolor='white', edgecolor='none')
            messagebox.showinfo("Success", f"Figure saved!\n{filename}")
    
    def quick_export_menu(self):
        """クイックエクスポートメニュー"""
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
        
        # ボタンの位置にメニューを表示
        btn = self.root.nametowidget(self.root.focus_get())
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        menu.tk_popup(x, y)
    
    def clear_all_data(self):
        """全チャンネルのデータを初期化"""
        # 確認ダイアログ
        result = messagebox.askyesno("Confirm", 
                                    "Clear all channel data?\nThis will reset all graph data.",
                                    icon='warning')
        if not result:
            return
        
        try:
            # 全チャンネルのバッファをクリア
            for i in range(8):
                self.display_buffer[i].clear()
                self.lines[i].set_data([], [])
                self.current_values[i] = 0.0
                self.value_labels[i].config(
                    text=f"+0.000 {self.config['channels'][i]['unit']}")
            
            # グラフを再描画
            self.canvas.draw_idle()
            
            messagebox.showinfo("Success", "All channel data has been cleared.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear data:\n{e}")
    
    def update_channel_name(self, channel_idx):
        """チャンネル名を更新"""
        new_name = self.channel_name_vars[channel_idx].get()
        self.config['channels'][channel_idx]['name'] = new_name
        
        # ラインのラベルを更新
        self.lines[channel_idx].set_label(new_name)
        
        # 凡例を更新
        self.update_legend()
        self.canvas.draw_idle()
    
    def update_channel_factor(self, channel_idx):
        """変換係数を更新"""
        try:
            new_factor = self.channel_factor_vars[channel_idx].get()
            self.config['channels'][channel_idx]['conversion_factor'] = new_factor
        except tk.TclError:
            # 無効な値の場合は元に戻す
            self.channel_factor_vars[channel_idx].set(
                self.config['channels'][channel_idx]['conversion_factor'])
    
    def update_active_channels(self):
        """アクティブチャンネルの更新"""
        self.active_channels = [var.get() for var in self.channel_vars]
        
        # 非アクティブなチャンネルを薄く表示
        for i, active in enumerate(self.active_channels):
            if active:
                self.lines[i].set_alpha(0.8)
            else:
                self.lines[i].set_alpha(0.1)
        
        # 凡例を更新
        self.update_legend()
        self.canvas.draw_idle()
        
    def open_settings(self):
        """設定ダイアログを開く"""
        editor = ConfigEditor(self.root, self.config)
        self.root.wait_window(editor)
        
        if editor.result:
            self.config = editor.result
            # グラフの再構築
            self.canvas.get_tk_widget().destroy()
            self.setup_graph()
            
    def start_recording(self):
        """データ録画開始"""
        # 録画時間の入力
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
                
                self.target_samples = int(duration * self.config['device']['sampling_rate'])
                self.recording_count = 0
                
                # 録画バッファの初期化
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
        
    def start_task(self):
        """データ取得タスクの開始"""
        try:
            self.task = nidaqmx.Task()
            
            # アクティブなチャンネルを追加
            for i, (ch, active) in enumerate(zip(self.config['channels'], self.active_channels)):
                if active:
                    channel_name = f"{self.config['device']['device_name']}/ai{ch['id']}"
                    
                    # Terminal Configuration
                    term_config = TerminalConfiguration.RSE
                    if self.config['device']['terminal_config'] == "DIFF":
                        term_config = TerminalConfiguration.DIFFERENTIAL
                    elif self.config['device']['terminal_config'] == "NRSE":
                        term_config = TerminalConfiguration.NRSE
                    
                    self.task.ai_channels.add_ai_voltage_chan(
                        channel_name,
                        terminal_config=term_config,
                        min_val=-10.0,
                        max_val=10.0
                    )
            
            # サンプリング設定
            self.task.timing.cfg_samp_clk_timing(
                rate=self.config['device']['sampling_rate'],
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=self.config['device']['samples_per_channel']
            )
            
            self.task.start()
            
            # 表示用バッファ（物理量変換後の値を保持）
            buffer_size = int(self.config['graph'].get('time_window', 5.0) * 
                            self.config['device']['sampling_rate'])
            self.display_buffer = [collections.deque(maxlen=buffer_size) for _ in range(8)]
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start DAQ task:\n{e}")
            
    def update_plot(self):
        """グラフの更新（20ms周期）"""
        if self.is_paused:
            self.update_id = self.root.after(20, self.update_plot)
            return
        
        try:
            data = self.task.read(number_of_samples_per_channel=READ_ALL_AVAILABLE)
            
            if not data or (isinstance(data, list) and len(data[0]) == 0):
                self.update_id = self.root.after(20, self.update_plot)
                return
            
            # データの整形
            if not isinstance(data[0], list):
                data = [[d] for d in data]
            
            num_new = len(data[0])
            active_ch_indices = [i for i, active in enumerate(self.active_channels) if active]
            
            # 表示バッファの更新（物理量変換）- アクティブなチャンネルのみ
            for data_idx, ch_idx in enumerate(active_ch_indices):
                ch_config = self.config['channels'][ch_idx]
                # 電圧値を物理量に変換
                converted_data = [v * ch_config['conversion_factor'] for v in data[data_idx]]
                
                self.display_buffer[ch_idx].extend(converted_data)
                
                # 現在値更新（変換済み値）
                self.current_values[ch_idx] = converted_data[-1]
                self.value_labels[ch_idx].config(
                    text=f"{self.current_values[ch_idx]:+.3f} {ch_config['unit']}")
            
            # 録画中の処理（元の電圧値を記録）
            if self.is_recording:
                for data_idx in range(len(active_ch_indices)):
                    self.recorded_data[data_idx].extend(data[data_idx])
                
                self.recording_count += num_new
                progress = min(100, int(self.recording_count / self.target_samples * 100))
                self.progress_label.config(
                    text=f"Progress: {progress}% ({self.recording_count}/{self.target_samples} samples)")
                
                if self.recording_count >= self.target_samples:
                    self.finish_recording()
            
            # 描画の間引き（draw_interval回に1回だけ描画）
            self.update_counter += 1
            if self.update_counter >= self.draw_interval:
                self.update_counter = 0
                
                # グラフデータの更新 - アクティブなチャンネルのみ
                for ch_idx in active_ch_indices:
                    current_buffer_size = len(self.display_buffer[ch_idx])
                    if current_buffer_size > 0:
                        time_data = np.linspace(0, self.config['graph'].get('time_window', 5.0), 
                                              current_buffer_size)
                        self.lines[ch_idx].set_data(time_data, list(self.display_buffer[ch_idx]))
                
                # 非アクティブなチャンネルは空データを設定
                for ch_idx in range(8):
                    if not self.active_channels[ch_idx]:
                        self.lines[ch_idx].set_data([], [])
                
                # 描画の最適化：draw_idle()を使用
                self.canvas.draw_idle()
            
        except Exception as e:
            print(f"Error in update_plot: {e}")
        
        self.update_id = self.root.after(20, self.update_plot)
        
    def finish_recording(self):
        """録画完了処理"""
        self.is_recording = False
        self.record_btn.config(state=tk.NORMAL)
        # Hold中でなければMonitoringに戻す
        if not self.is_paused:
            self.status_label.config(text="Monitoring...", foreground='green')
        self.progress_label.config(text="")
        self.save_data()
    
    def toggle_hold(self):
        """Hold/Resume切り替え"""
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            # Hold状態
            self.hold_btn.config(text="▶ Resume")
            self.status_label.config(text="Hold", foreground='red')
        else:
            # Resume状態
            self.hold_btn.config(text="⏸ Hold")
            self.status_label.config(text="Monitoring...", foreground='green')
        
    def save_data(self):
        """データをExcelに保存（電圧値と物理量の両方）"""
        try:
            active_ch_indices = [i for i, active in enumerate(self.active_channels) if active]
            
            df_data = {}
            for data_idx, ch_idx in enumerate(active_ch_indices):
                ch_config = self.config['channels'][ch_idx]
                voltage_data = self.recorded_data[data_idx][:self.target_samples]
                
                # 電圧値（生データ）
                df_data[f"{ch_config['name']}_V"] = voltage_data
                
                # 物理量（変換済み）
                converted_data = [v * ch_config['conversion_factor'] for v in voltage_data]
                df_data[f"{ch_config['name']}_{ch_config['unit']}"] = converted_data
            
            df = pd.DataFrame(df_data)
            
            # 時間軸
            t_axis = [t/self.config['device']['sampling_rate'] for t in range(self.target_samples)]
            df.insert(0, "Time[s]", t_axis)
            df = df.round(6)
            
            # ファイル名（C:\PRG\data に保存）
            now_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            save_dir = r"C:\PRG\data"
            
            # data フォルダがなければ作成
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            
            save_path = os.path.join(save_dir, f"USB6002_Data_{now_str}.xlsx")
            
            df.to_excel(save_path, index=False)
            messagebox.showinfo("Success", f"Data saved successfully!\n{save_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data:\n{e}")
            
    def save_figure(self):
        """グラフを高解像度で保存（インタラクティブ形式選択）"""
        filetypes = [
            ("PNG Image (High-Res)", "*.png"),
            ("JPEG Image", "*.jpg"),
            ("TIFF Image", "*.tiff"),
            ("PDF Vector", "*.pdf"),
            ("SVG Vector", "*.svg")
        ]
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=filetypes,
            initialfile=f"Figure_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        if filename:
            self.fig.savefig(filename, dpi=300, bbox_inches='tight', 
                           facecolor='white', edgecolor='none')
            messagebox.showinfo("Success", f"Figure saved!\n{filename}")
            
    def cleanup(self):
        """リソースのクリーンアップ"""
        if self.update_id:
            self.root.after_cancel(self.update_id)
            self.update_id = None
            
        if self.task:
            try:
                self.task.stop()
                self.task.close()
            except:
                pass
            self.task = None
        
    def on_closing(self):
        """ウィンドウを閉じる時の処理"""
        # 設定を自動保存
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")
        
        # リソースのクリーンアップ
        self.cleanup()
        
        # Tkinterを正常に終了（sys.exit()を使わない）
        self.root.quit()  # mainloopを終了
        self.root.destroy()  # ウィンドウを破棄

def main():
    root = tk.Tk()
    app = DAQApplication(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()

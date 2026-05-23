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
from PIL import Image, ImageGrab
import io

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
        
        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Save", command=self.save_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        
        # ウィンドウが閉じられる時も設定を保存
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def apply_bulk_factor(self):
        """全チャンネルに係数を一括適用"""
        try:
            bulk_value = float(self.bulk_factor_var.get())
            for entry in self.channel_entries:
                entry['factor'].set(bulk_value)
            messagebox.showinfo("Success", f"Applied conversion factor {bulk_value} to all channels!")
        except ValueError:
            messagebox.showerror("Error", "Invalid conversion factor value!")
    
    def on_closing(self):
        """ウィンドウを閉じる時の処理（設定を保存してから閉じる）"""
        try:
            # チャンネル設定を更新
            for i, entry in enumerate(self.channel_entries):
                self.config['channels'][i]['name'] = entry['name'].get()
                self.config['channels'][i]['conversion_factor'] = entry['factor'].get()
                self.config['channels'][i]['unit'] = entry['unit'].get()
                self.config['channels'][i]['y_min'] = entry['ymin'].get()
                self.config['channels'][i]['y_max'] = entry['ymax'].get()
            
            self.result = self.config
        except:
            pass
        
        self.destroy()
        
    def save_config(self):
        """設定を保存"""
        try:
            # チャンネル設定を更新
            for i, entry in enumerate(self.channel_entries):
                self.config['channels'][i]['name'] = entry['name'].get()
                self.config['channels'][i]['conversion_factor'] = entry['factor'].get()
                self.config['channels'][i]['unit'] = entry['unit'].get()
                self.config['channels'][i]['y_min'] = entry['ymin'].get()
                self.config['channels'][i]['y_max'] = entry['ymax'].get()
            
            self.result = self.config
            self.destroy()
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid value: {e}")

class DAQApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("USB-6002 Data Acquisition System - Configurable")
        self.root.geometry("1400x900")
        
        # 設定の読み込み
        self.config = self.load_config()
        
        # 状態管理
        self.is_recording = False
        self.task = None
        self.active_channels = [ch['enabled'] for ch in self.config['channels']]
        self.record_duration = tk.DoubleVar(value=self.config['device']['default_duration'])
        self.recording_count = 0
        self.target_samples = 0
        self.recorded_data = []
        self.update_id = None
        
        # データバッファ
        num_channels = len(self.config['channels'])
        display_samples = int(self.config['device']['sampling_rate'] * 
                             self.config['device']['display_window'])
        self.display_buffer = [collections.deque([0.0]*display_samples, maxlen=display_samples) 
                              for _ in range(num_channels)]
        self.current_values = [0.0] * num_channels
        
        # UI構築
        self.setup_ui()
        
        # 起動時に自動的にモニタリング開始
        self.root.after(500, self.auto_start_monitoring)
        
    def load_config(self):
        """設定ファイルを読み込み"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                messagebox.showwarning("Warning", f"Failed to load config: {e}\nUsing default settings.")
        
        # デフォルト設定を作成して保存
        config = self.get_default_config()
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"Created default config file: {CONFIG_FILE}")
        except Exception as e:
            print(f"Warning: Failed to save default config: {e}")
        
        return config
    
    def save_config(self):
        """設定ファイルを保存"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Success", "Configuration saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")
    
    def get_default_config(self):
        """デフォルト設定を返す"""
        return {
            "device": {
                "name": "Dev1",
                "sampling_rate": 1000,
                "display_window": 5.0,
                "default_duration": 10.0
            },
            "channels": [
                {
                    "id": i,
                    "name": f"CH{i}",
                    "enabled": True,
                    "conversion_factor": 1.0,
                    "unit": "V",
                    "y_min": -10.0,
                    "y_max": 10.0
                } for i in range(8)
            ],
            "graph": {
                "title": "Real-time Data Acquisition - USB-6002",
                "font_size_title": 16,
                "font_size_label": 14,
                "font_size_tick": 12,
                "font_size_legend": 11,
                "grid_style": ":",
                "legend_position": "upper right",
                "legend_columns": 4
            }
        }
    
    def open_config_editor(self):
        """設定エディタを開く"""
        editor = ConfigEditor(self.root, self.config.copy())
        self.root.wait_window(editor)
        
        if editor.result:
            self.config = editor.result
            # 設定をファイルに保存
            try:
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save config: {e}")
            messagebox.showinfo("Info", "Configuration updated!\nPlease restart the application for changes to take effect.")
    
    def setup_ui(self):
        """UIのセットアップ"""
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 左側：コントロールパネル
        control_frame = ttk.LabelFrame(main_frame, text="Control Panel", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 設定ボタン
        ttk.Button(control_frame, text="⚙ Edit Configuration", 
                  command=self.open_config_editor).grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # チャンネル選択
        channels_frame = ttk.LabelFrame(control_frame, text="Active Channels", padding="10")
        channels_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # ヘッダー
        ttk.Label(channels_frame, text="Active", font=('Arial', 9, 'bold')).grid(
            row=0, column=0, padx=5, pady=2)
        ttk.Label(channels_frame, text="Name", font=('Arial', 9, 'bold')).grid(
            row=0, column=1, padx=5, pady=2)
        ttk.Label(channels_frame, text="Factor", font=('Arial', 9, 'bold')).grid(
            row=0, column=2, padx=5, pady=2)
        ttk.Label(channels_frame, text="Current Value", font=('Arial', 9, 'bold')).grid(
            row=0, column=3, padx=5, pady=2)
        
        self.channel_vars = []
        self.channel_checkbuttons = []
        self.channel_name_vars = []
        self.channel_name_entries = []
        self.channel_factor_vars = []
        self.channel_factor_entries = []
        self.value_labels = []
        
        for i, ch in enumerate(self.config['channels']):
            row = i + 1
            
            # チェックボックス
            var = tk.BooleanVar(value=ch['enabled'])
            self.channel_vars.append(var)
            cb = ttk.Checkbutton(
                channels_frame, 
                variable=var,
                command=lambda idx=i: self.toggle_channel(idx)
            )
            cb.grid(row=row, column=0, pady=2)
            self.channel_checkbuttons.append(cb)
            
            # チャンネル名入力欄
            name_var = tk.StringVar(value=ch['name'])
            self.channel_name_vars.append(name_var)
            name_entry = ttk.Entry(channels_frame, textvariable=name_var, width=15)
            name_entry.grid(row=row, column=1, padx=2, pady=2)
            name_entry.bind('<Return>', lambda e, idx=i: self.update_channel_name(idx))
            name_entry.bind('<FocusOut>', lambda e, idx=i: self.update_channel_name(idx))
            self.channel_name_entries.append(name_entry)
            
            # 変換係数入力欄
            factor_var = tk.DoubleVar(value=ch['conversion_factor'])
            self.channel_factor_vars.append(factor_var)
            factor_entry = ttk.Entry(channels_frame, textvariable=factor_var, width=8)
            factor_entry.grid(row=row, column=2, padx=2, pady=2)
            factor_entry.bind('<Return>', lambda e, idx=i: self.update_channel_factor(idx))
            factor_entry.bind('<FocusOut>', lambda e, idx=i: self.update_channel_factor(idx))
            self.channel_factor_entries.append(factor_entry)
            
            # 現在値表示
            value_label = ttk.Label(channels_frame, text="0.000 " + ch['unit'], width=12,
                                   foreground=COLORS[i], font=('Arial', 9, 'bold'))
            value_label.grid(row=row, column=3, padx=5, pady=2)
            self.value_labels.append(value_label)
        
        # 測定時間設定
        duration_frame = ttk.LabelFrame(control_frame, text="Recording Duration", padding="10")
        duration_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(duration_frame, text="Duration (s):").grid(row=0, column=0, sticky=tk.W)
        duration_entry = ttk.Entry(duration_frame, textvariable=self.record_duration, width=10)
        duration_entry.grid(row=0, column=1, padx=5)
        
        # 表示時間軸設定
        display_frame = ttk.LabelFrame(control_frame, text="Display Settings", padding="10")
        display_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        
        # 時間軸の最大幅
        ttk.Label(display_frame, text="Time Window (s):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.display_window_var = tk.DoubleVar(value=self.config['device']['display_window'])
        display_window_entry = ttk.Entry(display_frame, textvariable=self.display_window_var, width=10)
        display_window_entry.grid(row=0, column=1, padx=5, pady=2)
        display_window_entry.bind('<Return>', self.update_display_window)
        
        # 縦軸ラベル
        ttk.Label(display_frame, text="Y-axis Label:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.ylabel_var = tk.StringVar(value="Voltage (V)")
        ylabel_entry = ttk.Entry(display_frame, textvariable=self.ylabel_var, width=15)
        ylabel_entry.grid(row=1, column=1, padx=5, pady=2)
        ylabel_entry.bind('<Return>', self.update_ylabel)
        ylabel_entry.bind('<FocusOut>', self.update_ylabel)
        
        # コントロールボタン
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)
        
        self.record_btn = ttk.Button(button_frame, text="🔴 Start Recording", 
                                     command=self.start_recording)
        self.record_btn.grid(row=0, column=0, pady=5, sticky=(tk.W, tk.E))
        self.record_btn.config(width=20)
        
        # ステータス表示
        status_frame = ttk.LabelFrame(control_frame, text="Status", padding="10")
        status_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=10)
        
        self.status_label = ttk.Label(status_frame, text="Monitoring...", 
                                      font=('Arial', 10, 'bold'), foreground='green')
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        self.progress_label = ttk.Label(status_frame, text="")
        self.progress_label.grid(row=1, column=0, sticky=tk.W)
        
        # 右側：グラフエリア
        graph_frame = ttk.Frame(main_frame)
        graph_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 論文用高品質グラフ
        self.setup_plot(graph_frame)
        
        # ウィンドウのリサイズ設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
    def setup_plot(self, parent):
        """論文品質のグラフをセットアップ"""
        graph_cfg = self.config['graph']
        
        # 図のサイズとDPI
        self.fig, self.ax = plt.subplots(figsize=(10, 6), dpi=100)
        
        # フォント設定
        plt.rcParams['font.family'] = 'serif'
        plt.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif', 'Liberation Serif']
        plt.rcParams['mathtext.fontset'] = 'stix'
        
        # 軸ラベル（最初のアクティブなチャンネルの単位を使用、または共通単位）
        self.ax.set_xlabel('Time (s)', fontsize=graph_cfg['font_size_label'], fontweight='bold')
        
        # 縦軸ラベル（複数単位がある場合は"Mixed Units"、単一なら単位表示）
        units = set(ch['unit'] for ch in self.config['channels'] if ch['enabled'])
        if len(units) == 1:
            ylabel = f"Value ({list(units)[0]})"
        else:
            ylabel = "Value (Mixed Units)"
        self.ax.set_ylabel(ylabel, fontsize=graph_cfg['font_size_label'], fontweight='bold')
        
        # 軸範囲（最初のアクティブチャンネルの範囲を使用）
        active_ch = next((ch for ch in self.config['channels'] if ch['enabled']), self.config['channels'][0])
        self.ax.set_xlim(0, self.config['device']['display_window'])
        self.ax.set_ylim(active_ch['y_min'], active_ch['y_max'])
        
        # グリッド線
        self.ax.grid(True, alpha=0.4, linestyle=graph_cfg['grid_style'], 
                    linewidth=1.0, color='gray')
        
        # 軸の設定
        self.ax.tick_params(axis='both', which='major', 
                           labelsize=graph_cfg['font_size_tick'], width=1.5, length=6)
        
        # 四方を枠で囲む
        for spine in self.ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.5)
            spine.set_color('black')
        
        # 時間軸
        display_samples = int(self.config['device']['sampling_rate'] * 
                             self.config['device']['display_window'])
        self.time_axis = np.linspace(0, self.config['device']['display_window'], display_samples)
        
        # 各チャンネルのライン
        self.lines = []
        for i, ch in enumerate(self.config['channels']):
            line, = self.ax.plot([], [], lw=1.5, color=COLORS[i], 
                               label=ch['name'], alpha=0.8)
            self.lines.append(line)
        
        # 凡例
        self.update_legend()
        
        # タイトル
        self.ax.set_title(graph_cfg['title'], 
                         fontsize=graph_cfg['font_size_title'], fontweight='bold', pad=15)
        
        # Matplotlibキャンバス
        self.canvas = FigureCanvasTkAgg(self.fig, parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # ツールバー
        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.pack(fill=tk.X)
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.update()
        
        # 保存ボタン
        save_btn = ttk.Button(toolbar_frame, text="💾 Save Figure (High-Res)", 
                             command=self.save_figure)
        save_btn.pack(side=tk.RIGHT, padx=5)
        
        # スクリーンショットボタン
        screenshot_btn = ttk.Button(toolbar_frame, text="📸 Screenshot to Clipboard", 
                                   command=self.screenshot_to_clipboard)
        screenshot_btn.pack(side=tk.RIGHT, padx=5)
        
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
    
    def update_display_window(self, event=None):
        """表示時間軸の幅を更新"""
        try:
            new_window = self.display_window_var.get()
            if new_window > 0:
                self.config['device']['display_window'] = new_window
                
                # グラフの時間軸を更新
                self.ax.set_xlim(0, new_window)
                
                # 時間軸配列を再生成
                display_samples = int(self.config['device']['sampling_rate'] * new_window)
                self.time_axis = np.linspace(0, new_window, display_samples)
                
                # バッファサイズを変更
                for i in range(len(self.config['channels'])):
                    old_data = list(self.display_buffer[i])
                    self.display_buffer[i] = collections.deque(
                        [0.0] * display_samples, maxlen=display_samples)
                    # 既存データを可能な限り保持
                    if old_data:
                        self.display_buffer[i].extend(old_data[-display_samples:])
                
                self.canvas.draw_idle()
        except tk.TclError:
            # 無効な値の場合は元に戻す
            self.display_window_var.set(self.config['device']['display_window'])
    
    def update_ylabel(self, event=None):
        """縦軸ラベルを更新"""
        new_label = self.ylabel_var.get()
        self.ax.set_ylabel(new_label, fontsize=self.config['graph']['font_size_label'], 
                          fontweight='bold')
        self.canvas.draw_idle()
    
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
            self.legend = self.ax.legend(active_lines, active_labels,
                                        loc=graph_cfg['legend_position'], 
                                        fontsize=graph_cfg['font_size_legend'], 
                                        framealpha=0.9, edgecolor='black',
                                        ncol=min(graph_cfg['legend_columns'], len(active_lines)), 
                                        columnspacing=1.0)
        
    def toggle_channel(self, channel_idx):
        """チャンネルのON/OFF切り替え"""
        self.active_channels[channel_idx] = self.channel_vars[channel_idx].get()
        
        if self.active_channels[channel_idx]:
            self.lines[channel_idx].set_alpha(0.8)
        else:
            self.lines[channel_idx].set_alpha(0.1)
        
        self.update_legend()
        self.canvas.draw_idle()
        
    def auto_start_monitoring(self):
        """起動時に自動的にモニタリング開始"""
        try:
            active_ch_indices = [i for i, active in enumerate(self.active_channels) if active]
            if not active_ch_indices:
                messagebox.showwarning("Warning", "At least one channel must be active!")
                return
            
            self.task = nidaqmx.Task()
            for ch_idx in active_ch_indices:
                self.task.ai_channels.add_ai_voltage_chan(
                    f"{self.config['device']['name']}/ai{ch_idx}",
                    terminal_config=TerminalConfiguration.RSE,
                    min_val=-10.0, max_val=10.0
                )
            
            self.task.timing.cfg_samp_clk_timing(
                rate=self.config['device']['sampling_rate'],
                sample_mode=AcquisitionType.CONTINUOUS
            )
            self.task.start()
            
            self.status_label.config(text="Monitoring...", foreground='green')
            self.update_plot()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start monitoring:\n{e}")
            self.status_label.config(text="Error - Device not found", foreground='red')
            
    def start_recording(self):
        """録画開始"""
        try:
            duration = self.record_duration.get()
            if duration <= 0:
                messagebox.showwarning("Warning", "Duration must be greater than 0!")
                return
            
            self.is_recording = True
            self.recording_count = 0
            self.target_samples = int(self.config['device']['sampling_rate'] * duration)
            
            active_ch_indices = [i for i, active in enumerate(self.active_channels) if active]
            self.recorded_data = [[] for _ in active_ch_indices]
            
            self.record_btn.config(state=tk.DISABLED)
            self.status_label.config(text="🔴 Recording...", foreground='red')
            
        except ValueError:
            messagebox.showwarning("Warning", "Invalid duration value!")
            
    def update_plot(self):
        """プロット更新"""
        if not self.task:
            return
        
        try:
            data = self.task.read(number_of_samples_per_channel=READ_ALL_AVAILABLE)
            
            if len(data) == 0 or (isinstance(data[0], list) and len(data[0]) == 0):
                self.update_id = self.root.after(20, self.update_plot)
                return
            
            if not isinstance(data[0], list):
                data = [data]
            
            num_new = len(data[0])
            active_ch_indices = [i for i, active in enumerate(self.active_channels) if active]
            
            # 表示バッファの更新（物理量変換）
            for data_idx, ch_idx in enumerate(active_ch_indices):
                ch_config = self.config['channels'][ch_idx]
                # 電圧値を物理量に変換
                converted_data = [v * ch_config['conversion_factor'] for v in data[data_idx]]
                
                self.display_buffer[ch_idx].extend(converted_data)
                self.lines[ch_idx].set_data(self.time_axis, list(self.display_buffer[ch_idx]))
                
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
            
            self.canvas.draw_idle()
            
        except Exception as e:
            print(f"Error in update_plot: {e}")
        
        self.update_id = self.root.after(20, self.update_plot)
        
    def finish_recording(self):
        """録画完了処理"""
        self.is_recording = False
        self.record_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Monitoring...", foreground='green')
        self.progress_label.config(text="")
        self.save_data()
        
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
        """グラフを高解像度で保存"""
        filetypes = [
            ("PNG Image (High-Res)", "*.png"),
            ("PDF Vector", "*.pdf"),
            ("SVG Vector", "*.svg"),
            ("TIFF Image", "*.tiff")
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
    
    def screenshot_to_clipboard(self):
        """画面をスクリーンショットしてクリップボードにコピー"""
        try:
            # 一時的に画面を更新
            self.canvas.draw()
            self.root.update()
            
            # Figureをメモリ上の画像として保存
            buf = io.BytesIO()
            self.fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                           facecolor='white', edgecolor='none')
            buf.seek(0)
            
            # PIL Imageとして読み込み
            img = Image.open(buf)
            
            # クリップボードにコピー（Windows）
            output = io.BytesIO()
            img.convert('RGB').save(output, 'BMP')
            data = output.getvalue()[14:]  # BMPヘッダーを除去
            output.close()
            
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            
            buf.close()
            
            messagebox.showinfo("Success", "Screenshot copied to clipboard!")
            
        except ImportError:
            # win32clipboardが使えない場合の代替処理
            messagebox.showerror("Error", 
                               "pywin32 module is required for clipboard functionality.\n"
                               "Please install it with: pip install pywin32")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy screenshot:\n{e}")
            
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

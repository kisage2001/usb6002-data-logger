# usb6002-data-logger
NI USB-6002 Data Acquisition System with real-time monitoring

## 機能
- 8チャンネル同時モニタリング
- リアルタイムグラフ表示
- データ記録（Excel形式）
- 変換係数設定（電圧→物理量）
- スクリーンショット機能
- 設定の保存・読込

## 必要な環境
- Python 3.8以上
- NI USB-6002
- NI-DAQmx

## インストール
```bash
pip install nidaqmx matplotlib pandas numpy pillow pywin32 openpyxl
```

## 使い方
```bash
python usb6002_configurable.py
```

## 設定
初回起動時に`config.json`が自動生成されます。

https://github.com/kisage2001/usb6002-data-logger/blob/main/Image.png

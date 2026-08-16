# ETNet Futures Exporter (期貨數據匯出工具)

一個 Windows 桌面程式（.exe），從 [etnet.com.hk 指數期貨頁面](https://www.etnet.com.hk/www/tc/futures/) 下載香港指數期貨報價數據，並儲存為 **.xlsx** 檔案到桌面。

## 功能

### Tab 0: 即時圖表 (Live Charts)
- 顯示 **恒生指數期貨 (HSI)** 及 **恒生中國企業指數期貨 (HHI)**（即月）的 **15分鐘陰陽燭圖**，附「中線（日市區間中點 = (最高+最低)/2）」虛線。
- **每 60 秒**自動從 etnet 更新一次數據。
- **exe/dmg 的做法**：此分頁直接載入 GitHub Pages 網頁（https://lightonint.github.io/etnet-download/），**exe 本身不會抓取 etnet 數據** —— 所有抓取都在網頁內進行（透過 Cloudflare Worker 代理），把負載完全交回網頁端。

#### Cloudflare Worker 代理（免費，可選但建議）
GitHub Pages 是靜態網站，瀏覽器直接抓 etnet 會被 CORS 擋住。預設會自動嘗試公開代理（cors.lol → allorigins → codetabs），免費額度有限、較不穩定。建議部署你自己的免費 Cloudflare Worker 代理：
1. Cloudflare 儀表板 → **Workers & Pages → Create → Worker**
2. 把 `webpage/worker_proxy.js` 的內容貼上取代預設程式碼 → **Deploy**
3. 複製你的 Worker 網址（`https://<名稱>.<帳號>.workers.dev`）
4. 告訴我網址，我會把它寫入 `webpage/app.js` 的 `CLOUDFLARE_WORKER_URL`（或你自行改完後 push）
- 免費方案每天 10 萬次請求，足夠每分鐘更新。

### Tab 1: 下載數據 (Get Data)
- 用 **tick box（勾選）** 選擇要下載的期貨產品（預設勾選：恒生指數期貨 HSI、恒生中國企業指數期貨 HHI；其他產品如小型恒指 MHI、恒生科技 HTI、美元兌人民幣 CUS 等亦可自由勾選）。
- 按下 **Get Data** 即時下載並儲存 .xlsx 到桌面；**月份自動下載「即月 + 下一個月」**，不需其他月份。
- 每個勾選的產品 = 一個 Excel 分頁，包含：
  - **報價**：日市 / 夜市最新價、升跌、升跌%、高/低水、最高、最低、前收市、開市、成交張數、交易宗數、每宗成交（即月及下月）
  - **未平倉**：未平倉總數 (GOI)、未平倉淨數 (NOI)、到期日
  - **15分鐘時段記錄**：每 15 分鐘的開/高/低/最新、升跌、高/低水、成交等
- 檔案命名：`etnet_futures_<合約代碼>_<月份>_<日期時間>.xlsx`

### Tab 2: 排程下載 (Scheduled Task)
支援多種排程方式，可自由組合：
- **每週**：勾選執行日子（星期一至日），可多選
- **每日**：每天執行
- **每隔 N 日**：每 N 天執行一次
- **執行時間（香港時間 HKT）**：用下拉選單（每 5 分鐘一個選項）或自訂時間加入**多個**指定時間（例：09:05、16:30）→ 即「每日執行次數」；預設以香港時間 (UTC+8) 計算，即使電腦在不同時區也會在正確的香港時間觸發
- 介面會即時顯示「每週執行 X 次（每日 Y 次）」摘要及下次執行時間（同時顯示香港時間）
- 排程設定會自動儲存，重開程式後仍保留
- **立即執行一次**：可手動觸發一次下載

## 使用方式

直接雙擊 `ETNetFuturesExporter.exe` 即可。程式介面為繁體中文。

> 已預先建好的 exe 位於 `dist\ETNetFuturesExporter.exe`（Windows 10/11 64-bit）。
> 如想自行重新打包，請參閱下方「建立 Windows .exe」。

> 注意：排程功能需要在程式開啟時才會觸發。如需電腦關機/程式關閉時仍執行，
> 可在 Windows 工作排程器 (Task Scheduler) 中加入啟動時自動執行程式。

## 環境設定 (.env)

程式啟動時會自動讀取 `.env` 設定檔（存放位置：exe 同一資料夾，或專案根目錄；
真實環境變數優先）。複製 `.env.example` 為 `.env` 後修改即可：

| 變數 | 用途 | 預設 |
|---|---|---|
| `ETNET_FUTURES_URL` | 期貨數據來源網址 | `https://www.etnet.com.hk/www/tc/futures/` |
| `REQUEST_TIMEOUT` | 下載逾時（秒） | `30` |
| `USER_AGENT` | 請求的瀏覽器標識 | Chrome UA |
| `OUTPUT_DIR` | 輸出資料夾（留空 = 桌面） | 桌面 |
| `DOWNLOAD_PREFIX` | .xlsx 檔名前綴 | `etnet_futures` |

`.env` 不會被提交到 GitHub（見 `.gitignore`）。

## 建立 Windows .exe

### 方法一：Windows 上一鍵打包（最簡單）
在你的 Windows 電腦上：
1. 安裝 [Python 3.9+](https://www.python.org/downloads/)（安裝時勾選 *Add python.exe to PATH*）
2. 雙擊執行專案內的 **`build.bat`**
3. 完成後 exe 位於 `dist\ETNetFuturesExporter.exe`

### 方法二：GitHub Actions（免本機環境）
把本專案推到 GitHub 後：
1. 到 GitHub 專案頁 → **Actions** → **Build Windows EXE** → **Run workflow**
2. 完成後在 workflow 的 **Artifacts** 下載 `ETNetFuturesExporter-windows`

### 方法三：手動指令
```bat
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --clean --noconfirm futures_exporter.spec
```

## macOS 版本 (.dmg)

在 macOS 上（Apple Silicon / Intel 皆可，產物為當前架構的 .app）：
```bash
python3 -m pip install -r requirements.txt pyinstaller pillow
python3 gen_icns.py && iconutil -c icns app.iconset -o app.icns   # 產生圖示（一次即可）
python3 -m PyInstaller --clean --noconfirm futures_exporter_mac.spec   # 產生 .app
rm -rf dmg_stage && mkdir dmg_stage
cp -R dist/ETNetFuturesExporter.app dmg_stage/
ln -s /Applications dmg_stage/Applications
hdiutil create -volname "ETNetFuturesExporter" -srcfolder dmg_stage -ov -format UDZO ETNetFuturesExporter-mac-arm64.dmg
```
> 未簽署的 .app 首次開啟時，請在 Finder 右鍵 →「開啟」以略過 Gatekeeper 警告。

## 專案結構

```
futures_exporter/
├── main.py                  # 程式入口
├── app/
│   ├── downloader.py        # 下載及解析 etnet 期貨頁面
│   ├── excel_writer.py      # 產生 .xlsx (openpyxl)
│   ├── scheduler.py         # 排程引擎（每週/每日/每隔N日、多時間）
│   ├── worker.py            # 背景下載執行緒 (QThread)
│   ├── config.py            # 排程設定檔存取（JSON）
│   ├── envconfig.py         # .env 設定載入（stdlib，無額外依賴）
│   └── ui_main.py           # 主視窗（兩個 Tab）
├── tests/                   # 單元測試（排程 + .env）
├── smoke_test.py            # 線上數據下載測試
├── futures_exporter.spec    # PyInstaller 設定
├── build.bat                # Windows 一鍵打包
├── .env.example             # 環境設定範例
└── .github/workflows/       # GitHub Actions 自動打包
```

## 設定檔位置
- Windows: `%APPDATA%\FuturesExporter\config.json`
- 其他系統: `~/.futures_exporter/config.json`

## 免責聲明
數據來自 etnet.com.hk，僅供參考，不構成任何投資建議。

# 簽章指南 — 令 Windows 不再攔截 / 誤報

Windows SmartScreen 與防毒軟件對「從網路下載、沒有數碼簽章」的 .exe 一律顯示
「未知發行者 / Windows 保護了您的電腦」。**要徹底消除**，需要一個由受信任
CA 發出的**代碼簽署憑證 (code-signing certificate)**。自簽憑證無效（Windows
不會信任它）。

## 方法 A：Azure Trusted Signing（免費，推薦）

Microsoft 的雲端代碼簽署服務，**免費層每月 5,000 次簽署**，簽出後憑證由
Microsoft 代管，Windows 開箱即信。

1. 建立免費 Azure 帳戶：https://azure.microsoft.com/free/
2. 在 Azure 入口網站建立 **Trusted Signing** 資源：
   - 填寫組織/個人資料做身份驗證（需數分鐘至數日審核）
   - 建立 **Certificate Profile**（SKU 選 Free Trial）
   - 記下：資源 **Endpoint**（形如 `https://xxx.codesigning.azure.net`）、
     **Account**、**Certificate Profile**、**Certificate Name**
3. 在本機安裝簽署工具：
   ```bash
   brew install azuresigntool       # macOS
   # Windows: choco install azuresigntool
   ```
4. 簽署（身份驗證會跳出瀏覽器登入你的 Azure 帳號）：
   ```bash
   azuresigntool sign \
     -kvu "https://xxx.codesigning.azure.net" \
     -kvi <identity(account)> \
     -kvs <certificate-profile> \
     -kvc <certificate-name> \
     -tr http://timestamp.digicert.com -v \
     -in dist/ETNetFuturesExporter.exe -out dist/ETNetFuturesExporter-signed.exe
   ```

## 方法 B：商用 OV 代碼簽署憑證（約 US$100–300/年）

向 DigiCert / Sectigo / SSL.com 等購買「OV Code Signing」憑證，取得
`cert.pem + key.pem`（或 .pfx）後：

```bash
./sign_windows.sh                                   # 使用 cert.pem + key.pem
PFX=my.pfx PFX_PASS=密碼 ./sign_windows.sh          # 或使用 .pfx
```

## 簽章前／後檢查

```bash
osslsigncode verify dist/ETNetFuturesExporter-signed.exe
```
應顯示 `Signature verification: ok` 及簽署者名稱。

## 其他降低誤報的措施

1. **GitHub Releases 分發**：已做（https://github.com/LightoninT/etnet-download/releases），
   有助累積檔案信譽。
2. **VirusTotal 檢查**：https://www.virustotal.com 上傳 exe 查看各防毒引擎結果；
   若屬誤報，可按其指引提交申訴。
3. **onedir 版本**：PyInstaller 單檔 (onefile) 自我解壓行為較易被防毒誤判；
   若你的防毒攔截單檔版，改用資料夾版（`dist/ETNetFuturesExporter/`）通常可通過。
4. 首次執行時：**更多資訊 (More info) → 仍要執行 (Run anyway)**。

## 非 .exe 的發佈方式（可避開或減少攔截）

Windows 的 SmartScreen / 防毒只會檢查「下載回來的可執行程式」。因此：

| 方式 | 是否被攔截 | 說明 |
|---|---|---|
| **ZIP 資料夾版**（已提供：`ETNetFuturesExporter-windows-onedir.zip`） | ZIP 本身**不會**觸發 SmartScreen（它是壓縮檔不是程式）；解壓後的 .exe 首次執行可能仍有一次提示 | 最實用的「非 exe」方案：下載 zip → 解壓 → 執行 |
| **直接用 Python 執行**（無 exe） | **完全不會**被攔截 | 開發者/個人使用：安裝 Python 後 `python main.py` |
| MSI 安裝檔 | 未簽章的 MSI 一樣觸發 SmartScreen | 沒有簽章時沒幫助，不值得做 |
| macOS .dmg | macOS Gatekeeper 對未簽章 app 同樣會提示 | 已有 dmg；右鍵→開啟 即可 |

**結論**：只要程式最終要「執行」，Windows 就必定檢查它 —— 沒有任何格式能
完全繞過；最接近的是 ZIP（傳輸階段零攔截）+ 資料夾版（比單檔 exe 少誤報）。
要徹底無提示，仍是取得 CA 簽章（見上方方法 A / B）。

## 現況（v1.1.5）

- 已內嵌正確的**版本資訊**（產品名稱、版本、公司、描述）→ 減少誤判、屬性頁更完整。
- 尚未簽章（無 CA 憑證）。完成方法 A 或 B 後，執行 `./sign_windows.sh` 即可。

# 用語對照表

翻譯常用詞彙統一對照，來源為 [L10N TW 詞彙對照表](https://hackmd.io/@l10n-tw/glossaries) 與既有專案慣用語。

## 標記語法

備註欄（最後一欄）的標記由 `fix_terminology.py` 解析：

- `不翻「X」` — **禁用詞**（中國用語），自動替換為本列 TW 欄位譯法
- `留意「X」` — **僅掃描不替換**（語境敏感），回報後人工判定
- `對應「anchor」` — **英文錨定**：可先寫多個（OR 語意），其後的 `不翻`／`留意` 標記只在
  msgid 命中錨定詞（詞界、大小寫不敏感）時才作用；`對應` 之前的標記維持全局行為。
  範例：`對應「line」「lines」留意「行」`＝msgid 含 line/lines 且 msgstr 用「行」時回報；
  `對應「keyring」「key ring」不翻「金鑰環」`＝msgid 含 keyring/key ring 時自動改為「鑰匙圈」。

## 通用詞彙

| English | 繁體中文 | 備註 |
|---------|---------|------|
| 32-bit | 32 位元 | 不翻「32 位」、bit 之所以翻譯為「位元」，是避免歧異，例如 "32-bit integer" 在簡體中文寫作「三十二位整数」，bit 乍看就成為量詞，與本意牴觸。 |
| 64-bit | 64 位元 | 不翻「64 位」 |
| Access | 存取 | 不翻「訪問」、亦作：取用、亦有「接達」的用法 |
| Adaptive | 適應性 | 不翻「自適應」 |
| add | 新增 | 留意「添加」 |
| Add-on | 增益集 | 不翻「加載項/外接程序」 |
| Addon / Add-on | 附加元件 | 不翻「附加組件」、關於 Fifox 中 Addon 與 Extension 的差異，請參見 [Mozilla Support](https://support.mozilla.org/en-US/questions/790919) |
| Address (n.) | 位址 | 留意「地址」、IP 位址、記憶體位址 |
| Address (v.) | 定址 | 不翻「尋址」、記憶體定址 |
| advanced | 進階 | 留意「高級」(分級則保留) |
| Advanced Settings | 進階設定 | 不翻「高級設置」 |
| Algorithm | 演算法 | 不翻「算法」 |
| Antivirus Software | 防毒軟體 | 不翻「殺毒軟體」 |
| Application | 應用程式 | 留意「應用」、亦作：應用（軟體） |
| apply | 套用 |  |
| Array | 陣列 | 不翻「數組」 |
| Assembler | 組譯器 | 不翻「彙編器」 |
| Assembly language | 組合語言 | 不翻「彙編語言」 |
| Asynchronous Programming | 非同步程式設計 | 不翻「異步編程」、例如 JavaScript 中的 `async`, `await` |
| Atomic operation | 最小操作 | 留意「原子操作」、參考：[並行程式設計: Atomics 操作](https://hackmd.io/@sysprog/concurrency-atomics) |
| Audio | 音訊 | 不翻「音頻」 |
| background | 背景 |  |
| Bandwidth | 頻寬 | 不翻「帶寬」 |
| Base Station | 基地台 | 不翻「基站」、亦作：基地站、通訊工程術語 |
| Baseband processor | 基頻處理器 | 不翻「基帶」 |
| behaviour | 行為 |  |
| Binary | 二進位 | 「進位制」在台灣簡稱「進位」，在中國簡稱「进制」 |
| Binary Search | 二元搜尋 | 不翻「二分查找/二分搜索」 |
| Binary Tree | 二元樹 | 不翻「二叉樹」 |
| Binding | 繫結/綁定 | 可參考[此討論](https://t.me/l10n_tw/34803)，依語境自行斟酌。 |
| Bitmap | 點陣圖 | 不翻「位圖」 |
| Bitrate | 位元率 | 不翻「碼率/比特率」、亦作：位元速率 |
| Block | 封鎖 | 留意「屏蔽」、不翻「和諧（河蟹）」、亦作：阻擋 / 阻塞、(non-)blocking 常譯作 (非) 阻塞 |
| Broadband | 寬頻 | 不翻「寬帶」 |
| Bubble Sort | 泡沫排序 | 不翻「冒泡排序」 |
| Build | 建構 | 留意「生成」、不翻「構建」、亦作：建置 |
| Build System | 建置系統 | 不翻「構建系統」 |
| button | 按鈕 |  |
| Byte | 位元組 | 不翻「字節」、在字元編碼仍以單一 byte 為主的年代，將 byte 翻譯為「字节」尚可接受。然而，Unicode 普及後，字元與 byte 已不再具有固定的一對一對應關係，因此「字节」無法準確反映 byte 的真正意義。<br>byte 本質上是由若干 bit 所組成的儲存單位，而非字元，因此譯為「位元組」更精確，不僅避免與字元 (character) 的概念混淆，亦可避免與計算機結構的 word 混淆，後者指一次性處理事務的固定長度的位元數量 |
| Cache | 快取 | 不翻「緩存」、亦作：快取記憶體、快取記憶體是 CPU 內暫時存放資料之處，存取速度略慢於 CPU 暫存器，而顯著快於主記憶體。除了用於計算機結構，快取也廣泛在資訊科技領域出現。 |
| Call | 呼叫 | 不翻「調用」、此指叫用 (invoke) 函式或副程式 (subroutine) 的過程 |
| cancel | 取消 |  |
| Character | 字元 | 留意「字符」、字符 可能是合法複詞的一部分（如「脫字符號」= caret notation），人工判定 |
| Chip | 晶片 |  |
| Class | 類別 | 此指一些物件導向程式語言中，可讓程式設計者自訂的資料型別 |
| Client | 用戶端 | 不翻「客戶端」 |
| close | 關閉 |  |
| Column | 行 |  |
| Command Line | 命令列 | 不翻「命令行」 |
| Command Line Interface | 命令列 | 不翻「命令行界面」、英文常縮寫為 CLI |
| Command Prompt | 命令提示字元 | 不翻「命令提示符」、Windows 早期的命令介面的殼層 (shell)<br>參見[微軟語言入口網站](https://www.microsoft.com/zh-tw/language/Search?&searchTerm=command%20prompt&langID=124&Source=true&productid=undefined) |
| community | 社群 | 不翻「社區」 |
| Compatibility | 相容性 | 不翻「兼容性」 |
| computer | 電腦 | 科目名稱如「計算機結構」保留 |
| Concurrent | 並行 | 不翻「並發」、請參見〈[並行程式設計: 概念](https://hackmd.io/@sysprog/concurrency-concepts)〉<br>須注意 Apple 將 Sidecar 也譯為並行，與本條無關 |
| Configuration / Configure | 組態 | 留意「配置」、不過本來配置就有布置的意思，在這樣的用法下與組態是否不太一樣？ |
| context menu | 情境選單 | 不翻「上下文菜單」 |
| Core dump | 記憶體傾印 | 不翻「內核轉儲」 |
| create | 建立 | 留意「創建」 |
| credential | 憑證 | 留意「身份驗證資訊」 |
| Cursor | 游標 | 不翻「光標」 |
| Customize | 自訂 | 留意「定製/自定義」、亦作：客製化 |
| Daemon | 常駐程式 | 不翻「守護進程」、亦作：系統服務 / 守護行程 / 幕後程式、適用於泛 Unix 風格之作業系統的術語 |
| Dashboard | 儀表板 | 不翻「儀錶盤」 |
| Data Type | （資料）型別 | 不翻「（數據）類型」 |
| Database | 資料庫 |  |
| Debug | 偵錯 | 留意「調試」、亦作：除錯 |
| Declaration | 宣告 | 留意「聲明」、程式設計術語 |
| Default | 預設 | 不翻「默認」、亦作：預設值 |
| Dependency | 相依性 | 留意「依賴」、亦作：相依項 |
| detect | 偵測 | 留意「檢測」 |
| Device | 裝置 | 留意「設備」、不翻「器件」、亦作：設備 |
| dialog | 對話框 |  |
| Disable | 停用 | 留意「禁用」 |
| Disk | 磁碟 | 根據[國教院資料](https://terms.naer.edu.tw/detail/4f27432dc4dec3b147dfca7bf63304bf/)，臺灣用語以「磁盤」指涉磁碟中儲存資料的金屬片 |
| Document | 文件 | 不翻「文檔」 |
| effect | 效果 |  |
| Enable | 啟用 |  |
| Enum | 列舉 | 不翻「枚舉」 |
| Export | 匯出 | 不翻「導出」 |
| Expression | 運算式 | 不翻「表達式」 |
| Extension | 擴充套件 | 留意「擴展」、不翻「插件」、亦作：延伸功能、Firefox 正體中文版中以「附加元件」稱呼 addon，以「擴充套件」稱呼 extension |
| Feedback | 回授 | 不翻「反饋」、feedback control system<br>一般動詞作「回饋」 |
| Field | 欄位 | 指關聯式資料庫中資料表的一行 |
| File | 檔案 | 留意「文件」 |
| File Extension | 副檔名 | 不翻「後綴名/擴展名」 |
| Firmware | 韌體 | 不翻「固件」 |
| folder | 資料夾 |  |
| Font | 字型 | 留意「字體」 |
| Font size | 字型大小 | 留意「字號」、不翻「字體大小」 |
| Frame | 影格 | 「[幀](https://dict.revised.moe.edu.tw/dictView.jsp?ID=7954)」是量詞，而 frame 是名詞，應依據場景給予合適的譯詞 |
| Frame | 訊框 | 網路工程術語，訊框為 TCP/IP 五層架構中，資料連結層的通訊單元 |
| Frame rate | 影格率 | 不翻「幀率」、亦作：圖禎率 / 畫面更新率 |
| Fullscreen | 全螢幕 | 不翻「全屏」 |
| Function | 函式（程式） | 留意「函數」、亦作：函數（數學）、若要表達為程式語言的一種結構，建議譯為「函式」<br>請參閱〈[你所不知道的 C 語言：函式呼叫篇](https://hackmd.io/@sysprog/c-function#%E7%B0%A1%E4%BB%8B)〉 |
| Gateway | 閘道 | 不翻「網關」、亦作：閘道器 |
| Generate | 產生 | 留意「生成」 |
| Generator | 產生器 | 不翻「生成器」 |
| Global Settings | 全域設定 | 不翻「全局設置」 |
| Global Variable | 全域變數 | 不翻「全局變量」、程式語言術語 |
| Handle | 控制代碼 | 不翻「句柄」、本質上是整數，用以標識程式執行過程中所建立或使用的物件 |
| Hardcore | 硬派 | 不翻「硬核」 |
| Hardware | 硬體 | 香港亦稱呼為「硬件」 |
| Hash Table | 雜湊表 | 不翻「哈希表/散列表」 |
| HDD | 硬碟 | 全稱為 Hard Disk Drive |
| Header file | 標頭檔 | 不翻「頭文件」 |
| Heap | 堆積 | 一種資料結構 |
| Highlight | 凸顯標示 | 留意「高亮」、亦作：醒目標示 / 色彩突顯 / 標明 |
| Hover | 暫留 | 留意「懸停」、指將滑鼠指標暫時停留於畫面某處上 |
| Icon | 圖示 | 不翻「圖標」、香港亦稱呼爲「圖標」 |
| image | 圖片 |  |
| Implement / Implementation | 實作 | 留意「實現」 |
| Import | 匯入 | 留意「導入」 |
| Indent | 縮排 | 不翻「縮進」、亦作：定位點 |
| Information | 資訊 | 不翻「信息」 |
| Information Technology | 資訊科技 | 不翻「信息技術」、亦作：IT |
| Integrate | 整合 | 不翻「集成」 |
| Interface | 介面 | 留意「界面」、不翻「接口」、簡體中文裏，和人交互翻譯爲「界面」，和機器或抽象事物交互翻譯爲「接口」 |
| Internet | 網際網路 | 香港亦稱呼為「互聯網」 |
| Interpreter | 直譯器 | 不翻「解釋器」 |
| Introduce | 介紹 | 留意「推介」 |
| Kernel | （作業系統）核心 | 不翻「內核」、建議不省略作業系統部份，避免造成閱聽者理解困擾 |
| Keyring | 鑰匙圈 | 對應「keyring」「key ring」不翻「金鑰環」 |
| Kit | 套件 | 不翻「工具包」 |
| LAN | LAN | 不翻「區域網」、亦作：區域網路、全稱為 Local Area Network |
| Library | 函式庫 | 亦作：程式庫 |
| Line | 列 | 直行橫列；對應「line」「lines」留意「行」 |
| Link | 連結 | 亦作：鏈結、Firefox 正體中文版沿襲 Netscape 用詞譯作「鏈結」。<br>強調相互結合的意境時，譯作「[連結](https://dict.revised.moe.edu.tw/dictView.jsp?ID=64001)」，例如「動態連結函式庫」(dynamic-link library)，而強調資料因結合而呈現[鏈狀](https://dict.revised.moe.edu.tw/dictView.jsp?ID=3626)樣貌，用「鏈結」，如鏈結串列 (linked list)。 |
| Linked List | 鏈結串列 | 不翻「鍊表」、一種資料結構 |
| Load | 載入 | 不翻「加載」 |
| Local | 區域 | 留意「局部/本地」、亦作：本機、分別為與 global 和 remote 相對時 |
| location | 位置 |  |
| Macro | 巨集 |  |
| Memory / RAM | 記憶體 | 不翻「內存」、亦作：主（要）記憶體、1. 近年來不少電腦推銷員在介紹產品時，常把「內存」與「儲存空間」的用語混用，導致混淆<br>2. 主要記憶體(primary storage)的翻譯為相對於次要記憶體(secondary storage)，參閱 [Computer data storage - Wikipedia](https://en.wikipedia.org/wiki/Computer_data_storage#Primary_storage)，可避免與其他類型記憶體（如硬碟）混淆 |
| Menu | 選單 | 留意「菜單」、亦作：功能表 |
| Merge Sort | 合併排序 | 不翻「歸併排序」 |
| Message | 訊息 | 不翻「消息」 |
| metadata | 中繼資料 |  |
| Modulation | 調變 | 不翻「調製」 |
| Module | 模組 | 不翻「模塊」 |
| Mouse | 滑鼠 |  |
| Navigation bar | 導覽列 | 留意「導航欄」、亦作：導航條 |
| Network | 網路 | 不翻「網絡」、香港稱呼為網絡 |
| Network adapter | 網路介面卡 | 不翻「網絡適配器」、參見[微軟語言入口網站](https://www.microsoft.com/zh-tw/language/Search?&searchTerm=adapter&langID=124&Source=true&productid=0) |
| Object-oriented Programming | 物件導向程式設計 | 不翻「面向對象程序設計」 |
| OK | 確定 |  |
| Ones' complement | 一補數 | 不翻「反碼」、香港稱呼爲「一補碼」 |
| open | 開啟 | 留意「打開」 |
| Operating System | 作業系統 |  |
| Operator | 運算子 | 不翻「運算符」 |
| Optimize | 最佳化 | 留意「優化」、雖然優化一詞常用於口語，但該稱呼並不精準<br>名詞為 optimization |
| Optional | 選用 | 亦作：選填 |
| Overwrite | 覆寫 | 留意「覆蓋」 |
| Package | 軟體包 | 亦作：~~套件~~、此處意指 software package<br>關於不建議使用「套件」翻譯的細節請參閱 [Telegram 討論串](https://t.me/l10n_tw/22024)<br>參考材料：[軟體包管理系統的基本概念](https://docs.google.com/document/d/1URPinHtcQnI-wu1GCm_QwI18VF2T-maweij82fmjTYw/preview) |
| Partition (disk) | 分割區 | 留意「分區」 |
| paste | 貼上 | 不翻「粘貼」 |
| Plugin | 外掛程式 | 不翻「插件」、Firefox 正體中文版使用此稱呼<br>有鑑於外掛程式常使人聯想為遊戲的作弊程式，若有更佳的稱呼，歡迎補充。 |
| Pointer | 指標 | 留意「指針」、C 語言中用來存放記憶體位址的一種資料型別 |
| Polymorphism | 多型 | 不翻「多態」 |
| Port | 連接埠 | 亦作：通訊埠、(a.) 實體的插孔或連接處<br>(b.) [網路通訊名詞](https://terms.naer.edu.tw/detail/1284277/) |
| Postfix | 尾碼 | 留意「後綴」 |
| Power Adapter | 電源供應器 | 不翻「電源適配器」、亦作：充電器、[adapter 與 charger 差異探討](https://www.etechnog.com/2019/06/difference-between-charger-adapter.html#:~:text=The%20charger%20is%20specially%20designed%20to%20charge%20a%20device%20such,power%20supply%20to%20a%20device.) |
| Powered By | 威力本源 | 不翻「由...驅動」、亦作：由…提供、威力本源乃是優秀的翻譯例子之一 |
| Prefix | 前置（詞、字、碼） | 留意「前綴」、亦作：字首、macOS 中對於 IPv6 的 prefix 稱呼為「前置碼」 |
| preset | 預設集 |  |
| preview | 預覽 |  |
| Process | 處理程序 | 不翻「進程」、亦作：行程 / 進程、微軟的稱呼原為「處理程序」，近年來則改用「處理序」<br>關於同樣翻譯為「進程」的討論參閱 [Telegram 討論串](https://t.me/l10n_tw/28168) <br> 而關於「行程」的稱呼請參閱〈[Linux 核心設計: 不僅是個執行單元的 Process](https://hackmd.io/@sysprog/linux-process#%E8%AA%B0%E6%AE%BA%E4%BA%86-Process%EF%BC%9F)〉 |
| Process | 製程 | 留意「工藝」、fabrication process |
| Program | 程式 | 留意「程序」 |
| Project | 專案 | 留意「項目」 |
| Protocol | 協定 | 留意「協議」、亦作：通訊協定、agreement 譯為協議以與protocol區分 |
| Quality | 品質 | 留意「質量」、質量一詞用來表達「品質與數量」，或物理學、天文學術語 |
| Queue | 佇列 | 不翻「隊列」、(a.) 一種資料結構<br>(b.) 常見於等候處理的工作或播放清單 |
| Quick Sort | 快速排序 | 不翻「快排」 |
| Read-only | 唯讀 | 不翻「只讀」 |
| Real-time | 即時 | 留意「實時」 |
| Recursion / Recursive | 遞迴 | 不翻「遞歸」 |
| Refresh | 重新整理 | 留意「刷新」 |
| Register (n.) | 暫存器 | 不翻「寄存器」、CPU 中暫時存放運算資料的單元，具有存取速度最快、容量最小的特性 |
| Register (v.) | 註冊 | |
| Registry | 登錄檔 | 不翻「註冊表」、亦作：註冊表、Microsoft Windows 作業系統中用來儲存電腦組態資訊的資料庫，參閱 [Microsoft Docs](https://docs.microsoft.com/en-us/windows/win32/sysinfo/registry) 及 [Wikipedia](https://docs.microsoft.com/en-us/windows/win32/sysinfo/registry) <br> 另請參見 https://aka.ms/AAkqh57 |
| Render | 呈現 | 留意「渲染」、亦作：算繪、關於不建議使用「渲染」翻譯的原因，參閱〈[論 Render 翻譯（算繪/演繹）](https://breezymove.blogspot.com/2013/12/render.html)〉及〈[資訊科技詞彙翻譯](https://hackmd.io/@sysprog/it-vocabulary)〉 |
| reset | 重設 |  |
| Resolution | 解析度 |  |
| Return Value | 回傳值 | 不翻「返回值」 |
| Row | 列 |  |
| Run | 執行 | 留意「運行」 |
| Save | 存檔 | 留意「保存」、不翻「存儲」、亦作：儲存 |
| scaling | 縮放 |  |
| Screen | 螢幕 | 不翻「屏幕」 |
| Search | 搜尋 | 留意「查找/搜索」 |
| Sensor | 感應器 | 不翻「傳感器」、亦作：感測器 |
| Serial Port | 序列埠 | 不翻「串行埠/串行/串口」 |
| Server | 伺服器 |  |
| setting(s) | 設定 | 不翻「設置」 |
| shortcut | 捷徑 | 不翻「快捷方式」 |
| Sign in | 登入 | 留意「登錄」 |
| Sign out | 登出 | 留意「註銷」、不翻「退出登錄」 |
| Sign up | 註冊 | |
| Signal | 訊號 | 不翻「信號」 |
| Signature | 特徵 | 留意「簽名」、function signature |
| Slider | 滑桿 | 留意「滑塊」、圖形介面中的一種控制元件，[見圖](https://docs.microsoft.com/en-us/windows/apps/design/controls/slider) |
| Socket | 插口（網路） | 不翻「套接字（網路）」、亦作：(保留原文)、「插座」是 socket 在電氣領域的特化用語，socket 一字多義，例如 eye socket 指眼眶。<br>由於「插座」在漢語已是特化用語，就不以「插座」稱呼電腦網路領域的 socket |
| Software | 軟體 | 香港亦有「軟件」的稱呼 |
| source | 來源 |  |
| Source Code | 來源碼 | 留意「原始碼」 |
| Stack | 堆疊 | 不翻「堆棧」、一種先進後出的資料結構 |
| String | 字串 | 不翻「字符串」、一串循序相連的字元 |
| Structure | 結構 | 留意「結構體」、亦作：結構體、當描述事物的脈絡及操作的模式時，稱「結構」，如論文結構和資料結構。<br>當強調用某個識別符號來展現特定的資料集合時，稱「結構體」，如 Go、C、Rust 程式語言的 `struct` |
| Subnet mask | 子網路遮罩 | 不翻「子網掩碼」、網路工程術語 |
| Support | 支援（某功能） | 留意「支持」、此處「支援」的意涵為[牛津辭典](https://www.oxfordlearnersdictionaries.com/definition/english/support_1?q=support)第九點所述 |
| System Crash | 系統當機（正規） | 不翻「死機」、亦作：死當（口語）、相關：Windows 的 BSOD, Unix-like 的 kernel panic |
| System Extension | 系統延伸功能 | 不翻「系統擴展」、macOS Catalina 引入的新機制，參見[蘋果支援網站](https://support.apple.com/zh-tw/HT210999) |
| tab | 分頁 | 不翻「標籤頁」 |
| Task bar | 工作列 | 不翻「任務欄」 |
| Task Manager | 工作管理員 | 不翻「任務管理器」 |
| Terminal | 終端機 | 留意「終端」 |
| Thread | 執行緒 | 不翻「線程」 |
| Threshold | 門檻值 | 留意「閾值」 |
| through / via | 透過 | 留意「通過」(通過=pass exam) |
| thumbnail | 縮圖 |  |
| tooltip | 工具提示 |  |
| Touch Screen | 觸控螢幕 |  |
| Traverse | 走訪 | 不翻「遍歷」 |
| Tutorial | 教學 | 留意「教程」 |
| Two's complement | 二補數 | 不翻「補碼」、香港稱呼爲「二補碼」 |
| uninstall | 解除安裝 | 留意「卸載」 |
| Union | 聯集（數學） | 不翻「併集（數學）/聯合體（程式）」 |
| user | 使用者 | 不翻「用戶」 |
| Video | 影片 | 不翻「視頻」、亦作：視訊 |
| Volume (disk) | 磁碟區（微軟） | 留意「卷（微軟）/宗卷（蘋果）」、亦作：卷宗（蘋果） |
| Wallpaper | 桌布 | 不翻「壁紙/牆紙」 |
| WAN | WAN | 不翻「廣域網」、亦作：廣域網路、全稱為 Wide Area Network |
| Wildcard character | 萬用字元 | 不翻「通配符」 |
| Window | 視窗 | 不翻「窗口」 |
| Word | 字組 | 針對計算機結構的用語 |


# SNES DSP

以 Python 實現的 Nintendo DSP-1、DSP-1A、DSP-1B、DSP-2、DSP-3 及 DSP-4：一顆執行你所提供微碼的 NEC uPD77C25，以零售版卡帶與它進行的交換作為準則。

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | 繁體中文（香港）

[![CI](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/snes-dsp-python)](https://github.com/gufranco/snes-dsp-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**6** 款晶片共用 **5** 個微碼映像檔，讀出 **121** 種交換，來自 **36** 盒零售版卡帶，其中 **62** 種在晶片上重播，**0** 次失敗，**0** 個以人手描述的命令，**987** 項測試，**100%** 語句及分支覆蓋率，沒有任何依賴套件

```python
import snesdsp

part = snesdsp.Chip("dsp2")
part.write(0x09)
for byte in (0x02, 0x00, 0x03, 0x00):
    part.write(byte)
print([part.read() for _ in range(4)])
print(part, part.model, part.identity.part)
```

```
[6, 0, 0, 0]
<Chip dsp2 on upd7725> dsp2 dsp2
```

範例建立一顆 DSP-2，即把 DSP-2 微碼載入一顆 uPD77C25 並將其啟動。命令 `0x09` 將兩個 16 位元的字相乘，每個字先送低位元組。答案是第一個字中的 2 乘 3，由映像檔中的程式計算得出。本套件沒有任何一行說明命令 `0x09` 做甚麼。

## 安裝

| 要求 | 版本 |
|:--|:--|
| Python | 3.12 或更新版本 |
| git | 任何版本，用於取得子模組 |
| 微碼 | 你擁有的每個想執行的映像檔副本，列於[你提供的微碼](#the-microcode-you-supply) |

```bash
git clone --recurse-submodules https://github.com/gufranco/snes-dsp-python.git
cd snes-dsp-python
python3 snesdsp/doctor.py
```

本套件只匯入標準程式庫內的模組。處理器是位於儲存庫根目錄的 `nec-upd7725-96050-python` 子模組，沒有它甚麼都無法執行。`snes-driver-python` 子模組只用於重新讀取卡帶。從 download-zip 連結取得的原始碼封存檔不包含任何一個子模組，因此在那裏每款晶片都會拒絕建立並說明原因。

診斷腳本檢查機器、簽出的副本、每款晶片及其下的處理器，最後以一行作結。提交錯誤報告時請貼上它的完整輸出。五個映像檔齊全時，它的結尾是：

```
  17 checks, nothing to report
```

缺少映像檔時，每款需要該映像檔的晶片所對應的一行會說明副本應放在哪裏。

版本遵循 [Semantic Versioning](https://semver.org/)，由 semantic-release 根據提交歷史發佈。每個版本都有標籤，並列於[發佈頁面](https://github.com/gufranco/snes-dsp-python/releases)。

## 介面

`snesdsp.Chip(model, **options)` 建立一款晶片並將其啟動。`model` 為必填，比對時不區分大小寫、連字號或底線。只有映像檔存在時才會建立晶片：沒有後備方案，無法建立的晶片會引發 `NoFirmware`。

| 選項 | 預設值 | 意義 |
|:--|:--|:--|
| `gap` | `14` | 每次存取後晶片執行的指令數，即主機最少會留給它的數量 |
| `patience` | `400000` | 讀取時等待晶片發出請求的指令數，超過後照樣讀取 |
| `boot` | `20000` | 載入後、首次存取前執行的指令數 |
| `fill` | `0` | 載入映像檔前處理器記憶體所持有的值 |
| `image` | 無 | 映像檔的位元組，直接傳入，因此不搜尋任何目錄。需要 `identity` |
| `identity` | 無 | `image` 是甚麼，即 `snesdsp.identify(image)` 傳回的值 |
| `images` | 無 | 由晶片名稱對應到 `(identity, path)` 的映射，取代目錄搜尋 |

### 型號

| 型號 | 別名 | 執行的映像檔 | 程式的功能 |
|:--|:--|:--|:--|
| `dsp1` | `dsp-1`, `upd77c25dsp1`, `nintendodsp1` | `dsp1` | 31 個定點 3D 數學命令：一部攝影機、三個姿態矩陣、投影及旋轉 |
| `dsp1a` | `dsp-1a`, `upd77c25dsp1a`, `nintendodsp1a` | `dsp1` | 在較小晶粒上的 DSP-1 程式及數據 ROM |
| `dsp1b` | `dsp-1b`, `upd77c25dsp1b`, `nintendodsp1b` | `dsp1b` | 最後一版 DSP-1 光罩，31 個命令，修正了一個算術錯誤 |
| `dsp2` | `dsp-2`, `upd77c25dsp2`, `nintendodsp2` | `dsp2` | 6 個命令：圖塊轉換、透明色、合併、鏡像、乘法及重新縮放 |
| `dsp3` | `dsp-3`, `upd77c25dsp3`, `nintendodsp3` | `dsp3` | 13 個命令：一個解壓器、一個位元平面轉換器，以及在六角網格上的搜尋 |
| `dsp4` | `dsp-4`, `upd77c25dsp4`, `nintendodsp4` | `dsp4` | 15 個命令，其中 7 個是道路渲染器，會在中途暫停並其後恢復 |

### 呼叫

| 呼叫 | 效果 |
|:--|:--|
| `write(value)` | 向數據埠寫入一個位元組，然後執行 `gap` 條指令 |
| `read()` | 最多等待 `patience` 條指令讓晶片發出請求，從數據埠讀取一個位元組，然後執行 `gap` 條指令 |
| `read_status()` | 狀態暫存器。第 7 位元是 RQM，在晶片請求下一個位元組期間設定 |
| `write_bus(address, value)` | `address` 的第 0 位元為 0 時執行 `write(value)`，為 1 時寫入狀態埠。傳回該晶片 |
| `read_bus(address)` | `address` 的第 0 位元為 0 時執行 `read()`，為 1 時執行 `read_status()` |
| `step(count=None)` | 執行 `count` 條指令，省略 `count` 時執行 `gap` 條 |
| `elapsed(master_clocks)` | 執行晶片在該數量的主機主時鐘內所執行的指令數。傳回該晶片 |
| `waited()` | 逐步執行直至晶片發出請求，最多 `patience` 條指令。晶片發出請求時為 True |
| `settle()` | `waited()`，晶片始終沒有發出請求時引發 `NeverReady` |
| `reset()` | 重建處理器，重新載入相同的映像檔位元組並再次啟動。傳回該晶片 |

### 狀態

| 屬性 | 意義 |
|:--|:--|
| `model`, `part` | 標準型號名稱 |
| `identity` | 映像檔的 `Identity`：`part`、`processor`、`revision`、`program_words`、`data_words` |
| `processor` | 映像檔執行所在的處理器，這裏每款晶片都是 `upd7725` |
| `asking` | RQM 設定期間為 True |
| `pending_output` | 晶片發出請求時為 1，否則為 0 |
| `clock` | 晶片的時鐘，單位為 Hz |
| `gap`, `patience` | 上述兩個選項，可寫入 |
| `core` | 執行映像檔的 `upd7725` 處理器 |
| `console` | 上述呼叫所經過的處理器主機埠 |

### 模組內容

| 名稱 | 內容 |
|:--|:--|
| `snesdsp.MODELS` | 六個 `Model` 記錄，以標準名稱為鍵。每個記錄都有 `name`、`aliases`、`summary` 及 `image` |
| `snesdsp.Model` | 這些記錄的型別 |
| `snesdsp.SHARES_MICROCODE` | `{"dsp1a": "dsp1"}`，唯一執行另一款晶片映像檔的晶片 |
| `snesdsp.available(held=None)` | 映像檔位於本機的晶片，以晶片名稱對應到 `(identity, path)` 的映射表示。傳入形狀相同的映射 `held` 時，會讀取它而不進行搜尋 |
| `snesdsp.why_not(held=None)` | 至少有一款晶片可以建立時為 `None`，否則為說明為何一款都無法建立的句子。接受同樣的 `held` |
| `snesdsp.MASTER_CLOCK` | `21477273`，主機的主時鐘，單位為 Hz，是 NTSC 色彩副載波的六倍 |
| `snesdsp.DSP_CLOCK` | `7600000`，晶片的時鐘，單位為 Hz，每個時鐘一條指令 |
| `snesdsp.GAP` | `14`，`gap` 的預設值 |
| `snesdsp.clock_of(model)` | 該型號的時鐘，單位為 Hz。名稱未知時引發 `UnknownModelError` |
| `snesdsp.steps_for(master_clocks, clock=DSP_CLOCK, master=MASTER_CLOCK)` | 在該數量的主時鐘內執行的指令數，向下取整 |
| `snesdsp.__version__` | 已安裝的版本 |
| `snesdsp.identify(image, catalogue=None)` | 映像檔的 `Identity`，按 SHA-256 在清單或形狀相同的映射 `catalogue` 中尋找。會引發 `Unrecognised` 或 `Corrupt` |
| `snesdsp.digests_of(image)` | 映像檔的 CRC32、MD5、SHA-1 及 SHA-256，以 `crc32`、`md5`、`sha1` 及 `sha256` 為鍵的小寫十六進位 |
| `snesdsp.directories(environment=None)` | 搜尋按次序讀取的目錄，取自 `environment` 或程序的環境變數 |
| `snesdsp.search(places=None, catalogue=None)` | 在 `places` 或 `directories()` 中找到的每個映像檔，以 `(identity, path)` 配對列出，每款晶片以最先找到的檔案為準 |

```python
import snesdsp

for name, model in snesdsp.MODELS.items():
    print(name, model.image, model.aliases)

print(snesdsp.SHARES_MICROCODE)
print(snesdsp.MASTER_CLOCK, snesdsp.DSP_CLOCK, snesdsp.GAP, snesdsp.clock_of("DSP-1"))
print(snesdsp.steps_for(snesdsp.MASTER_CLOCK // 60))

for wrong in ("dsp5", None):
    try:
        snesdsp.Chip(wrong)
    except snesdsp.UnknownModelError as error:
        print(error)
```

```
dsp1 dsp1 ('dsp-1', 'upd77c25dsp1', 'nintendodsp1')
dsp1a dsp1 ('dsp-1a', 'upd77c25dsp1a', 'nintendodsp1a')
dsp1b dsp1b ('dsp-1b', 'upd77c25dsp1b', 'nintendodsp1b')
dsp2 dsp2 ('dsp-2', 'upd77c25dsp2', 'nintendodsp2')
dsp3 dsp3 ('dsp-3', 'upd77c25dsp3', 'nintendodsp3')
dsp4 dsp4 ('dsp-4', 'upd77c25dsp4', 'nintendodsp4')
{'dsp1a': 'dsp1'}
21477273 7600000 14 7600000
126666
dsp5 is not a part this package covers; it has dsp1, dsp1a, dsp1b, dsp2, dsp3, dsp4
no model was named, and this package will not choose one for you. Name one of: dsp1, dsp1a, dsp1b, dsp2, dsp3, dsp4
```

六十分之一秒的主時鐘相當於晶片執行 126,666 條指令。

### 錯誤

| 錯誤 | 引發時機 |
|:--|:--|
| `UnknownModelError` | 缺少型號名稱，或沒有型號使用該名稱。訊息會列出每個型號 |
| `NoFirmware` | 處理器子模組未簽出、找不到該晶片的映像檔，或傳入了 `image` 但沒有 `identity` |
| `NeverReady` | `settle()` 執行了 `patience` 條指令，晶片始終沒有發出請求 |
| `Unrecognised` | 傳給 `snesdsp.identify` 的位元組，其 SHA-256 與清單中任何映像檔都不符。訊息會說明該檔案最可能是甚麼 |
| `Corrupt` | 映像檔的 SHA-256 相符，但與清單記錄的另一個摘要不符 |
| `WrongShape` | `image` 的長度不是其 `identity` 所需的長度：每個程式字 3 個位元組，每個數據字 2 個位元組 |

```python
from pathlib import Path

import snesdsp

if snesdsp.why_not():
    raise snesdsp.NoFirmware(snesdsp.why_not())

identity, where = snesdsp.available()["dsp1b"]
held = Path(where).read_bytes()
print(snesdsp.identify(held), identity.program_words, identity.data_words, len(held))

part = snesdsp.Chip("dsp1b", image=held, identity=identity)
print(part.identity.part, part.processor)

for wrong in (held[:-2], held[::-1]):
    try:
        snesdsp.identify(wrong)
    except snesdsp.Unrecognised as error:
        print(str(error)[:72])
try:
    snesdsp.Chip("dsp1b", image=held[:-2], identity=identity)
except snesdsp.WrongShape as error:
    print(error)

slow = snesdsp.Chip("dsp1", patience=0)
slow.write(0x00)
try:
    slow.settle()
except snesdsp.NeverReady as error:
    print(error)
```

```
<Identity dsp1b DSP-1B on upd7725> 2048 1024 8192
dsp1b upd7725
this is 8190 bytes, and the manifest knows no part of that length (it kn
this is 8192 bytes, the length of dsp1, dsp1b, dsp2, dsp3, dsp4, but its
a upd7725 takes 8192 bytes of firmware and this is 8190
dsp1 did not ask for attention within 0 instructions
```

範例直接傳入映像檔，因此不搜尋任何目錄。每個映像檔都有 2,048 個程式字及 1,024 個數據字。短了兩個位元組的檔案會因長度被拒絕，而相同位元組反轉後則會因內容被拒絕。

<a id="the-microcode-you-supply"></a>

## 你提供的微碼

本儲存庫不附帶微碼，不會下載微碼，也不提供連結。每個映像檔在其任何一個位元組執行前，都會先以 SHA-256 識別。[`snesdsp/artifacts.manifest.json`](snesdsp/artifacts.manifest.json) 存放各個摘要。

| 映像檔 | 執行它的晶片 | 位元組 | CRC32 | SHA-256 |
|:--|:--|--:|:--|:--|
| `dsp1` | `dsp1`, `dsp1a` | 8,192 | `27124599` | `5f2e5ed06b362be023b978b5978813ecb9a07c76592454b45c2a1ed17a0de349` |
| `dsp1b` | `dsp1b` | 8,192 | `588279b4` | `4d42db0f36faef263d6b93f508e8c1c4ae8fc2605fd35e3390ecc02905cd420c` |
| `dsp2` | `dsp2` | 8,192 | `f0221c90` | `5efbdf96ed0652790855225964f3e90e6a4d466cfa64df25b110933c6cf94ea1` |
| `dsp3` | `dsp3` | 8,192 | `e3b54e6a` | `2e635f72e4d4681148bc35429421c9b946e4f407590e74e31b93b8987b63ba90` |
| `dsp4` | `dsp4` | 8,192 | `ca09e176` | `63ede17322541c191ed1fdf683872554a0a57306496afc43c59de7c01a6e764a` |

搜尋會依序從以下目錄讀取以 `.bin` 或 `.rom` 結尾的檔案，每款晶片以最先找到的檔案為準：

1. `SNES_DSP_FIRMWARE_DIR` 中的每個目錄，分隔方式與作業系統分隔 `PATH` 的方式相同。
2. `UPD7725_FIRMWARE_DIR` 中的每個目錄，這是本成員曾與 snes-st-python 共用的名稱。
3. 存放本簽出副本的目錄中的 [`firmware/`](firmware/README.md)，適用於本儲存庫作為另一個專案的子模組時。
4. 本簽出副本中的 [`firmware/`](firmware/README.md)。

SHA-256 不在清單中的檔案會被搜尋略過。若交給 `snesdsp.identify`，它會被拒絕並附上診斷：複製器檔頭、位元組對調的傾印及已知的損壞傾印都會被識別並指出。

確認你持有的副本：

```bash
shasum -a 256 firmware/dsp1.bin                 # macOS
sha256sum firmware/dsp1.bin                     # Linux
certutil -hashfile firmware\dsp1.bin SHA256     # Windows
```

## 以主機的方式驅動晶片

主機透過位址存取晶片。位址的第 0 位元選擇埠：0 是數據埠，1 是狀態暫存器。較高的位元都不解碼，因此一款晶片會在整個位址窗口內回應。

晶片以 7,600,000 Hz 運行，每個時鐘執行一條指令。主機以 21,477,273 Hz 計算主時鐘，一次慢速卡帶存取花費其中 8 個。65816 對長位址的一次儲存需要 5 個週期，因此主機在兩次存取之間最少留給晶片 40 個主時鐘，即 14 條指令。這就是預設的 `gap`。花費更長時間的主機以 `elapsed` 表明。

```python
import snesdsp

part = snesdsp.Chip("dsp1")
print(f"{part.read_bus(0x3F8001):#04x}", part.asking)

part.write_bus(0x3F8000, 0x00)
for word in (0x4000, 0x2000):
    part.write_bus(0x3F8000, word & 0xFF)
    part.write_bus(0x3F8000, word >> 8)
low, high = part.read_bus(0x3F8000), part.read_bus(0x3F8000)
print(hex(low | high << 8), f"{part.read_status():#04x}")
print(part.gap, part.patience, part.clock)
print(part.elapsed(snesdsp.MASTER_CLOCK // 60) is part, part.reset() is part)
```

```
0x84 True
0x1000 0x84
14 400000 7600000
True True
```

奇數位址讀取狀態暫存器，啟動後 RQM 已設定。偶數位址傳送 DSP-1 的乘法命令 `0x00` 及其兩個參數。`0x4000 * 0x2000 >> 15` 等於 `0x1000`。

## 驅動每款晶片

以下每個輸出都是晶片自身微碼的回答。在每次具備映像檔的流水線執行中，[`conformance/documented.py`](conformance/documented.py) 都會對各晶片執行相同的交換。

### DSP-1

先是一個命令位元組，然後是小端序的參數字，回答也以相同方式傳回。命令 `0x00` 將兩個定點字相乘。

```python
from snesdsp import Chip

part = Chip("dsp1")
part.write(0x00)
for value in (0x4000, 0x2000):
    part.write(value & 0xFF)
    part.write(value >> 8)
low, high = part.read(), part.read()
print(hex(low | (high << 8)))
```

```
0x1000
```

### DSP-1A

沒有 DSP-1A 映像檔。建立它時執行的是 DSP-1 的映像檔。

```python
from snesdsp import Chip

part = Chip("dsp1a")
print(part.model, part.identity.part)
```

```
dsp1a dsp1
```

### DSP-1B

DSP-1B 執行自己的映像檔。它的修正不在乘法中，這裏的乘法同樣得出 `0x1000`。修正所在之處見[是否正確](#is-it-right)。

```python
from snesdsp import Chip

part = Chip("dsp1b")
part.write(0x00)
for value in (0x4000, 0x2000):
    part.write(value & 0xFF)
    part.write(value >> 8)
low, high = part.read(), part.read()
print(part.identity.part, hex(low | (high << 8)))
```

```
dsp1b 0x1000
```

### DSP-2

命令 `0x09` 是整數乘法，而非定點乘法。

```python
from snesdsp import Chip

part = Chip("dsp2")
part.write(0x09)
for value in (0x0002, 0x0003):
    part.write(value & 0xFF)
    part.write(value >> 8)
print([hex(part.read()) for _ in range(4)])
```

```
['0x6', '0x0', '0x0', '0x0']
```

### DSP-3

DSP-3 每次接收一個字。命令 `0x001c` 以最後寫入的字作答，只要有讀取就一直如此。

```python
from snesdsp import Chip

part = Chip("dsp3")
for byte in (0x1C, 0x00):
    part.write(byte)
for byte in (0x34, 0x12, 0x78, 0x56):
    part.write(byte)
print(" ".join(f"{part.read():02x}" for _ in range(8)))
```

```
78 56 78 56 78 56 78 56
```

snes9x 的 DSP-3 程式碼對此命令以兩個零字作答。[`conformance/divergences.json`](conformance/divergences.json) 記錄了這項分歧，[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 說明了怎樣才能確定是否有遊戲發送此命令。

### DSP-4

DSP-4 接收一個命令字及參數，然後分批作答。

```python
from snesdsp import Chip

part = Chip("dsp4")
part.write(0x01)
part.write(0x00)
for value in (0x0001, 0x0002, 0x0003, 0x0004):
    part.write(value & 0xFF)
    part.write(value >> 8)
print([hex(part.read()) for _ in range(6)])
```

```
['0x4', '0x0', '0x4', '0x0', '0x4', '0x0']
```

<a id="is-it-right"></a>

## 是否正確

命令計算出甚麼，就是程式的答案，因此這裏的檢查涵蓋程式以外的一切：埠、節奏、每個映像檔的身分，以及真實遊戲進行的交換。

| 檢查 | 命令 | 需要映像檔 |
|:--|:--|:--:|
| 處理器，逐條指令 | 位於 [nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python) | 否 |
| 埠、節奏、狀態暫存器及匯流排解碼 | 每個模組旁的單元測試 | 否 |
| 每個型號、別名及映像檔，以及每個映像檔都有一個決定性的摘要 | 每個模組旁的單元測試 | 否 |
| 卡帶進行的每次交換都得到回答 | `python3 -m conformance.against_cartridges <part>` | 是 |
| 每款晶片的回答仍與擷取語料庫時相同 | `python3 -m conformance.answers` | 是 |
| DSP-1 及 DSP-1B 映像檔仍在當初發現分歧之處出現分歧 | `python3 -m conformance.masks` | 是 |
| 沒有任何隨附微碼令返回堆疊超過 4 層 | `python3 -m conformance.stack` | 是 |
| README 的每個範例都輸出其所述的內容 | `python3 -m conformance.documented` | 是 |
| 逐步執行保持在每秒 150,000 條指令以上 | `python3 -m conformance.speed` | 是 |

每個需要映像檔的工具在一個映像檔都沒有時，都會以 2 結束並說明缺少甚麼，而不是當作通過。

### 交換

遊戲發送的內容由 [snes-driver-python](https://github.com/gufranco/snes-driver-python) 從卡帶中讀出，它會反組譯驅動晶片的常式。每個結果都是一個形態：存取的次序及寬度，不含有效負載。[`cartridges.manifest.json`](cartridges.manifest.json) 以摘要指明每盒卡帶，並不儲存任何卡帶的任何位元組。

| 晶片 | 卡帶 | 形態 | 在晶片上重播 | 存取位置 |
|:--|--:|--:|--:|--:|
| DSP-1 | 29 | 50 | 22 | 1,384 |
| DSP-2 | 3 | 13 | 1 | 270 |
| DSP-3 | 1 | 20 | 10 | 182 |
| DSP-4 | 3 | 38 | 29 | 910 |

DSP-1 的各列來自 29 個不同的驅動程式。DSP-3 的各列來自一盒卡帶，也是唯一搭載該晶片的卡帶。

形態不含有效負載，因此其位元組由固定種子產生。晶片以沉默回應的形態會在 256 個命令位元組下逐一重播，只有全部 256 個都沉默時才算作沉默。有四個形態，DSP-1 一個，DSP-3 兩個，DSP-4 一個，會先讀後寫：在主機上它們讀取的是先前交換留下的內容，因此會另行報告，而不算作沉默。其餘每個形態都得到回答。

```bash
python3 -m conformance.against_cartridges dsp1
python3 -m conformance.answers --take dsp1
python3 -m conformance.answers
python3 -m conformance.record
```

`against_cartridges` 接收一款晶片，未指明時為 `dsp3`，任何交換保持沉默時以 1 結束。`answers` 接收晶片名稱，預設為全部，回答有變時以 1 結束，本機的映像檔並非擷取語料庫時所用的映像檔時以 2 結束。即使沒有映像檔，某款晶片沒有語料庫，或其語料庫並非按今天掃描的形狀以相同次序擷取時，亦以 1 結束：所有載荷都來自同一個帶種子的隨機序列，一個形狀移動了，其後每個形狀的載荷都會改變。`--take` 會記錄回答，而不是檢查回答。`record` 重新讀取 [`cartridges/`](cartridges) 或 `SNES_CARTRIDGE_DIR` 中的每盒卡帶，一盒都沒有時以 2 結束。

### DSP-1B 的修正

DSP-1B 修正了一個算術錯誤，因此必定有某些輸入會令兩個光罩出現分歧。`python3 -m conformance.masks --sweep` 以 256 個命令位元組及 16 組各 6 個字的參數執行兩個映像檔。它找到 6 個命令位元組，即 `0x04`、`0x0b`、`0x1b`、`0x24`、`0x2b` 及 `0x3b`，在其中一組參數上出現差異，由回答的第三個字起不同。該範圍內沒有其他差異。`python3 -m conformance.masks` 會重新推導這 6 個命令位元組，其中任何一個改變或變成一致時以 1 結束。

### 證據來源

| 證據 | 能確定甚麼 | 不能確定甚麼 |
|:--|:--|:--|
| NEC 的數據表，經由處理器的記錄 | 寬度、記憶體大小、4 層堆疊、每條指令的時鐘數 | NEC 沒有印出的行為 |
| 在該處理器上執行的微碼 | 每個命令計算出甚麼 | 埠是否在正確時刻交給它正確的位元組 |
| 從卡帶讀出的交換 | 晶片能回答已發售遊戲所提出的要求 | 沒有遊戲提出的任何要求 |
| 同一晶片的行為模型 | 甚麼都不能確定：從不跟從它 | 只在其出現分歧之處記錄於 [`conformance/divergences.json`](conformance/divergences.json) |

Nintendo 沒有發表過任何有關這些晶片的資料。節奏、啟動長度及第 0 位元以上的解碼都是界限值，[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 列出了每一項及可確定它的量度方法。[`conformance/hardware.json`](conformance/hardware.json) 記錄了權威次序，以及本成員所比較的對象。

## 參與開發

| 需要 | 位置 |
|:--|:--|
| 每個關卡檢查及其執行次序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 供編程代理使用的相同資料 | [AGENTS.md](AGENTS.md) |
| 本儲存庫與家族其他成員共用的標準 | [FAMILY.md](FAMILY.md) |
| 錯誤報告及錯誤答案 | [GitHub Issues](https://github.com/gufranco/snes-dsp-python/issues)，附上診斷腳本的輸出 |
| 保安報告 | [SECURITY.md](SECURITY.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 --with types-setuptools==84.0.0.20260812 mypy==1.14.1
pnpm run format:check
cov=(uvx --python 3.12 --from coverage==7.6.10 --with setuptools==84.0.0 coverage)
"${cov[@]}" erase
for file in $(find snesdsp conformance -name '*.test.py' | sort); do
  "${cov[@]}" run -a "$file"
done
"${cov[@]}" report
python3 -m conformance.speed
```

每個模組旁都有一個名為 `<module>.test.py` 的測試檔案，各自可以獨立執行。覆蓋率是 100% 語句及分支的硬性關卡。吞吐量下限在覆蓋率步驟之外執行。切勿在報告中附上微碼或卡帶：SHA-256 足以識別兩者。

## 參考資料

- NEC，*uPD7725/uPD96050 Digital Signal Processor* 數據表。從中取得的每項事實都連同頁碼記錄於 [nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python)，本儲存庫將其作為子模組附帶。該數據表不可再分發，亦不在本儲存庫中。
- snes9x，提交 `2971061cf07fdc6fc7d18883edf4e648eb16a6d2` 的 `dsp3.cpp`，https://github.com/snes9xgit/snes9x ，只為說明那一項已記錄的分歧而閱讀。這裏沒有任何內容跟從它。
- [snes-driver-python](https://github.com/gufranco/snes-driver-python)，用於讀取卡帶自身程式碼向其協處理器發送的內容。
- 讀者擁有的零售版卡帶，每盒在讀取前都會以摘要對照 [`cartridges.manifest.json`](cartridges.manifest.json) 確認。

## 引用本專案

[CITATION.cff](CITATION.cff) 在每次發佈時，由加蓋套件版本的腳本更新。

## 授權

MIT。見 [LICENSE](LICENSE)。

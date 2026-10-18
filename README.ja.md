# SNES DSP

PythonによるNintendo DSP-1、DSP-1A、DSP-1B、DSP-2、DSP-3、DSP-4です。利用者が用意したマイクロコードを実行する1個のNEC uPD77C25で、市販カートリッジがこのチップと行うやり取りに照らして検証されています。

[English](README.md) | 日本語 | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/snes-dsp-python)](https://github.com/gufranco/snes-dsp-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**5**個のマイクロコードイメージ上の**6**種類のチップ、**36**本の市販カートリッジから読み出した**121**件のやり取り、そのうち**62**件をチップに対して再生、失敗**0**件、手作業で記述したコマンド**0**個、テスト**987**件、ステートメントとブランチのカバレッジ**100%**、依存関係なし

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

この例はDSP-2を構築します。DSP-2はDSP-2のマイクロコードをuPD77C25に読み込み、起動します。コマンド`0x09`は、下位バイトから送られた2つの16ビットワードを乗算します。答えは最初のワードに入った2かける3で、それを計算したのはイメージ内のプログラムです。このパッケージには、コマンド`0x09`が何をするかを記述した行は1行もありません。

## インストール

| 要件 | バージョン |
|:--|:--|
| Python | 3.12以降 |
| git | 任意、サブモジュールの取得用 |
| マイクロコード | 実行したい各イメージについて、自分が所有するコピー。[利用者が用意するマイクロコード](#the-microcode-you-supply)に一覧があります |

```bash
git clone --recurse-submodules https://github.com/gufranco/snes-dsp-python.git
cd snes-dsp-python
python3 snesdsp/doctor.py
```

このパッケージは標準ライブラリ以外を何もインポートしません。プロセッサはリポジトリのルートにある`nec-upd7725-96050-python`サブモジュールで、これがなければ何も動きません。`snes-driver-python`サブモジュールはカートリッジの再読み出しにのみ使います。download-zipリンクから得たソースアーカイブにはどちらのサブモジュールも含まれないため、その場合はすべてのチップが構築を拒否し、その理由を示します。

ドクターはマシン、チェックアウト、すべてのチップとその下のプロセッサを確認し、最後に1行を出力します。バグ報告には出力全体を貼り付けてください。5つのイメージがすべて揃っている場合、最後は次のようになります。

```
  17 checks, nothing to report
```

イメージがない場合、それを必要とする各チップの行に、コピーを置く場所が示されます。

リリースは[Semantic Versioning](https://semver.org/)に従い、semantic-releaseによってコミット履歴から作成されます。各リリースにはタグが付けられ、[リリースページ](https://github.com/gufranco/snes-dsp-python/releases)に掲載されます。

## インターフェース

`snesdsp.Chip(model, **options)`は1つのチップを構築して起動します。`model`は必須で、大文字小文字、ハイフン、アンダースコアを区別せずに照合されます。チップはイメージがある場合にのみ構築されます。フォールバックはなく、構築できないチップは`NoFirmware`を送出します。

| オプション | デフォルト | 意味 |
|:--|:--|:--|
| `gap` | `14` | 各アクセスの後にチップが実行する命令数。コンソールが空けられる最小値です |
| `patience` | `400000` | 読み出しが、チップの要求を待ってからそれでも読み出すまでの命令数 |
| `boot` | `20000` | 読み込み後、最初のアクセスの前に実行する命令数 |
| `fill` | `0` | イメージを読み込む前にプロセッサのメモリが保持する値 |
| `image` | なし | イメージのバイト列。直接渡すため、ディレクトリは検索されません。`identity`が必要です |
| `identity` | なし | `image`が何であるか。`snesdsp.identify(image)`が返す形式です |
| `images` | なし | チップ名から`(identity, path)`へのマッピング。ディレクトリ検索の代わりに使われます |

### モデル

| モデル | 別名 | 実行するイメージ | プログラムの内容 |
|:--|:--|:--|:--|
| `dsp1` | `dsp-1`, `upd77c25dsp1`, `nintendodsp1` | `dsp1` | 固定小数点3D演算の31個のコマンド。カメラ、3つの姿勢行列、投影と回転 |
| `dsp1a` | `dsp-1a`, `upd77c25dsp1a`, `nintendodsp1a` | `dsp1` | より小さなダイに載ったDSP-1のプログラムとデータROM |
| `dsp1b` | `dsp-1b`, `upd77c25dsp1b`, `nintendodsp1b` | `dsp1b` | DSP-1の最後のマスク。31個のコマンドで、演算の不具合が修正されています |
| `dsp2` | `dsp-2`, `upd77c25dsp2`, `nintendodsp2` | `dsp2` | 6個のコマンド。タイル変換、透明色、合成、ミラー、乗算、再スケール |
| `dsp3` | `dsp-3`, `upd77c25dsp3`, `nintendodsp3` | `dsp3` | 13個のコマンド。展開器、ビットプレーン変換器、ヘックスグリッド上の探索 |
| `dsp4` | `dsp-4`, `upd77c25dsp4`, `nintendodsp4` | `dsp4` | 15個のコマンド。そのうち7個は途中で中断して再開する道路レンダラです |

### 呼び出し

| 呼び出し | 効果 |
|:--|:--|
| `write(value)` | データポートに1バイト書き込み、その後`gap`命令を実行します |
| `read()` | チップが要求するまで最大`patience`命令待ち、データポートから1バイト読み出し、その後`gap`命令を実行します |
| `read_status()` | ステータスレジスタ。ビット7はRQMで、チップが次のバイトを要求している間セットされます |
| `write_bus(address, value)` | `address`のビット0が0なら`write(value)`、1ならステータスポートへの書き込みです。チップを返します |
| `read_bus(address)` | `address`のビット0が0なら`read()`、1なら`read_status()`です |
| `step(count=None)` | `count`命令を実行します。`count`を省略した場合は`gap`命令です |
| `elapsed(master_clocks)` | コンソールのマスタークロックでその数だけの時間に、チップが実行する数の命令を実行します。チップを返します |
| `waited()` | チップが要求するまで、最大`patience`命令ステップ実行します。要求があればTrueです |
| `settle()` | `waited()`を実行し、チップが一度も要求しなければ`NeverReady`を送出します |
| `reset()` | プロセッサを再構築し、同じイメージのバイト列を再読み込みして再び起動します。チップを返します |

### 状態

| 属性 | 意味 |
|:--|:--|
| `model`, `part` | 正規のモデル名 |
| `identity` | イメージの`Identity`。`part`、`processor`、`revision`、`program_words`、`data_words` |
| `processor` | イメージが動作するプロセッサ。ここではすべてのチップで`upd7725`です |
| `asking` | RQMがセットされている間True |
| `pending_output` | チップが要求している間は1、それ以外は0 |
| `clock` | チップのクロック(Hz) |
| `gap`, `patience` | 上記の2つのオプション。書き込み可能です |
| `core` | イメージを実行している`upd7725`プロセッサ |
| `console` | 上記の呼び出しが経由する、プロセッサのホストポート |

### モジュールの内容

| 名前 | 内容 |
|:--|:--|
| `snesdsp.MODELS` | 正規名をキーとする6つの`Model`レコード。それぞれ`name`、`aliases`、`summary`、`image`を持ちます |
| `snesdsp.Model` | それらのレコードの型 |
| `snesdsp.SHARES_MICROCODE` | `{"dsp1a": "dsp1"}`。別のチップのイメージを実行する唯一のチップです |
| `snesdsp.available(held=None)` | このマシンにイメージがあるチップ。チップ名から`(identity, path)`へのマッピングです。同じ形のマッピング`held`を渡すと、検索せずにそれを読みます |
| `snesdsp.why_not(held=None)` | 少なくとも1つのチップを構築できる場合は`None`、そうでなければどれも構築できない理由を述べる文。同じ`held`を受け取ります |
| `snesdsp.MASTER_CLOCK` | `21477273`。コンソールのマスタークロック(Hz)で、NTSCカラーキャリアの6倍です |
| `snesdsp.DSP_CLOCK` | `7600000`。チップのクロック(Hz)で、1クロックにつき1命令です |
| `snesdsp.GAP` | `14`。デフォルトの`gap`です |
| `snesdsp.clock_of(model)` | そのモデルのクロック(Hz)。不明な名前には`UnknownModelError`を送出します |
| `snesdsp.steps_for(master_clocks, clock=DSP_CLOCK, master=MASTER_CLOCK)` | その数のマスタークロックで実行される命令数。切り捨てです |
| `snesdsp.__version__` | インストールされているバージョン |
| `snesdsp.identify(image, catalogue=None)` | イメージの`Identity`。マニフェスト、または同じ形のマッピング`catalogue`からSHA-256で見つけます。`Unrecognised`または`Corrupt`を送出します |
| `snesdsp.digests_of(image)` | イメージのCRC32、MD5、SHA-1、SHA-256。`crc32`、`md5`、`sha1`、`sha256`をキーとする小文字の16進数です |
| `snesdsp.directories(environment=None)` | 検索が読むディレクトリを順に並べたもの。`environment`またはプロセスの環境変数から求めます |
| `snesdsp.search(places=None, catalogue=None)` | `places`、または`directories()`で見つかったすべてのイメージを`(identity, path)`の組で返します。チップごとに最初に見つかったファイルが優先されます |

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

60分の1秒分のマスタークロックは、チップの126,666命令に相当します。

### エラー

| エラー | 送出される条件 |
|:--|:--|
| `UnknownModelError` | モデル名がないか、その名前のモデルが存在しない。メッセージにはすべてのモデルが列挙されます |
| `NoFirmware` | プロセッサのサブモジュールがチェックアウトされていない、チップのイメージが見つからない、または`identity`なしで`image`が渡された |
| `NeverReady` | `settle()`が`patience`命令を実行し、チップが一度も要求しなかった |
| `Unrecognised` | マニフェスト内のどのイメージにもないSHA-256を持つバイト列が`snesdsp.identify`に渡された。メッセージには、そのファイルが何である可能性が最も高いかが示されます |
| `Corrupt` | イメージがSHA-256では一致したが、マニフェストに記録された別のダイジェストでは一致しなかった |
| `WrongShape` | `image`の長さが、その`identity`が必要とする長さではない。プログラムワードあたり3バイト、データワードあたり2バイトです |

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

この例はイメージを直接渡すため、ディレクトリは検索されません。どのイメージも2,048プログラムワードと1,024データワードです。2バイト短いファイルは長さによって拒否され、同じバイト列を逆順にしたものは内容によって拒否されます。

<a id="the-microcode-you-supply"></a>

## 利用者が用意するマイクロコード

マイクロコードはここに含まれず、ダウンロードもされず、リンクもされていません。各イメージは、その1バイトでも実行される前にSHA-256で識別されます。ダイジェストは[`snesdsp/artifacts.manifest.json`](snesdsp/artifacts.manifest.json)にあります。

| イメージ | それを実行するチップ | バイト数 | CRC32 | SHA-256 |
|:--|:--|--:|:--|:--|
| `dsp1` | `dsp1`, `dsp1a` | 8,192 | `27124599` | `5f2e5ed06b362be023b978b5978813ecb9a07c76592454b45c2a1ed17a0de349` |
| `dsp1b` | `dsp1b` | 8,192 | `588279b4` | `4d42db0f36faef263d6b93f508e8c1c4ae8fc2605fd35e3390ecc02905cd420c` |
| `dsp2` | `dsp2` | 8,192 | `f0221c90` | `5efbdf96ed0652790855225964f3e90e6a4d466cfa64df25b110933c6cf94ea1` |
| `dsp3` | `dsp3` | 8,192 | `e3b54e6a` | `2e635f72e4d4681148bc35429421c9b946e4f407590e74e31b93b8987b63ba90` |
| `dsp4` | `dsp4` | 8,192 | `ca09e176` | `63ede17322541c191ed1fdf683872554a0a57306496afc43c59de7c01a6e764a` |

検索は、次のディレクトリから`.bin`または`.rom`で終わるファイルをこの順に読み、チップごとに最初に見つかったファイルが採用されます。

1. `SNES_DSP_FIRMWARE_DIR`内のすべてのディレクトリ。オペレーティングシステムが`PATH`を区切るのと同じ方法で区切ります。
2. `UPD7725_FIRMWARE_DIR`内のすべてのディレクトリ。このメンバーがかつてsnes-st-pythonと共有していた名前です。
3. このチェックアウトを含むディレクトリ内の[`firmware/`](firmware/README.md)。これが別のプロジェクトのサブモジュールである場合のためです。
4. このチェックアウト内の[`firmware/`](firmware/README.md)。

SHA-256がマニフェストにないファイルは、検索ではスキップされます。`snesdsp.identify`に渡すと、診断付きで拒否されます。コピー機のヘッダ、バイトスワップされたダンプ、既知の不良ダンプはそれぞれ認識され、名前が示されます。

手元のコピーを確認します。

```bash
shasum -a 256 firmware/dsp1.bin                 # macOS
sha256sum firmware/dsp1.bin                     # Linux
certutil -hashfile firmware\dsp1.bin SHA256     # Windows
```

## コンソールと同じ方法で駆動する

コンソールはアドレスを通じてチップにアクセスします。そのアドレスのビット0がポートを選びます。0はデータポート、1はステータスレジスタです。それより上位のビットはデコードされないため、1つのチップがアドレスウィンドウ全体で応答します。

チップは7,600,000 Hzで1クロックにつき1命令を実行します。コンソールは21,477,273 Hzでマスタークロックを数え、低速なカートリッジアクセスにそのうち8を費やします。ロングアドレスへの65816のストアは5サイクルかかるため、コンソールが2つのアクセスの間にチップに空けられる最小値は40マスタークロック、つまり14命令です。これがデフォルトの`gap`です。より長い時間を費やしたコンソールは、それを`elapsed`で伝えます。

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

奇数アドレスはステータスレジスタを読み出し、起動後はRQMがセットされています。偶数アドレスは、乗算であるDSP-1のコマンド`0x00`とその2つの引数を運びます。`0x4000 * 0x2000 >> 15`は`0x1000`です。

## すべてのチップを駆動する

以下の各出力は、そのチップ自身のマイクロコードが返した答えです。[`conformance/documented.py`](conformance/documented.py)は、イメージがあるすべてのパイプライン実行で、同じやり取りをチップに対して実行します。

### DSP-1

コマンドバイト、次にリトルエンディアンの引数ワード、そして同じ形式で答えが返ります。コマンド`0x00`は2つの固定小数点ワードを乗算します。

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

DSP-1Aのイメージはありません。DSP-1Aを構築すると、DSP-1のイメージが実行されます。

```python
from snesdsp import Chip

part = Chip("dsp1a")
print(part.model, part.identity.part)
```

```
dsp1a dsp1
```

### DSP-1B

DSP-1Bは独自のイメージを実行します。その修正は乗算にはなく、ここでも乗算は`0x1000`を返します。修正がどこにあるかは[正しいか](#is-it-right)で説明します。

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

コマンド`0x09`は固定小数点ではなく整数の乗算です。

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

DSP-3は1ワードずつ受け取ります。コマンド`0x001c`は、読み出しが続く限り、最後に書き込まれたワードを返します。

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

snes9xのDSP-3コードは、このコマンドに2つのゼロワードを返します。[`conformance/divergences.json`](conformance/divergences.json)がこの不一致を記録し、[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)が、いずれかのゲームがこのコマンドを送るかどうかを決着させるものを説明しています。

### DSP-4

DSP-4はコマンドワードとパラメータを受け取り、その後バッチで答えを返します。

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

## 正しいか

コマンドが何を計算するかはプログラムの答えです。そのため、ここでの確認はプログラムの周囲すべてを検証します。ポート、ペース、各イメージの同一性、そして実際のゲームが行うやり取りです。

| 確認 | コマンド | イメージが必要 |
|:--|:--|:--:|
| プロセッサ、命令ごと | [nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python)内 | いいえ |
| ポート、ペース、ステータスレジスタ、バスデコード | 各モジュールの隣にあるユニットテスト | いいえ |
| すべてのモデル、別名、イメージ、および各イメージに決め手となるダイジェストがあること | 各モジュールの隣にあるユニットテスト | いいえ |
| カートリッジが行うすべてのやり取りに答えが返ること | `python3 -m conformance.against_cartridges <part>` | はい |
| すべてのチップが、コーパス取得時と同じ答えを今も返すこと | `python3 -m conformance.answers` | はい |
| DSP-1とDSP-1Bのイメージが、不一致が見つかった箇所で今も不一致であること | `python3 -m conformance.masks` | はい |
| 出荷されたどのマイクロコードも、リターンスタックを4レベルより深くしないこと | `python3 -m conformance.stack` | はい |
| READMEのすべての例が、記載どおりの出力をすること | `python3 -m conformance.documented` | はい |
| ステップ実行が毎秒150,000命令を上回ること | `python3 -m conformance.speed` | はい |

イメージを必要とする各ツールは、イメージがない場合、成功扱いにせず、終了コード2で終了し、何が欠けているかを示します。

### やり取り

ゲームが送る内容は、[snes-driver-python](https://github.com/gufranco/snes-driver-python)によってカートリッジから読み出されます。これはチップを駆動するルーチンを逆アセンブルします。各結果は形状です。つまりアクセスの順序と幅で、ペイロードは含みません。[`cartridges.manifest.json`](cartridges.manifest.json)はすべてのカートリッジをダイジェストで指定し、どのカートリッジのバイトも保存されません。

| チップ | カートリッジ | 形状 | チップに対して再生 | アクセス箇所 |
|:--|--:|--:|--:|--:|
| DSP-1 | 29 | 50 | 22 | 1,384 |
| DSP-2 | 3 | 13 | 1 | 270 |
| DSP-3 | 1 | 20 | 10 | 182 |
| DSP-4 | 3 | 38 | 29 | 910 |

DSP-1の行は29の異なるドライバから得られています。DSP-3の行は、このチップを搭載する唯一のカートリッジ1本から得られています。

形状はペイロードを持たないため、そのバイトは固定シードから生成されます。チップが無応答で答える形状は、256個のコマンドバイトそれぞれで再度再生され、256個すべてが無応答の場合にのみ無応答と数えられます。DSP-1に1つ、DSP-3に2つ、DSP-4に1つ、計4つの形状は書き込む前に読み出します。コンソール上ではそれ以前のやり取りが残したものを読むため、無応答として数えずに別に報告されます。それ以外のすべての形状には答えが返ります。

```bash
python3 -m conformance.against_cartridges dsp1
python3 -m conformance.answers --take dsp1
python3 -m conformance.answers
python3 -m conformance.record
```

`against_cartridges`は1つのチップを受け取り、指定がなければ`dsp3`です。いずれかのやり取りが無応答のままなら終了コード1で終了します。`answers`はチップ名を受け取り、デフォルトではすべてです。答えが変わっていれば終了コード1で、このマシン上のイメージがコーパス取得時のものと異なれば終了コード2で終了します。イメージがなくても、コーパスが記録されていないチップや、コーパスが現在走査しているシェイプを同じ順序で取得したものでない場合は終了コード1で終了します。すべてのペイロードは1つのシード付き乱数列から作られるため、シェイプが1つ動くと、それ以降のすべてのシェイプのペイロードが変わるからです。`--take`は答えを確認する代わりに記録します。`record`は[`cartridges/`](cartridges)または`SNES_CARTRIDGE_DIR`内のすべてのカートリッジを再読み出しし、1本もなければ終了コード2で終了します。

### DSP-1Bの修正

DSP-1Bは演算の不具合を修正したため、2つのマスクが不一致になる入力が存在するはずです。`python3 -m conformance.masks --sweep`は、両方のイメージを256個のコマンドバイトと、それぞれ6ワードからなる16個の引数セットで実行します。その結果、`0x04`、`0x0b`、`0x1b`、`0x24`、`0x2b`、`0x3b`の6個のコマンドバイトが、1つの引数セットで答えの3ワード目以降が異なることが分かりました。その範囲内では、それ以外に異なるものはありません。`python3 -m conformance.masks`はその6個を再導出し、いずれかが変化するか一致に変わった場合は終了コード1で終了します。

### 根拠の出どころ

| 根拠 | 決着させるもの | 決着させられないもの |
|:--|:--|:--|
| プロセッサの記録を通じたNECのデータシート | 幅、メモリサイズ、4レベルのスタック、命令あたりのクロック数 | NECが記載しなかった動作 |
| そのプロセッサ上で実行したマイクロコード | 各コマンドが何を計算するか | ポートが正しいバイトを正しいタイミングで渡しているかどうか |
| カートリッジから読み出したやり取り | 出荷されたゲームが求めるものにチップが答えること | どのゲームも求めないもの |
| 同じチップの振る舞いモデル | 何も決着させません。決して従いません | 不一致がある箇所のみ、[`conformance/divergences.json`](conformance/divergences.json)に記録します |

Nintendoはこれらのチップについて何も公開していません。ペース、起動時間、ビット0より上のデコードは範囲であり、[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)がそれぞれを決着させる測定とともに列挙しています。[`conformance/hardware.json`](conformance/hardware.json)は権威の順序と、このメンバーが何と比較されるかを記録しています。

## 開発に参加する

| 必要なもの | 場所 |
|:--|:--|
| すべてのゲートと実行順序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| コーディングエージェント向けの同じ内容 | [AGENTS.md](AGENTS.md) |
| このリポジトリがファミリーの他のリポジトリと共有する基準 | [FAMILY.md](FAMILY.md) |
| バグ報告と誤った答え | [GitHub Issues](https://github.com/gufranco/snes-dsp-python/issues)、ドクターの出力を添えて |
| セキュリティ報告 | [SECURITY.md](SECURITY.md) |

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

各モジュールの隣には`<module>.test.py`という名前のテストファイルがあり、それぞれ単独で実行できます。カバレッジはステートメントとブランチで100%の厳格なゲートです。スループットの下限はカバレッジのステップの外で実行されます。報告にマイクロコードやカートリッジを添付しないでください。どちらもSHA-256で識別できます。

## 参考文献

- NEC、*uPD7725/uPD96050 Digital Signal Processor*データシート。そこから得たすべての事実は、ページ番号とともに[nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python)に記録されています。このリポジトリはそれをサブモジュールとして含みます。データシートは再配布できず、このリポジトリには含まれていません。
- snes9x、コミット`2971061cf07fdc6fc7d18883edf4e648eb16a6d2`の`dsp3.cpp`、https://github.com/snes9xgit/snes9x 。記録された1件の不一致を述べるためにのみ読みました。ここではそれに従っていません。
- [snes-driver-python](https://github.com/gufranco/snes-driver-python)。カートリッジ自身のコードがコプロセッサに何を送るかを読み出すためのものです。
- 読者が所有する市販カートリッジ。それぞれ読み出す前に[`cartridges.manifest.json`](cartridges.manifest.json)に照らしてダイジェストで確認します。

## 引用

[CITATION.cff](CITATION.cff)は、パッケージのバージョンを刻むスクリプトによって、リリースごとに更新されます。

## ライセンス

MIT。[LICENSE](LICENSE)を参照してください。

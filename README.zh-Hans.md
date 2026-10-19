# SNES DSP

用 Python 实现的 Nintendo DSP-1、DSP-1A、DSP-1B、DSP-2、DSP-3 和 DSP-4：一颗 NEC uPD77C25 运行你提供的微码，并以零售版卡带与它之间的交换为准。

[English](README.md) | [日本語](README.ja.md) | 简体中文 | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/snes-dsp-python)](https://github.com/gufranco/snes-dsp-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**6** 个部件，基于 **5** 个微码镜像；从 **36** 个零售版卡带中读出 **121** 个交换，其中 **62** 个在部件上回放；**0** 个失败，**0** 个手工描述的命令，**993** 个测试，**100%** 语句和分支覆盖率，无依赖

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

这个示例构建一个 DSP-2，它把 DSP-2 微码加载进 uPD77C25 并启动。命令 `0x09` 将两个先发低字节的 16 位字相乘。答案的第一个字是 2 乘 3，由镜像中的程序计算得出。本包没有任何一行代码说明命令 `0x09` 做什么。

## 安装

| 要求   | 版本                                                                                              |
| :----- | :------------------------------------------------------------------------------------------------ |
| Python | 3.12 或更新                                                                                       |
| git    | 任意版本，用于获取子模块                                                                          |
| 微码   | 你想运行的每个镜像都需要一份你自己拥有的副本，列在 [你提供的微码](#the-microcode-you-supply) 之下 |

```bash
git clone --recurse-submodules https://github.com/gufranco/snes-dsp-python.git
cd snes-dsp-python
python3 snesdsp/doctor.py
```

本包只导入标准库。处理器是仓库根目录下的 `nec-upd7725-96050-python` 子模块，没有它什么都无法运行。`snes-driver-python` 子模块仅用于重新读取卡带。通过下载 zip 链接得到的源码归档不含任何一个子模块，因此在那里每个部件都会拒绝构建并说明原因。

诊断脚本检查机器、检出的代码、每个部件以及底层的处理器，最后输出一行结论。提交任何缺陷报告时请粘贴它的完整输出。五个镜像都齐全时，它以如下一行结束：

```
  17 checks, nothing to report
```

缺少某个镜像时，需要它的每个部件对应的那一行会说明副本应放在哪里。

版本发布遵循 [语义化版本](https://semver.org/)，由 semantic-release 根据提交历史生成。每个版本都打了标签，并列在 [发布页面](https://github.com/gufranco/snes-dsp-python/releases) 上。

## 接口

`snesdsp.Chip(model, **options)` 构建一个部件并启动它。`model` 是必填项，匹配时不区分大小写、连字符和下划线。只有镜像存在时才会构建部件：没有回退方案，无法构建的部件会抛出 `NoFirmware`。

| 选项       | 默认值   | 含义                                                          |
| :--------- | :------- | :------------------------------------------------------------ |
| `gap`      | `14`     | 每次访问后部件运行的指令数，即主机最少能留给它的数量          |
| `patience` | `400000` | 读取时等待部件请求的指令数，超过后照样读取                    |
| `boot`     | `20000`  | 加载后、首次访问前运行的指令数                                |
| `fill`     | `0`      | 加载镜像前处理器各存储器中的值                                |
| `image`    | 无       | 直接传入的镜像字节，这样就不会搜索任何目录。需要 `identity`   |
| `identity` | 无       | `image` 是什么，形式与 `snesdsp.identify(image)` 的返回值相同 |
| `images`   | 无       | 部件名到 `(identity, path)` 的映射，用来代替目录搜索          |

### 型号

| 型号    | 别名                                       | 运行的镜像 | 程序的功能                                                    |
| :------ | :----------------------------------------- | :--------- | :------------------------------------------------------------ |
| `dsp1`  | `dsp-1`, `upd77c25dsp1`, `nintendodsp1`    | `dsp1`     | 31 条定点 3D 数学命令：一个摄像机、三个姿态矩阵、投影和旋转   |
| `dsp1a` | `dsp-1a`, `upd77c25dsp1a`, `nintendodsp1a` | `dsp1`     | 更小晶片上的 DSP-1 程序和数据 ROM                             |
| `dsp1b` | `dsp-1b`, `upd77c25dsp1b`, `nintendodsp1b` | `dsp1b`    | 最后一版 DSP-1 掩模，31 条命令，修正了一处算术错误            |
| `dsp2`  | `dsp-2`, `upd77c25dsp2`, `nintendodsp2`    | `dsp2`     | 6 条命令：图块转换、透明色、合并、镜像翻转、乘法和缩放        |
| `dsp3`  | `dsp-3`, `upd77c25dsp3`, `nintendodsp3`    | `dsp3`     | 13 条命令：一个解压器、一个位平面转换器和一个六角网格上的搜索 |
| `dsp4`  | `dsp-4`, `upd77c25dsp4`, `nintendodsp4`    | `dsp4`     | 15 条命令，其中 7 条是会在中途挂起并恢复的道路渲染器          |

### 调用

| 调用                        | 效果                                                                                    |
| :-------------------------- | :-------------------------------------------------------------------------------------- |
| `write(value)`              | 向数据端口写入一个字节，然后运行 `gap` 条指令                                           |
| `read()`                    | 最多等待 `patience` 条指令让部件发出请求，从数据端口读取一个字节，然后运行 `gap` 条指令 |
| `read_status()`             | 状态寄存器。第 7 位是 RQM，部件请求下一个字节时置位                                     |
| `write_bus(address, value)` | `address` 的第 0 位为 0 时执行 `write(value)`，为 1 时写入状态端口。返回该部件          |
| `read_bus(address)`         | `address` 的第 0 位为 0 时执行 `read()`，为 1 时执行 `read_status()`                    |
| `step(count=None)`          | 运行 `count` 条指令，省略 `count` 时运行 `gap` 条                                       |
| `elapsed(master_clocks)`    | 运行部件在这么多个主机主时钟内执行的指令数。返回该部件                                  |
| `waited()`                  | 单步运行直到部件发出请求，最多 `patience` 条指令。发出请求时为 True                     |
| `settle()`                  | 即 `waited()`，部件始终未发出请求时抛出 `NeverReady`                                    |
| `reset()`                   | 重建处理器，重新加载同样的镜像字节并再次启动。返回该部件                                |

### 状态

| 属性              | 含义                                                                              |
| :---------------- | :-------------------------------------------------------------------------------- |
| `model`, `part`   | 规范型号名                                                                        |
| `identity`        | 镜像的 `Identity`：`part`、`processor`、`revision`、`program_words`、`data_words` |
| `processor`       | 镜像运行所在的处理器，这里的每个部件都是 `upd7725`                                |
| `asking`          | RQM 置位时为 True                                                                 |
| `pending_output`  | 部件发出请求时为 1，否则为 0                                                      |
| `clock`           | 部件的时钟，单位 Hz                                                               |
| `gap`, `patience` | 上面的两个选项，可写                                                              |
| `core`            | 运行镜像的 `upd7725` 处理器                                                       |
| `console`         | 上述调用所经过的处理器主机端口                                                    |

### 模块内容

| 名称                                                                     | 内容                                                                                                           |
| :----------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------- |
| `snesdsp.MODELS`                                                         | 六个 `Model` 记录，以规范名称为键。每个记录有 `name`、`aliases`、`summary` 和 `image`                          |
| `snesdsp.Model`                                                          | 这些记录的类型                                                                                                 |
| `snesdsp.SHARES_MICROCODE`                                               | `{"dsp1a": "dsp1"}`，唯一一个运行另一部件镜像的部件                                                            |
| `snesdsp.available(held=None)`                                           | 镜像在本机上的部件，形式为部件名到 `(identity, path)` 的映射。传入形状相同的映射 `held` 时，读取它而不进行搜索 |
| `snesdsp.why_not(held=None)`                                             | 至少有一个部件能构建时为 `None`，否则为说明为何一个都无法构建的句子。接受同样的 `held`                         |
| `snesdsp.MASTER_CLOCK`                                                   | `21477273`，主机的主时钟，单位 Hz，是 NTSC 彩色副载波的六倍                                                    |
| `snesdsp.DSP_CLOCK`                                                      | `7600000`，部件的时钟，单位 Hz，每个时钟一条指令                                                               |
| `snesdsp.GAP`                                                            | `14`，`gap` 的默认值                                                                                           |
| `snesdsp.clock_of(model)`                                                | 该型号的时钟，单位 Hz。名称未知时抛出 `UnknownModelError`                                                      |
| `snesdsp.steps_for(master_clocks, clock=DSP_CLOCK, master=MASTER_CLOCK)` | 这么多个主时钟内运行的指令数，向下取整                                                                         |
| `snesdsp.__version__`                                                    | 已安装的版本                                                                                                   |
| `snesdsp.identify(image, catalogue=None)`                                | 镜像的 `Identity`，按 SHA-256 在清单或形状相同的映射 `catalogue` 中查找。会抛出 `Unrecognised` 或 `Corrupt`    |
| `snesdsp.digests_of(image)`                                              | 镜像的 CRC32、MD5、SHA-1 和 SHA-256，以 `crc32`、`md5`、`sha1` 和 `sha256` 为键的小写十六进制                  |
| `snesdsp.directories(environment=None)`                                  | 搜索按顺序读取的目录，取自 `environment` 或进程环境                                                            |
| `snesdsp.search(places=None, catalogue=None)`                            | 在 `places` 或 `directories()` 中找到的每个镜像，以 `(identity, path)` 对给出，每个部件以最先找到的文件为准    |

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

六十分之一秒的主时钟相当于部件的 126,666 条指令。

### 错误

| 错误                | 抛出时机                                                                                      |
| :------------------ | :-------------------------------------------------------------------------------------------- |
| `UnknownModelError` | 缺少型号名，或没有型号使用该名称。消息会列出所有型号                                          |
| `NoFirmware`        | 处理器子模块未检出、找不到该部件的镜像，或传入了 `image` 却没有 `identity`                    |
| `NeverReady`        | `settle()` 运行了 `patience` 条指令，部件始终未发出请求                                       |
| `Unrecognised`      | 传给 `snesdsp.identify` 的字节的 SHA-256 与清单中任何镜像都不符。消息会说明该文件最可能是什么 |
| `Corrupt`           | 镜像的 SHA-256 匹配，但与清单记录的另一个摘要不一致                                           |
| `WrongShape`        | `image` 的长度不是其 `identity` 所需的长度：每个程序字 3 字节，每个数据字 2 字节              |

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

这个示例直接传入镜像，因此不会搜索任何目录。每个镜像都是 2,048 个程序字和 1,024 个数据字。少两个字节的文件会因长度被拒绝，同样的字节反转后会因内容被拒绝。

<a id="the-microcode-you-supply"></a>

## 你提供的微码

这里不包含微码，不下载微码，也不链接到微码。每个镜像在任何一个字节运行之前都先通过 SHA-256 识别。[`snesdsp/artifacts.manifest.json`](snesdsp/artifacts.manifest.json) 保存这些摘要。

| 镜像    | 运行它的部件    | 字节数 | CRC32      | SHA-256                                                            |
| :------ | :-------------- | -----: | :--------- | :----------------------------------------------------------------- |
| `dsp1`  | `dsp1`, `dsp1a` |  8,192 | `27124599` | `5f2e5ed06b362be023b978b5978813ecb9a07c76592454b45c2a1ed17a0de349` |
| `dsp1b` | `dsp1b`         |  8,192 | `588279b4` | `4d42db0f36faef263d6b93f508e8c1c4ae8fc2605fd35e3390ecc02905cd420c` |
| `dsp2`  | `dsp2`          |  8,192 | `f0221c90` | `5efbdf96ed0652790855225964f3e90e6a4d466cfa64df25b110933c6cf94ea1` |
| `dsp3`  | `dsp3`          |  8,192 | `e3b54e6a` | `2e635f72e4d4681148bc35429421c9b946e4f407590e74e31b93b8987b63ba90` |
| `dsp4`  | `dsp4`          |  8,192 | `ca09e176` | `63ede17322541c191ed1fdf683872554a0a57306496afc43c59de7c01a6e764a` |

搜索会按顺序从以下目录读取以 `.bin` 或 `.rom` 结尾的文件，为某个部件找到的第一个文件胜出：

1. `SNES_DSP_FIRMWARE_DIR` 中的每个目录，分隔方式与操作系统分隔 `PATH` 的方式相同。
2. `UPD7725_FIRMWARE_DIR` 中的每个目录，这是本成员曾与 snes-st-python 共用的名称。
3. 存放本检出目录的目录中的 [`firmware/`](firmware/README.md)，用于本项目作为另一个项目子模块的情况。
4. 本检出目录中的 [`firmware/`](firmware/README.md)。

SHA-256 不在清单中的文件会被搜索跳过。如果把它交给 `snesdsp.identify`，它会被拒绝并附上诊断：拷贝机文件头、字节交换的转储和已知的坏转储都会被识别并指出。

确认你持有的副本：

```bash
shasum -a 256 firmware/dsp1.bin                 # macOS
sha256sum firmware/dsp1.bin                     # Linux
certutil -hashfile firmware\dsp1.bin SHA256     # Windows
```

## 像主机那样驱动它

主机通过地址访问部件。该地址的第 0 位选择端口：0 是数据端口，1 是状态寄存器。更高的位都不参与译码，因此一个部件会在整个地址窗口内应答。

部件以 7,600,000 Hz 每个时钟运行一条指令。主机以 21,477,273 Hz 计数主时钟，一次慢速卡带访问花费其中 8 个。65816 向长地址的一次存储需要 5 个周期，因此主机在两次访问之间最少能留给部件 40 个主时钟，也就是 14 条指令。这就是 `gap` 的默认值。花费时间更长的主机用 `elapsed` 说明这一点。

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

奇数地址读取状态寄存器，启动后 RQM 已置位。偶数地址传送 DSP-1 命令 `0x00`（一次乘法）及其两个参数。`0x4000 * 0x2000 >> 15` 等于 `0x1000`。

## 驱动每个部件

下面的每个输出都是部件自身微码给出的答案。[`conformance/documented.py`](conformance/documented.py) 在每次具备镜像的流水线运行中，都会对这些部件执行同样的交换。

### DSP-1

先发一个命令字节，再发小端序的参数字，答案也以同样方式返回。命令 `0x00` 将两个定点字相乘。

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

不存在 DSP-1A 镜像。构建 DSP-1A 时运行的是 DSP-1 的镜像。

```python
from snesdsp import Chip

part = Chip("dsp1a")
print(part.model, part.identity.part)
```

```
dsp1a dsp1
```

### DSP-1B

DSP-1B 运行它自己的镜像。它的修正不在乘法中，乘法在这里同样得到 `0x1000`。修正所在之处见 [它对吗](#is-it-right)。

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

命令 `0x09` 是整数乘法，而不是定点乘法。

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

DSP-3 一次接收一个字。命令 `0x001c` 以最后写入的字作答，只要有读取就一直如此。

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

snes9x 的 DSP-3 代码对这条命令回答两个零字。[`conformance/divergences.json`](conformance/divergences.json) 记录了这一分歧，[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 说明了怎样才能确定是否有游戏发送这条命令。

### DSP-4

DSP-4 接收一个命令字和若干参数，然后分批作答。

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

## 它对吗

命令计算出的结果就是程序的答案，因此这里的检查约束的是程序周围的一切：端口、节奏、每个镜像的身份，以及真实游戏进行的交换。

| 检查                                                       | 命令                                                                                   | 需要镜像 |
| :--------------------------------------------------------- | :------------------------------------------------------------------------------------- | :------: |
| 处理器，逐条指令                                           | 在 [nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python) 中 |    否    |
| 端口、节奏、状态寄存器和总线译码                           | 每个模块旁边的单元测试                                                                 |    否    |
| 每个型号、别名和镜像，以及每个镜像都有一个起决定作用的摘要 | 每个模块旁边的单元测试                                                                 |    否    |
| 卡带进行的每个交换都得到回答                               | `python3 -m conformance.against_cartridges <part>`                                     |    是    |
| 每个部件的回答仍与采集语料时相同                           | `python3 -m conformance.answers`                                                       |    是    |
| DSP-1 和 DSP-1B 镜像仍在先前发现的位置上不一致             | `python3 -m conformance.masks`                                                         |    是    |
| 没有任何随附的微码使返回栈超过 4 层                        | `python3 -m conformance.stack`                                                         |    是    |
| 每个 README 示例都打印出它声称的内容                       | `python3 -m conformance.documented`                                                    |    是    |
| 单步运行保持在每秒 150,000 条指令以上                      | `python3 -m conformance.speed`                                                         |    是    |

每个需要镜像的工具在没有镜像时都会以 2 退出并说明缺少什么，而不是判为通过。

### 交换

游戏发送的内容由 [snes-driver-python](https://github.com/gufranco/snes-driver-python) 从卡带中读出，它会反汇编驱动部件的例程。每个结果是一个形态：访问的顺序和宽度，不含载荷。[`cartridges.manifest.json`](cartridges.manifest.json) 以摘要标识每个卡带，任何卡带的字节都不会被存储。

| 部件  | 卡带 | 形态 | 在部件上回放 | 访问位置 |
| :---- | ---: | ---: | -----------: | -------: |
| DSP-1 |   29 |   50 |           22 |    1,384 |
| DSP-2 |    3 |   13 |            1 |      270 |
| DSP-3 |    1 |   20 |           10 |      182 |
| DSP-4 |    3 |   38 |           29 |      910 |

DSP-1 的各行来自 29 个不同的驱动程序。DSP-3 的各行来自一个卡带，即唯一搭载该部件的卡带。

形态不含载荷，因此它的字节由固定种子生成。部件以沉默回应的形态会在 256 个命令字节下各回放一次，只有全部 256 次都沉默时才算沉默。有四个形态先读后写，DSP-1 上一个，DSP-3 上两个，DSP-4 上一个：在主机上它们读取的是先前某次交换留下的内容，因此单独报告，而不算作沉默。其余每个形态都会得到回答。

```bash
python3 -m conformance.against_cartridges dsp1
python3 -m conformance.answers --take dsp1
python3 -m conformance.answers
python3 -m conformance.record
```

`against_cartridges` 接收一个部件，未指定时为 `dsp3`，任何交换保持沉默时以 1 退出。DSP-1A 和 DSP-1B 回放 DSP-1 的形状，因为从转储无法判断一块 DSP-1 电路板装的是哪一版掩膜，而三者接受相同的命令。`answers` 接收部件名，默认全部，回答发生变化时以 1 退出，本机上的镜像不是采集语料时所用的镜像时以 2 退出。即使没有镜像，某个部件没有语料，或其语料并非按今天扫描的形状以相同顺序采集时，也以 1 退出：所有载荷都来自同一个带种子的随机序列，一个形状移动了，其后每个形状的载荷都会改变。`--take` 记录回答而不是检查回答。`record` 重新读取 [`cartridges/`](cartridges) 或 `SNES_CARTRIDGE_DIR` 中的每个卡带，一个都没有时以 2 退出。

### DSP-1B 的修正

DSP-1B 修正了一处算术错误，因此必然有某个输入会让两个掩模不一致。`python3 -m conformance.masks --sweep` 让两个镜像遍历 256 个命令字节和 16 组参数，每组 6 个字。它找到 6 个命令字节：`0x04`、`0x0b`、`0x1b`、`0x24`、`0x2b` 和 `0x3b`，它们在一组参数上从答案的第三个字起出现差异。在这个空间内没有其他差异。`python3 -m conformance.masks` 会重新推导这 6 个，任何一个发生变化或变得一致时以 1 退出。

### 证据从何而来

| 证据                             | 能确定什么                                 | 不能确定什么                                                                            |
| :------------------------------- | :----------------------------------------- | :-------------------------------------------------------------------------------------- |
| NEC 的数据手册，经由处理器的记录 | 位宽、存储器大小、4 层栈、每条指令的时钟数 | NEC 没有印出的行为                                                                      |
| 在该处理器上运行的微码           | 每条命令计算什么                           | 端口是否在正确的时刻把正确的字节交给它                                                  |
| 从卡带中读出的交换               | 部件会回答已发售游戏提出的请求             | 任何游戏都没有提出的请求                                                                |
| 同一部件的行为模型               | 什么都不能：从不遵循它                     | 仅在其不一致之处记录，见 [`conformance/divergences.json`](conformance/divergences.json) |

Nintendo 没有公布这些部件的任何资料。节奏、启动长度以及第 0 位以上的译码都是界限，[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 列出了每一项以及能确定它的测量。[`conformance/hardware.json`](conformance/hardware.json) 记录了权威顺序以及本成员与什么进行比较。

## 参与开发

| 需求                           | 位置                                                                                    |
| :----------------------------- | :-------------------------------------------------------------------------------------- |
| 每项门禁检查及其运行顺序       | [CONTRIBUTING.md](CONTRIBUTING.md)                                                      |
| 面向编程代理的同样内容         | [AGENTS.md](AGENTS.md)                                                                  |
| 本仓库与家族其余成员共用的标准 | [FAMILY.md](FAMILY.md)                                                                  |
| 缺陷报告和错误答案             | [GitHub Issues](https://github.com/gufranco/snes-dsp-python/issues)，附上诊断脚本的输出 |
| 安全报告                       | [SECURITY.md](SECURITY.md)                                                              |

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

每个模块旁边都有一个名为 `<module>.test.py` 的测试文件，每个都能单独运行。覆盖率是一项硬性门禁检查，要求 100% 语句和分支覆盖。吞吐量下限在覆盖率步骤之外运行。切勿把微码或卡带附在报告中：用 SHA-256 就能标识它们。

## 参考资料

- NEC，_uPD7725/uPD96050 Digital Signal Processor_ 数据手册。从中摘取的每个事实都连同页码记录在 [nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python) 中，本仓库将其作为子模块携带。该手册不可再分发，也不在本仓库中。
- snes9x，提交 `2971061cf07fdc6fc7d18883edf4e648eb16a6d2` 中的 `dsp3.cpp`，https://github.com/snes9xgit/snes9x ，仅为说明那一处已记录的分歧而阅读。这里没有任何内容遵循它。
- [snes-driver-python](https://github.com/gufranco/snes-driver-python)，用于读取卡带自身代码发送给其协处理器的内容。
- 读者自己拥有的零售版卡带，每个在读取前都先根据 [`cartridges.manifest.json`](cartridges.manifest.json) 以摘要确认。

## 引用本项目

[CITATION.cff](CITATION.cff) 在每次发布时由写入包版本的脚本更新。

## 许可证

MIT。见 [LICENSE](LICENSE)。

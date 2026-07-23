# PESMaker VASP AIMD → NEP Toolkit

本目录提供两个独立于 PESMaker 工作流的辅助脚本，用于从单个 VASP AIMD 目录生成 GPUMD/NEP 可用的 `train.xyz`。

| 脚本 | 选择方式 | 适合用途 |
| --- | --- | --- |
| `aimd_fps_to_nep.py` | PESMaker 最远点采样（FPS） | 根据构型差异选择代表性结构 |
| `aimd_interval_to_nep.py` | 等间距采样 | 按固定轨迹帧间隔抽稀 AIMD 时间序列 |
| `merge_aimd_train_xyz.py` | 指定来源合并 | 将多个正式 FPS 或 Interval `train.xyz` 合并并记录来源范围 |

两个脚本都不会修改或导入 PESMaker 私有源码，而是调用正式命令：

```text
python -m pesmaker select <自动生成的 YAML>
```

## 共同工作流程

```text
XDATCAR
  → PESMaker 选择构型
  → 根据 manifest.jsonl 和 NBLOCK 定位 OUTCAR 离子步
  → 流式提取 TOTEN、力和 stress
  → 构型匹配与标签检查
  → train.xyz
```

OUTCAR 一次只解析一个离子步，不会一次性把全部帧读入内存。FPS 仍需要 PESMaker 读取 XDATCAR 并计算几何特征；等间距脚本会先以文本流方式统计 XDATCAR 帧数。

## 适用范围

当前版本支持：

- 单个 VASP AIMD 目录。
- 固定晶胞轨迹。
- AIMD 过程中原子数和原子顺序保持不变。
- XDATCAR 与 OUTCAR 来自同一次计算。
- 没有人工拼接的 XDATCAR 或 OUTCAR。
- 三维周期性体系。

当前版本不处理：

- 变胞 AIMD。
- 多个 AIMD 目录合并。
- 拼接或混用的续算轨迹。
- train/test 划分。
- 电子步收敛质量过滤。
- 已有输出目录覆盖或续跑。

## 环境要求

必须使用已经安装 PESMaker 的同一个 Python 环境运行脚本。环境至少需要：

- Python 3.10 或更高版本。
- PESMaker。
- ASE。
- NumPy。
- PyYAML。
- Matplotlib（FPS 绘图需要）。

可以使用以下命令检查环境：

```bash
python -m pesmaker --help
python -c "import ase, numpy, yaml; print(ase.__version__)"
```

脚本通过 `sys.executable -m pesmaker select` 启动 PESMaker。因此，运行脚本的 Python 环境必须就是安装 PESMaker 的环境。

## 预期输入

`--aimd-dir` 必须明确指向包含以下文件的目录：

```text
VASP_AIMD/
├── INCAR
├── XDATCAR
└── OUTCAR
```

三个 VASP 文件只读打开。脚本不会修改、移动、删除、压缩或重命名它们。

## FPS 脚本用法

```bash
python PESMaker_AIMD_Toolkit/aimd_fps_to_nep.py \
  --aimd-dir /absolute/path/to/VASP_AIMD \
  --max-count 200 \
  --min-distance 0.0
```

参数：

| 参数 | 是否必填 | 说明 |
| --- | --- | --- |
| `--aimd-dir` | 是 | 包含 INCAR、XDATCAR 和 OUTCAR 的目录 |
| `--max-count` | 是 | FPS 最多选择多少个构型，必须是正整数 |
| `--min-distance` | 否 | PESMaker 简单几何描述符空间中的最小距离，默认 `0.0`，不是 Å |

首次使用建议保持 `--min-distance 0.0`，仅通过 `--max-count` 控制数量。

FPS 输出目录固定为：

```text
<aimd-dir>/PESMakerToolkit_AIMD_FPS_to_NEP/
```

成功后的预期输出：

```text
PESMakerToolkit_AIMD_FPS_to_NEP/
├── train.xyz
├── selected.xyz
├── manifest.jsonl
├── selection_features.npy
├── fps_selection.png
├── frame_mapping.jsonl
├── pesmaker_fps.yaml
└── toolkit.log
```

## 等间距脚本用法

最简调用：

```bash
python PESMaker_AIMD_Toolkit/aimd_interval_to_nep.py \
  --aimd-dir /absolute/path/to/VASP_AIMD \
  --interval 100
```

指定起始帧和结束帧：

```bash
python PESMaker_AIMD_Toolkit/aimd_interval_to_nep.py \
  --aimd-dir /absolute/path/to/VASP_AIMD \
  --interval 100 \
  --start-frame 1000 \
  --end-frame 10000
```

参数：

| 参数 | 是否必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--aimd-dir` | 是 | 无 | 包含 INCAR、XDATCAR 和 OUTCAR 的目录 |
| `--interval` | 是 | 无 | 每隔多少个 XDATCAR 帧选择一个构型，必须是正整数 |
| `--start-frame` | 否 | `0` | 允许选择的第一个 XDATCAR 帧，采用零基编号 |
| `--end-frame` | 否 | 最后一帧 | 允许选择的最后一个 XDATCAR 帧，采用包含式边界 |

### 帧号和结束边界

`start-frame=0` 表示 XDATCAR 中保存的第一帧，不表示 VASP 离子步 0。

例如：

```text
--start-frame 100
--end-frame 1000
--interval 200
```

实际选择：

```text
100, 300, 500, 700, 900
```

`end-frame` 是允许范围的包含式上边界，但只有落在等间距序列上的帧才会被选择。脚本不会为了包含结束帧而额外加入一个非等间距构型。

如果不设置 `--end-frame`，采样范围延伸到 XDATCAR 最后一帧。显式结束帧超过轨迹范围时会报错，不会静默截断。

### interval 与 NBLOCK

`--interval` 的单位是 XDATCAR 帧，不是 VASP 离子步。候选 OUTCAR 离子步按以下公式计算：

```text
ionic_step = (source_frame + 1) × NBLOCK
```

例如：

```text
NBLOCK = 5
--interval 100
```

相邻训练构型对应的 VASP 离子步间隔约为：

```text
100 × 5 = 500
```

帧号公式只负责候选定位；每个候选仍必须通过晶胞、元素顺序和周期性坐标比较。

### 等间距脚本预期输出

输出目录固定为：

```text
<aimd-dir>/PESMakerToolkit_AIMD_Interval_to_NEP/
```

成功后的预期输出：

```text
PESMakerToolkit_AIMD_Interval_to_NEP/
├── train.xyz
├── selected.xyz
├── manifest.jsonl
├── frame_mapping.jsonl
├── pesmaker_interval.yaml
└── toolkit.log
```

等间距采样不计算 FPS 描述符，因此不会生成 `selection_features.npy` 或 `fps_selection.png`。

## 合并脚本用途与语法

`merge_aimd_train_xyz.py` 用于合并多个 AIMD 子目录中已经生成并验证的正式 `train.xyz`。它不重新解析 AIMD、不调用 PESMaker，也不修改任何 PESMaker 源码。

用户必须明确指定合并来源，不允许脚本自动猜测或混合 FPS 与 Interval：

```bash
python PESMaker_AIMD_Toolkit/merge_aimd_train_xyz.py \
  --aimd-root /absolute/path/to/AIMD_ROOT \
  --source interval
```

合并 FPS 来源：

```bash
python PESMaker_AIMD_Toolkit/merge_aimd_train_xyz.py \
  --aimd-root /absolute/path/to/AIMD_ROOT \
  --source fps
```

参数：

| 参数 | 是否必填 | 说明 |
| --- | --- | --- |
| `--aimd-root` | 是 | 直接包含多个 VASP AIMD 运行目录的根目录 |
| `--source` | 是 | 只能是 `interval` 或 `fps`，不提供默认值 |

### 预期输入结构

`--aimd-root` 的直接子目录中，正式 AIMD 目录必须同时包含 INCAR、XDATCAR 和 OUTCAR：

```text
AIMD_ROOT/
├── aimd_case_01/
│   ├── INCAR
│   ├── XDATCAR
│   ├── OUTCAR
│   ├── PESMakerToolkit_AIMD_Interval_to_NEP/
│   │   └── train.xyz
│   └── PESMakerToolkit_AIMD_FPS_to_NEP/
│       └── train.xyz
├── aimd_case_02/
│   ├── INCAR
│   ├── XDATCAR
│   ├── OUTCAR
│   └── ...
└── scripts/                 # 不含三项 VASP 文件，因此忽略
```

来源参数和实际查找路径严格对应：

```text
--source interval
→ <AIMD子目录>/PESMakerToolkit_AIMD_Interval_to_NEP/train.xyz

--source fps
→ <AIMD子目录>/PESMakerToolkit_AIMD_FPS_to_NEP/train.xyz
```

脚本只检查 AIMD 根目录的直接子目录，不递归搜索任意 `train.xyz`。因此不会误收集 `_smoke_test`、`_failed_*` 或其他临时目录。

每一个识别出的正式 AIMD 子目录都必须存在所选来源的 `train.xyz`。如果任一目录缺失，脚本会在创建合并输出前失败并列出缺失目录，不会静默跳过。

### 合并输出目录

输出位于 AIMD 根目录的同级目录，名称明确包含来源：

```text
<aimd-root上级目录>/Merged_Interval_NEP_TrainXYZ/
<aimd-root上级目录>/Merged_FPS_NEP_TrainXYZ/
```

例如：

```text
/mnt/d/ResearchData/
├── growthDatasetPreparation_AIMD/
└── Merged_Interval_NEP_TrainXYZ/
```

输出文件结构：

```text
Merged_Interval_NEP_TrainXYZ/
├── train.xyz
├── source_ranges.tsv
├── README.md
└── merge.log
```

- `train.xyz`：按照 AIMD 目录名称不区分大小写排序后直接拼接的训练集，不重新格式化标签。
- `source_ranges.tsv`：机器可读的来源、帧数、元素、原子数和合并范围。
- `README.md`：自动生成的人类可读来源表、目录说明、合并规则和复现命令。
- `merge.log`：来源验证、帧数范围、总帧数和失败原因。

`source_ranges.tsv` 包含：

```text
order
sampling_source
aimd_directory
source_train_xyz
frame_count
atom_count
elements
merged_start_0based
merged_end_0based
merged_start_1based
merged_end_1based
```

零基和一基范围均为包含式。脚本根据实际读取帧数动态计算范围，不硬编码当前数据集的数量。

### 合并验证与安全行为

每个来源和最终合并文件均使用 ASE 流式验证：

- extxyz 至少包含一帧。
- 晶胞、位置、Energy、force 和 Virial 均存在且为有限值。
- force 形状严格为 `N×3`。
- Virial 恰好包含 9 个分量。
- 合并总帧数等于所有来源帧数之和。
- 合并元素集合与来源元素集合一致。

合并过程先生成：

```text
train.xyz.partial
source_ranges.tsv.partial
README.md.partial
```

全部验证通过后才改名为正式文件，其中 `train.xyz` 最后改名。输出目录已经存在时脚本拒绝覆盖。

第一版不会执行随机打乱、去重、二次 FPS、train/test 划分或标签单位转换。

## WSL 调用示例

Windows D 盘在 WSL 中通常映射到 `/mnt/d`。例如：

```bash
conda run -n pesmaker python \
  /mnt/d/ResearchData/PESMaker_litupVer/PESMaker_AIMD_Toolkit/aimd_interval_to_nep.py \
  --aimd-dir /mnt/d/ResearchData/example_AIMD \
  --interval 100 \
  --start-frame 0
```

查看命令行帮助：

```bash
python aimd_fps_to_nep.py --help
python aimd_interval_to_nep.py --help
python merge_aimd_train_xyz.py --help
```

## 输出文件说明

| 文件 | 用途 |
| --- | --- |
| `train.xyz` | 最终 NEP 训练数据，每帧包含总能量、力和总 Virial |
| `selected.xyz` | PESMaker 选中的无标签构型 |
| `manifest.jsonl` | PESMaker 选择清单，包含原始零基 `source_frame` |
| `frame_mapping.jsonl` | `train.xyz` 帧与 XDATCAR/OUTCAR 帧号的对应关系 |
| `pesmaker_fps.yaml` | FPS 脚本自动生成的 PESMaker 配置 |
| `pesmaker_interval.yaml` | 等间距脚本自动生成的 PESMaker 配置 |
| `selection_features.npy` | FPS 使用的简单几何特征 |
| `fps_selection.png` | FPS 选择过程图 |
| `toolkit.log` | 参数、路径、NBLOCK、帧数、标签范围、几何偏差和错误原因 |

两个脚本都会拒绝覆盖已存在的身份目录，也不会自动创建编号子目录。

## 构型与标签检查

每个选中帧必须满足：

- 原子数完全一致。
- 元素及原子顺序完全一致。
- 固定晶胞矩阵元素最大差不超过 `1e-4 Å`。
- 周期性最小镜像下最大原子位移不超过 `1e-4 Å`。
- `free_energy`、力和 stress 均存在且为有限值。
- 力数组形状严格为 `N×3`。
- 对应离子步能在 OUTCAR 中找到。

任一选中帧不满足要求时，整个转换失败，不会生成正式 `train.xyz`。

## train.xyz 标签定义

每个构型使用 GPUMD/NEP 扩展 XYZ 格式：

```text
Lattice="ax ay az bx by bz cx cy cz"
Energy=<total energy in eV>
Properties=species:S:1:pos:R:3:force:R:3
Virial="vxx vxy vxz vyx vyy vyz vzx vzy vzz"
pbc="T T T"
```

- `Energy`：VASP `free energy TOTEN`，单位 eV，是总能量。
- `force`：每个原子的力，单位 eV/Å。
- `Virial`：整个构型的 3×3 总 Virial，单位 eV，不是每原子值。

Virial 转换采用：

```text
Virial = -V × stress_ASE
```

ASE 使用拉伸为正的 stress 约定，转换后的总 Virial 符合 GPUMD/NEP 使用的符号约定。

## 安全输出与失败行为

脚本先写入：

```text
train.xyz.partial
frame_mapping.jsonl.partial
```

所有选中帧都匹配并通过标签检查后，才改名为正式文件：

```text
train.xyz
frame_mapping.jsonl
```

如果失败：

- 不生成正式 `train.xyz`。
- 已完成的选择结果和 `toolkit.log` 会保留。
- `.partial` 文件可能保留，但不能用于训练。
- 失败原因会写入日志并显示在终端。

## 常见错误

### 输出目录已经存在

脚本不会覆盖已有结果：

```text
Error: output directory already exists; refusing to overwrite
```

请先检查已有 `train.xyz` 和 `toolkit.log`，再决定是否保留或移走目录。

### 构型不匹配

常见原因包括：

- XDATCAR 与 OUTCAR 不是同一次计算。
- 文件被拼接或截断。
- INCAR 中的 `NBLOCK` 与实际轨迹写出不一致。
- AIMD 使用变胞设置。
- 原子顺序被其他工具修改。

### 缺少能量、力或 stress

脚本不会用其他能量定义代替 TOTEN，也不会生成缺少 Virial 的训练帧。应检查 OUTCAR 是否完整，以及相应离子步是否正常结束。

## 已完成的真实数据验证

FPS 脚本已在一个固定晶胞 VASP AIMD 目录上完成端到端测试：

- XDATCAR：16,851 帧。
- OUTCAR：约 1.46 GB。
- FPS 测试选择：5 帧。
- 选中离子步：1、5883、10596、14036、16583。
- 每帧原子数：156。
- `train.xyz` 可由 ASE 重新读取。
- TOTEN 与 PESMaker `collect` 解析结果一致。
- Virial 最大差约 `6.54×10⁻⁵ eV`，来自 OUTCAR 文本打印精度。

等间距脚本已在同一条 16,851 帧轨迹上使用以下参数完成端到端测试：

```text
--start-frame 100
--end-frame 16500
--interval 4000
```

验证结果：

- 实际源帧：100、4100、8100、12100、16100。
- 对应 OUTCAR 离子步：101、4101、8101、12101、16101（`NBLOCK=1`）。
- `manifest.jsonl`、`frame_mapping.jsonl` 和预期帧号完全一致。
- 5 个结构均包含有限的 Energy、`156×3` force 和 9 个 Virial 分量。
- `train.xyz` 可由 ASE 重新读取。
- 没有残留 `.partial` 文件。

真实测试只能证明对应数据及当前适用范围内的流程可用，不能替代对其他 VASP 版本、变胞或拼接轨迹的单独验证。

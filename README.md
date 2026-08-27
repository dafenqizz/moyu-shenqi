# 摸鱼神器（PySide6）

一个基于 Python 和 PySide6 的 Windows 桌面悬浮窗示例项目。它提供广告图片轮播、外部窗口接入、系统托盘和全局快捷键，适合作为 Qt 桌面浮窗交互的学习参考。

## 下载与运行

无需安装 Python。前往 [Releases 页面](https://github.com/dafenqizz/moyu-shenqi/releases) 下载最新版本的 `MoyuMask.exe`，双击即可在 Windows 上运行。

也可以直接下载当前版本：[MoyuMask.exe](https://github.com/dafenqizz/moyu-shenqi/releases/download/v1.0.0/MoyuMask.exe)。

如果 Windows SmartScreen 对未签名程序显示提示，请确认下载来源为本项目 Release 页面后，选择“更多信息”并点击“仍要运行”。

## 风险与安全提示

> 本工具仅用于个人本地娱乐与 PySide6 桌面交互学习，请勿在办公环境或违反所在组织规定的场景中使用。

- 只从本项目的 GitHub Release 下载二进制文件；不信任第三方重新分发的 EXE。
- 如需自行验证，建议本地使用 PyInstaller 编译源码。
- `v1.0.0` 使用 Python 3.12.4、PySide6 6.11.2、PyInstaller 6.22.2 构建。
- `MoyuMask.exe` 的 SHA-256：`2229df4b90e639bdd1707f0b41704758f273b5b2f9ceb33dadbb3bad80bb2aaa`。
- 运行前可将下载的 EXE 上传至 [VirusTotal](https://www.virustotal.com/) 进行多引擎扫描。PyInstaller 单文件程序可能触发误报，请结合下载来源、哈希值和扫描结果判断。

## 功能

- 无边框置顶悬浮窗
- 广告伪装模式
- 外部视频/浏览器窗口接入模式
- 系统托盘
- Windows 全局热键
- 窗口位置与大小记忆

## 注意事项

- 仅支持 Windows。
- 外部窗口接入依赖 Windows 窗口句柄；管理员权限运行或受保护的软件窗口可能无法接入。
- 请仅对自己拥有控制权的软件窗口使用接入功能。

## 环境安装

建议使用 Python 3.10+。

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 运行

```powershell
python app.py
```

广告页面默认轮播 `assets/` 内的三张图片。点击标题栏中的“图”按钮，可选择最多三张本地图片作为自定义广告素材。

## PyInstaller 打包

建议使用无控制台单文件模式：

```powershell
pyinstaller --noconsole --onefile --clean --name MoyuMask --add-data "assets;assets" app.py
```

## 交互说明

- 点击标题栏左侧黄色标签切换广告/视频模式
- 广告页默认每 3 秒轮播 `assets` 中的三张图片；点击顶部不明显的“图”按钮，可选择最多三张自定义广告图片，程序会自动保存并轮播
- 最小窗口尺寸为 `120x70`
- 两种模式都支持调整窗口大小；拖拽左、右、下三边或下方两个角即可缩放
- 点击“广告/视频”标签只切换内容，不会自动改变当前窗口大小；窗口位置和大小会自动记忆
- 视频模式中点击“拖拽选择窗口”，按住鼠标左键拖到浏览器或视频软件窗口后松开，即可尝试接入
- 接入后可点击右上角“清除当前窗口”，再重新选择其他窗口
- 视频页覆盖的左、右、下边缘也可以直接拖拽调整主窗口大小
- 再次点击“广告”会显示广告伪装界面，外部视频窗口会被广告层遮住
- `ESC`：先切回广告模式，再按一次隐藏到托盘
- `Ctrl+Alt+M`：老板键显示/隐藏窗口
- 右上角关闭按钮：静默隐藏到托盘，不弹出提示，也不直接退出
- 托盘菜单：显示窗口、切换模式、退出程序

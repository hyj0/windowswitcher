# Python Window Switcher

用键盘上的短字母标记快速切换 Windows 窗口或点击任务栏按钮。实现思路参考
[FastWindowSwitcher](https://github.com/JochenBaier/fastwindowswitcher)：

- Win32 API 枚举当前可见的顶层窗口；
- Microsoft UI Automation 枚举主、副任务栏中的按钮；
- PySide6 显示不抢焦点、鼠标可穿透的置顶字母标记；
- `RegisterHotKey` 注册全局快捷键，低级键盘钩子读取字母，匹配后激活窗口或调用
  任务栏按钮。

## 安装与运行

需要 Windows 10/11 和 Python 3.10+。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python windowswitcher.py
```

运行测试：

```powershell
python -m unittest discover -s tests -v
```

`tests/support/` 里是当初验证「快捷键不漏给前台应用」的目标窗口和按键辅助脚本。
`tests/test_key_isolation.py` 会真正按下 `Alt+Q`，大约需要半分钟；若本机已有切换器在跑，
或你不想发送真实按键，可设环境变量 `SKIP_INPUT_TESTS=1`。

程序启动后：

1. 按 `Alt+Q` 显示标记；
2. 输入标记上的字母，唯一标签会立即执行；
3. `Backspace` 删除已输入的字母；
4. `Esc` 取消；
5. 再按一次 `Alt+Q` 也会取消。

快捷键交给 Windows 的 `RegisterHotKey` 处理，前台应用不会收到这个按键。标记显示
期间会临时安装低级键盘钩子，把所有按键都拦下来，只有修饰键放行以免应用里的
`Alt`、`Ctrl` 卡住；退出标记模式后钩子立即卸载，正常打字不受影响。程序空闲时不
挂任何键盘钩子。

只有用户真正看得到的窗口才会分配字母：程序对每个候选标记位置做命中测试，被其他
窗口完全盖住的窗口不参与编号。窗口较宽时，同一个标签会在窗口顶部多处显示，部分
被遮挡时仍能找到。任务栏按钮的标签显示在按钮中央，被遮挡或滚动出可视范围的按钮
同样不分配字母。最小化窗口通过它对应的任务栏按钮切换。

## 已知限制

- Windows 不同版本的任务栏 UI Automation 结构会变化。读取失败时，顶层窗口切换
  仍然可用，并会在控制台记录警告。
- 若目标程序以管理员身份运行，而本程序不是管理员，Windows 的 UIPI 安全机制可能
  阻止激活或点击它；此时需以相同权限运行本程序，键盘钩子同样受此限制。
- 默认快捷键在 `windowswitcher.py` 的 `Switcher("alt+q")` 处配置，写法形如
  `ctrl+alt+space`、`win+f2`。快捷键被别的程序占用时启动会报错。
- 触发时会注入一次 `Ctrl` 轻敲，用来抵消 Windows 对孤立 `Alt`/`Win` 的处理
  （否则前台程序的菜单栏或开始菜单会被点亮）。

参考项目使用 GPL-3.0。本项目是独立的 Python 重写，没有复制其源码；标签顺序与交互
方式保持兼容，便于对照验证。

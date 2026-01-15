# 跨设备输入切换工具（原型）

通过局域网在设备间切换键盘与鼠标控制。一个设备运行主控端（捕获输入），另一台设备运行客户端（注入输入）。

## 依赖

- Python 3.9+
- `pip install -r requirements.txt`

说明：macOS 上可能需要为终端授予“辅助功能”权限。

## 使用方法

在目标设备启动客户端：

```bash
python -m src.client --bind 0.0.0.0 --port 54242
```

在拥有键盘/鼠标的设备启动主控端：

```bash
python -m src.controller --host <client-ip> --port 54242
```

使用快捷键切换远程模式（默认：`<ctrl>+<alt>+f9`）。

### 参数

- `--hotkey "<ctrl>+<alt>+f9"`：修改切换快捷键（pynput 格式）
- `--suppress-local`：远程模式生效时屏蔽本地输入
- `--verbose`：输出更多日志

## 注意事项

- 当前为局域网原型：无加密、无鉴权。
- 主控端发送相对鼠标位移，屏幕大小不同会有手感差异。
- 开启 `--suppress-local` 后，仅在远程模式下阻止本地输入。

## 后续方向

- 设备发现（mDNS）与配对
- TLS + 共享密钥鉴权
- 多客户端切换与屏幕边缘无缝接力

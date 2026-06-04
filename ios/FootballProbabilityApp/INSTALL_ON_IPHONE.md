# iPhone 安装说明

这个项目是个人自用 iOS APP，不需要上架 App Store。

## 最快方式：Xcode 直接安装到手机

1. 在 Mac 上安装完整 Xcode。
2. 执行：

   ```bash
   sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
   ```

3. 打开：

   ```text
   ios/FootballProbabilityApp/FootballProbabilityApp.xcodeproj
   ```

4. Xcode -> Settings -> Accounts，登录你的 Apple ID。
5. 选中项目 Target `FootballProbabilityApp`，进入 `Signing & Capabilities`：
   - 勾选 `Automatically manage signing`
   - Team 选择你的 Apple ID
   - Bundle Identifier 改成你自己的唯一值，例如 `com.yourname.footballprobability`
6. 用数据线连接 iPhone，手机上选择“信任此电脑”。
7. Xcode 顶部设备选择你的 iPhone，点击 Run。

如果你用的是免费 Apple ID，APP 通常 7 天后需要重新安装一次；付费 Apple Developer 账号有效期更长。

## 导出 IPA

满足下面条件后，可以运行：

```bash
cd ios/FootballProbabilityApp
chmod +x build_ipa.sh
./build_ipa.sh
```

生成位置：

```text
ios/FootballProbabilityApp/build/export/FootballProbabilityApp.ipa
```

注意：`.ipa` 必须被你的 Apple 开发证书和描述文件签名，否则 iPhone 不能安装。

## 后端地址

APP 默认连接：

```text
http://127.0.0.1:8910
```

这适合 iPhone 模拟器。真机需要把 `FootballAPIClient.swift` 里的地址改成电脑局域网 IP，例如：

```swift
http://192.168.1.23:8910
```

然后让手机和电脑连同一个 Wi-Fi，并启动后端：

```bash
python3 -c "from football_data_mcp.server import main; main()"
```

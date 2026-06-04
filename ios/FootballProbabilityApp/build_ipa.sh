#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$ROOT_DIR/FootballProbabilityApp.xcodeproj"
SCHEME="FootballProbabilityApp"
CONFIGURATION="Release"
BUILD_DIR="$ROOT_DIR/build"
ARCHIVE_PATH="$BUILD_DIR/$SCHEME.xcarchive"
EXPORT_PATH="$BUILD_DIR/export"
EXPORT_OPTIONS="$ROOT_DIR/ExportOptions.development.plist"

if ! xcodebuild -version >/dev/null 2>&1; then
  echo "错误：当前没有可用的完整 Xcode。请安装 Xcode，并执行："
  echo "sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
  exit 1
fi

if ! security find-identity -v -p codesigning | grep -q "Apple Development"; then
  echo "错误：没有找到 Apple Development 签名证书。"
  echo "请打开 Xcode -> Settings -> Accounts，登录 Apple ID，并在项目 Signing & Capabilities 里选择 Team。"
  exit 1
fi

mkdir -p "$BUILD_DIR"

xcodebuild archive \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration "$CONFIGURATION" \
  -destination "generic/platform=iOS" \
  -archivePath "$ARCHIVE_PATH" \
  -allowProvisioningUpdates

rm -rf "$EXPORT_PATH"
xcodebuild -exportArchive \
  -archivePath "$ARCHIVE_PATH" \
  -exportPath "$EXPORT_PATH" \
  -exportOptionsPlist "$EXPORT_OPTIONS" \
  -allowProvisioningUpdates

echo "IPA 已生成：$EXPORT_PATH/$SCHEME.ipa"

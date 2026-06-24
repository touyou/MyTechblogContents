---
title: "マルチプラットフォーム App Intents の構成 — Extension の SPM 化と Delegate 分離 (3/N)"
emoji: "📦"
type: "tech"
topics: ["AppIntents", "SwiftUI", "macOS", "watchOS", "Extension"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の 3 回目です。
前回は [TodoService の話 (2/N)](https://zenn.dev/touyou/articles/intenttodo_02_todoservice_dependency) をしましたが、今回は Extension target やマルチプラットフォームをまたいだコード共有の話です。

IntentTodo は最終的に以下の構成に落ち着いています。

```
Packages/
├── Domain/           # SwiftData モデル、共通 Entity、ActivityAttributes
├── Repository/       # データアクセス層 (Protocol + 実装)
├── TodoAppIntents/   # ★コア: Intent 定義 + ビジネスロジック (TodoService)
├── UI/               # メインアプリ SwiftUI Views (iOS/iPadOS/macOS/visionOS)
├── LiveActivity/     # ActivityKit 管理 + ロック画面 View (iOS 限定)
├── WidgetUI/         # ホームウィジェット View
└── WatchUI/          # watchOS View + Components + Complication (watchOS 限定)
```

そして、Extension target は宣言だけの薄いラッパーに保ちます。

```
IntentTodoWidget/                   # ホーム画面ウィジェット + コントロールセンター
├── IntentTodoWidget.swift          # Provider + Widget 宣言 (WidgetUI を import)
├── IntentTodoWidgetBundle.swift    # 全 Widget / Control をバンドル
├── Configuration/                  # WidgetConfigurationIntent
├── Controls/                       # ControlWidget 3 種
└── Helpers/WidgetModelContainer.swift

IntentTodoLiveActivity/             # ライブアクティビティ
├── IntentTodoLiveActivityBundle.swift
└── TodoLiveActivity.swift          # ActivityConfiguration (LiveActivity を import)

IntentTodoWatchApp/                 # watchOS アプリ
├── IntentTodoWatchApp.swift        # @main (WatchUI を import)
└── TodoComplication.swift          # コンプリケーション Widget 宣言
```

なぜこの構成にしたかを順番に整理します。

## Extension の中に View を書かない理由

最初は Extension target の中に直接 View を置いていました。
ところがこれをやると次のような不便が出てきます。

- **プレビューが効かない / 効きづらい**: Extension target の SwiftUI Preview は Xcode のサポートが薄く、ちょっとした View の修正がストレス
- **テストが書けない**: Extension target に `@testable import` がそもそも難しい
- **再利用できない**: Watch のコンプリケーション View と Widget の View はほぼ同じ表示を出したいケースがあるが、ターゲットが違うので共有できない
- **コンパイルが分かれる**: Extension ごとに別ターゲットでビルドされるので、地味にビルド時間が伸びる

これを解消するため、View・状態管理・データ取得ロジックを **すべて SPM パッケージに移送** しました。
Extension target には「ターゲット固有のスキャフォルド」 (`@main` の `WidgetBundle`、`ActivityConfiguration` など) しか残さない方針です。

## 切り出しのライン

`Packages/LiveActivity` を例にとると、こうなります。

- `LiveActivity/` パッケージ:
  - `TodoDeadlineActivityAttributes` (Domain と共有する ActivityAttributes)
  - `TodoLiveActivityManager` (`Activity<...>.request` などを叩く `@MainActor final class`)
  - `LiveActivityMonitor` (`@Query` で Todo を購読し、期限が近いものに対して Activity を起動する View)
  - ロック画面 / Dynamic Island 用の `View`
- `IntentTodoLiveActivity/` Extension target:
  - `IntentTodoLiveActivityBundle.swift` (`@main`)
  - `TodoLiveActivity.swift` (`ActivityConfiguration` で `LiveActivity` の View を組み合わせるだけ)

Extension target の `TodoLiveActivity.swift` はほぼこれだけになります。

```swift
import ActivityKit
import LiveActivity
import SwiftUI
import WidgetKit

struct TodoLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: TodoDeadlineActivityAttributes.self) { context in
            TodoLiveActivityLockScreenView(context: context)
        } dynamicIsland: { context in
            todoDynamicIsland(for: context)
        }
    }
}
```

これで View 周りはすべて `LiveActivity` パッケージのプレビューで触れるようになります。

## macOS native への対応 — Delegate 分離パターン

IntentTodo は当初 Catalyst で macOS をなんとなく動かしていましたが、`App Intents 中心設計` をきちんと適用するためには **macOS native** で動かしたい、という要件が出てきました。

ここで詰まったのが `UIApplicationDelegate` と `NSApplicationDelegate` の違いです。プロトコルが別物なので、同じクラスを両方に流用できません。

ただ、世の中ではよくある話で、Paul Hudson の[`swiftui-agent-skill`](https://github.com/twostraws/swiftui-agent-skill) や Swift by Sundell の記事で紹介されているのが「**Delegate を `#if` で分離して、本体ロジックは別のクラスに切り出して両方から使う**」というパターン。
IntentTodo もこれを採用しました。

```swift
@main
struct IntentTodoApp: App {
    #if os(iOS) || os(visionOS)
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    #elseif os(macOS)
    @NSApplicationDelegateAdaptor(MacAppDelegate.self) var appDelegate
    #endif

    init() {
        // ...
        #if os(iOS) || os(visionOS) || os(macOS)
        MainActor.assumeIsolated {
            NotificationHandler.shared.navigationModel = navigation
        }
        #endif
    }
}
```

`AppDelegate` (iOS/visionOS) と `MacAppDelegate` (macOS) はそれぞれ薄い委譲を書くだけで、本体ロジックは `NotificationHandler` という cross-platform 共通クラスに集約します。

```swift
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_: UIApplication, didFinishLaunchingWithOptions _: ...) -> Bool {
        NotificationHandler.shared.install()
        return true
    }
    // delegate methods は NotificationHandler に委譲
}

final class MacAppDelegate: NSObject, NSApplicationDelegate, UNUserNotificationCenterDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NotificationHandler.shared.install()
    }
    // 同上
}
```

`NotificationHandler` は `@MainActor` なシングルトンとして、通知タップ時に NavigationModel を書き換える、という責務を持ちます。
これでプラットフォーム固有のスキャフォルドだけ `#if` で分け、ロジックは 1 箇所にまとまります。

## pbxproj 側の落とし穴: platformFilter

ここまで頑張っても、macOS native でビルドしようとすると以下のエラーが出ることがあります。

> error: Building project IntentTodo with scheme IntentTodo and configuration Debug
> ... built for macOS but contains embedded content built for watchOS/iOS

これは Watch App / Live Activity Extension など、macOS でホストできない Embed 対象を macOS のビルドに混ぜようとして起きるエラー。
解決は pbxproj 側で `PBXBuildFile` の対応するエントリに `platformFilter = ios;` を付与することです。

```diff
- 46AFBEFE2F2D6E8000444306 /* IntentTodoLiveActivityExtension.appex in Embed Foundation Extensions */ = {isa = PBXBuildFile; fileRef = ...; settings = {ATTRIBUTES = (RemoveHeadersOnCopy, ); }; };
+ 46AFBEFE2F2D6E8000444306 /* IntentTodoLiveActivityExtension.appex in Embed Foundation Extensions */ = {isa = PBXBuildFile; fileRef = ...; platformFilter = ios; settings = {ATTRIBUTES = (RemoveHeadersOnCopy, ); }; };
```

Xcode の UI からは見えにくい設定なので、pbxproj を直接いじることになります。

## ターゲット依存と TodoService ファクトリ

前回 (2/N) で触れた `TodoService.swiftDataBacked(container:)` ファクトリの背景もここに繋がります。

`IntentTodoWatchApp` ターゲットが直接依存しているのは Domain / TodoAppIntents / WatchUI のみで、Repository パッケージは link していません。
それでも watchOS App プロセスの `AppDependencyManager` に TodoService を登録する必要があるとき、Repository を直接 import せずに済むファクトリがあると、pbxproj 側を触らなくて済みます。

```swift
// IntentTodoWatchApp.swift
@main
struct IntentTodoWatchApp: App {
    init() {
        let container = try! SharedModelContainer.createContainer()
        AppDependencyManager.shared.add(dependency: container)
        MainActor.assumeIsolated {
            let todoService = TodoService.swiftDataBacked(container: container)
            AppDependencyManager.shared.add(dependency: todoService)
        }
    }
    // ...
}
```

依存グラフを minimum に保ちながら、必要なところで service が組み立てられる、というバランスを取れています。

## (2026-06-24 追記) 別プロセス前提 — マイグレーションはアプリ本体に寄せる

ここまで書いたように Extension target は薄いスキャフォルドに留めますが、Widget / Live Activity は **アプリ本体とは別プロセス** で動く、という前提は変わりません。WWDC 2026 の "SwiftData Group Lab" (セッション 8017) で、この「別プロセスで同じ App Group のストアを共有する」構成の SwiftData マイグレーション指針が示されていました。要は **マイグレーションを担当するプロセスをアプリ本体 1 つに固定する** べき、というものです。

アプリ更新直後は本体より先に Widget が起動し得るので、Extension 側にマイグレーションプランを持たせると本体の移行と競合し得る、というのが理屈。Extension 構成の観点だと「View もデータ取得ロジックも SPM に寄せ、**マイグレーションの責務もアプリ本体に寄せる**」と覚えておくと収まりが良いです。SwiftData / CloudKit 側の具体的な書き方は [4/N](https://zenn.dev/touyou/articles/intenttodo_04_swiftdata_cloudkit) に書きました。(Group Lab はベータ時点の要約ベースなので、実際に `SchemaMigrationPlan` を入れる際は最新ドキュメントで再確認予定です)

## まとめ

- Extension target は薄いスキャフォルドに留めて、View / 状態管理 / データ取得は SPM パッケージに移送する
- macOS native 対応は `#if` で Delegate 分岐 + 共通実体クラスへ委譲
- pbxproj の `platformFilter = ios;` を見落とすと macOS ビルドで Embed エラーが出る
- ターゲット依存をなるべく minimum に保つため、`TodoService.swiftDataBacked(container:)` のような薄いファクトリを TodoAppIntents 側に置く

次回は [SwiftData + CloudKit 同期で踏んだスキーマ要件と落とし穴の話 (4/N)](https://zenn.dev/touyou/articles/intenttodo_04_swiftdata_cloudkit) を書きます。

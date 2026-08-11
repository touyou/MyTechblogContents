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

ここまで書いたように Extension target は薄いスキャフォルドに留めますが、Widget / Live Activity は **アプリ本体とは別プロセス** で動く、という前提は変わりません。WWDC 2026 の SwiftData Group Lab で、この「別プロセスで同じ App Group のストアを共有する」構成のマイグレーション指針が示された、という話を見かけました。要は **マイグレーションを担当するプロセスをアプリ本体 1 つに固定する** べき、というものです。

アプリ更新直後は本体より先に Widget が起動し得るので、Extension 側にマイグレーションプランを持たせると本体の移行と競合し得る、というのが理屈です。Extension 構成の観点だと「View もデータ取得ロジックも SPM に寄せ、**マイグレーションの責務もアプリ本体に寄せる**」と覚えておくと収まりが良いです。SwiftData / CloudKit 側の具体的な書き方は [4/N](https://zenn.dev/touyou/articles/intenttodo_04_swiftdata_cloudkit) に書きました。

ただこれ、**一次資料で裏を取れていない伝聞** です。当初はセッション 8017 として書いていたんですが、あとで手元に貯めたアーカイブを漁り直したら書き起こしが見つかりませんでした (出てくるのは別テーマの 8011 だけです)。Group Lab はライブ Q&A なので公式の書き起こしが出ないことも多いみたいです。指針そのものは SwiftData を複数プロセスで共有するときの一般則として妥当だと思うので運用は変えていませんが、「Apple がこう言った」ではなく「そう聞いた」くらいの確度で読んでもらえればと思います。

## (2026-07-08 追記) もう1つの例外: AppShortcutsProvider もアプリ本体に置く

上の「マイグレーションはアプリ本体に寄せる」と同じ形の話がもう1つ見つかりました。**`AppShortcutsProvider`（App Shortcuts の宣言）も SPM パッケージに置いてはいけません。**

`TodoAppIntents` パッケージ内に `AppShortcutsProvider` を置いても、ビルド・実行はエラーなく通ります。ところが Siri / Shortcuts アプリ / Spotlight に **App Shortcut が一切出てきません**。Intent 本体（`actions` / `entities` / `queries`）はパッケージから依存元アプリの統合メタデータへちゃんと集約されるのに、`AppShortcutsProvider.appShortcuts`（メタデータ上は `autoShortcuts`）だけは集約対象から外れる、というのが実体でした。

ビルド時に生成される `Metadata.appintents`（DerivedData 配下の `extract.actionsdata`、JSON）をパッケージ側とアプリ側で見比べると差が分かります。

| キー | パッケージ側 | アプリ側 |
|------|------|------|
| `actions` | 20 | 20 (集約される) |
| `entities` | 3 | 3 (集約される) |
| `queries` | 3 | 3 (集約される) |
| `autoShortcuts` | 8 | 0 (集約されない) |

`TodoAppShortcuts` をメインアプリターゲット直下へ移したところ、アプリ側の `autoShortcuts` が 0 → 8 になり、App Shortcut が実際に出るようになりました。Intent 本体は `public` のままパッケージに残し、`AppShortcutsProvider` からは `import TodoAppIntents` で参照する形にしています。

この不具合は **ビルドやコード補完のどのタイミングでも露見しません**。ビルドは通り、Intent 自体は Siri への直接指示や Widget からは機能し、警告も出ないので気付きにくいです。App Shortcut のフレーズだけが黙って欠落しているので、Shortcuts アプリを開いて目視確認するか、統合メタデータの `autoShortcuts` 件数を直接見ないと気付けませんでした。

## AppIntentsPackage をどこに宣言するか

`AppShortcutsProvider` の隣にある話として、`AppIntentsPackage` の置き場所にも触れておきます。IntentTodo は長らく「パッケージ側に 1 つだけ宣言して、**メインアプリターゲットには `includedPackages` 付きの `AppIntentsPackage` を重複宣言しない**」という運用でした。2026-04 に Shortcuts のルーティングが壊れた (`LNContextErrorDomain Code=2001`) ときに、重複宣言が原因だと判断したのが根拠です。

ただこれ、あとで Xcode 27 beta 5 で再検証したら **そこまで断定できる根拠が無かった** ことが分かりました。アプリターゲットと Widget / Live Activity / watchOS の全 Extension ターゲットに、公式ドキュメントどおりの形 (`includedPackages` にパッケージ側の `TodoIntentsPackage` を並べた `AppIntentsPackage`) を足してビルドし直しても、統合メタデータ (`extract.actionsdata`) の `actions` / `entities` / `queries` の件数は宣言が無かったときと 1 件も違いません。重複は起きていませんでした。

そもそもセッション 244 (23:29〜24:00) やセッション 275 (25:50)、それに `AppIntentsPackage` の公式ドキュメントを読むと、**この「利用側にも `includedPackages` 付きで宣言する」形のほうが標準手順** として紹介されています。当時のコミットを読み返してみても、Intent routing の修正・`@Dependency` パターンへの統一・重複 Intent の削除をまとめてやった大きな PR の中の出来事で、重複宣言だけを切り出して再現させた記録は残っていませんでした。当時のデバッグログで疑っていたのも「Widget Extension が `TodoAppIntents` を import しているせいで Shortcuts が Widget Extension を intent の提供元として選んでしまった」の方で、これは 2/N で書いた実行プロセス選択の話であって、宣言の書き方とは別軸です。

とはいえ確認できたのはビルドとメタデータのレベルまでで、Siri / Shortcuts の実機ルーティングまでは追えていません。なので運用としては重複宣言しないまま (壊れないと分かっている側) にしておいて、複数ターゲットで型を共有する必要が本当に出てきたら実機で Siri から呼んでみてから採用する、という位置づけにしています。「壊れた記憶」をそのまま制約として書き残すと、何と何を切り分けたのかが後から辿れなくなるんだな、というのが反省点でした。

一方で、上の `AppShortcutsProvider` の制約の方は **この話とは独立していて、そのまま生きています**。アプリと Extension に `AppIntentsPackage` を足した状態でも、`AppShortcutsProvider` がパッケージ内にある限り `autoShortcuts` は 0 のままで、アプリターゲットへ移した瞬間だけ 0 → 8 になりました。2 つが絡んでいる可能性も疑っていたんですが、別々の話でした。

ついでに年代の整理も 1 つ。「Intent や Entity を Swift Package に置ける」ようになった時期を、自分はなんとなく WWDC 2024 (セッション 10134) 頃だと思っていたんですが、10134 が言っているのはむしろ逆で "Only frameworks are supported at this time. Libraries outside of a framework are not." でした。あの時点で対応していたのは Framework 形態だけで、SPM パッケージや static library に広がったのは 2025 のセッション 244 / 275 です。この記事で書いている「Intent をパッケージに置く」構成は、そんなに昔から成立していたわけではなかったんだなというのは、ちょっと意外でした。

## まとめ

- Extension target は薄いスキャフォルドに留めて、View / 状態管理 / データ取得は SPM パッケージに移送する
- macOS native 対応は `#if` で Delegate 分岐 + 共通実体クラスへ委譲
- pbxproj の `platformFilter = ios;` を見落とすと macOS ビルドで Embed エラーが出る
- ターゲット依存をなるべく minimum に保つため、`TodoService.swiftDataBacked(container:)` のような薄いファクトリを TodoAppIntents 側に置く
- `AppShortcutsProvider` をアプリ本体に置く制約は健在。一方「アプリ側に `includedPackages` 付きの `AppIntentsPackage` を書いてはいけない」の方は、再検証で断定を取り下げた (実機ルーティングは未確認なので運用は据え置き)

次回は [SwiftData + CloudKit 同期で踏んだスキーマ要件と落とし穴の話 (4/N)](https://zenn.dev/touyou/articles/intenttodo_04_swiftdata_cloudkit) を書きます。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-11**: 「`AppIntentsPackage` をどこに宣言するか」の節を追加。重複宣言の禁止という断定を取り下げ、`AppShortcutsProvider` の制約とは独立であることを確認。SwiftData Group Lab の出典 (セッション 8017) が一次資料で確認できなかったため、伝聞である旨に書き換え
- **2026-07-08**: `AppShortcutsProvider` を SPM パッケージに置くと `autoShortcuts` が集約されない、という節を追加
- **2026-06-24**: 別プロセス前提とマイグレーションの責務をアプリ本体に寄せる、という節を追加

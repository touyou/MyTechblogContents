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
        let container = try SharedModelContainer.createContainer()   // 失敗時の扱いは下記
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

### コンテナ生成が失敗したときの扱いは、プロセスごとに違う

ここで各プロセスが `SharedModelContainer.createContainer()` を呼ぶわけですが、**`try!` は使わないようにしました**。`try!` はトラップするだけでメッセージを残さないので、Extension のクラッシュが「ウィジェットが白いまま」「Watch アプリを開いてすぐ落ちる」という見え方しかせず、理由が Console に出ないと切り分けようがありません。最低限 `Logger.critical` に error と `NSError` の domain / code / userInfo を吐いてから落とす、という形に揃えています (4/N に書いたログの話と同じです)。

そのうえで、落とすか落とさないかは **「そのプロセスで表示できるものが残っているか」** で決めました。

| 呼出元 | 扱い | 理由 |
|-------|-----|------|
| アプリ本体 / Watch App の `init()` | ログ + `fatalError` | ストアが無ければ何も表示できない |
| Widget Extension の共有コンテナ | ログ + `fatalError` | Extension 内の全ウィジェット / コントロールが対象で、代替表示が無い |
| コンプリケーションの Provider | ログ + **`nil` を保持して `.unavailable()` の entry** | **ここだけ `fatalError` は不適切**。落とすとコンプリケーションが空白になり、それは「予定なし」と区別が付かない |

コンプリケーションだけ扱いが違うのは、5/N で書く「fetch 失敗を 0 や空に潰さない」というのと同じ判断です。空白は「何も無い」に見えてしまうので、「不明」を出す口 (`loadFailed`) が既にあるならそちらに載せて、短い policy で再試行させた方がいい、ということでした。コンテナ生成の失敗も fetch の失敗も、ユーザーから見れば「情報が出てこない」という同じ現象なんだから、扱いも揃うべきだよなと思います。

## 別プロセス前提 — マイグレーションはアプリ本体に寄せる

ここまで書いたように Extension target は薄いスキャフォルドに留めますが、Widget / Live Activity は **アプリ本体とは別プロセス** で動く、という前提は変わりません。WWDC 2026 の SwiftData Group Lab で、この「別プロセスで同じ App Group のストアを共有する」構成のマイグレーション指針が示された、という話を見かけました。要は **マイグレーションを担当するプロセスをアプリ本体 1 つに固定する** べき、というものです。

アプリ更新直後は本体より先に Widget が起動し得るので、Extension 側にマイグレーションプランを持たせると本体の移行と競合し得る、というのが理屈です。Extension 構成の観点だと「View もデータ取得ロジックも SPM に寄せ、**マイグレーションの責務もアプリ本体に寄せる**」と覚えておくと収まりが良いです。SwiftData / CloudKit 側の具体的な書き方は [4/N](https://zenn.dev/touyou/articles/intenttodo_04_swiftdata_cloudkit) に書きました。

ただこれ、**一次資料で裏を取れていない伝聞** です。当初はセッション 8017 として書いていたんですが、あとで手元に貯めたアーカイブを漁り直したら書き起こしが見つかりませんでした (出てくるのは別テーマの 8011 だけです)。Group Lab はライブ Q&A なので公式の書き起こしが出ないことも多いみたいです。指針そのものは SwiftData を複数プロセスで共有するときの一般則として妥当だと思うので運用は変えていませんが、「Apple がこう言った」ではなく「そう聞いた」くらいの確度で読んでもらえればと思います。

## もう1つの例外: AppShortcutsProvider もアプリ本体に置く

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

### フレーズにパラメータを入れるなら、候補は絞る

置き場所とは別に、フレーズの書き方でも 1 つ気を付けることがありました。フレーズには `"Complete \(\.$todo) in \(.applicationName)"` のように Intent のパラメータを埋め込めます (更新の通知が要る話は 2/N に書きました) が、セッション 244 (9:46) が **"If provided, an App Shortcut for each value of that type will be created."** と言っていて、つまり **`suggestedEntities()` が返した件数だけ App Shortcut が生える** ということになります。

なので全件返す実装のままフレーズだけパラメータ化すると、Shortcuts や Spotlight が自動生成された shortcut で埋まります。IntentTodo は `suggestedEntities()` を「直近の未完了 10 件」に絞りました (HIG の "not more than ten" に合わせています)。全件が要る用途は `EnumerableEntityQuery` の `allEntities()` が別に担当しているので、この 2 つは役割が違う、と考えるのが正しかったです。パラメータ無しのフレーズも各 shortcut に 1 つずつ残しています (指定なしで呼ばれたときに Siri が聞き返せるように、というのがセッション 10102 の 8:14 の指示です)。

この不具合は **ビルドやコード補完のどのタイミングでも露見しません**。ビルドは通り、Intent 自体は Siri への直接指示や Widget からは機能し、警告も出ないので気付きにくいです。App Shortcut のフレーズだけが黙って欠落しているので、Shortcuts アプリを開いて目視確認するか、統合メタデータの `autoShortcuts` 件数を直接見ないと気付けませんでした。

## AppIntentsPackage をどこに宣言するか

`AppShortcutsProvider` の隣にある話として、`AppIntentsPackage` の置き場所にも触れておきます。IntentTodo は長らく「パッケージ側に 1 つだけ宣言して、**メインアプリターゲットには `includedPackages` 付きの `AppIntentsPackage` を重複宣言しない**」という運用でした。2026-04 に Shortcuts のルーティングが壊れた (`LNContextErrorDomain Code=2001`) ときに、重複宣言が原因だと判断したのが根拠です。

ただこれ、あとで Xcode 27 beta 5 で再検証したら **そこまで断定できる根拠が無かった** ことが分かりました。アプリターゲットと Widget / Live Activity / watchOS の全 Extension ターゲットに、公式ドキュメントどおりの形 (`includedPackages` にパッケージ側の `TodoIntentsPackage` を並べた `AppIntentsPackage`) を足してビルドし直しても、統合メタデータ (`extract.actionsdata`) の `actions` / `entities` / `queries` の件数は宣言が無かったときと 1 件も違いません。重複は起きていませんでした。

そもそもセッション 244 (23:29〜24:00) やセッション 275 (25:50)、それに `AppIntentsPackage` の公式ドキュメントを読むと、**この「利用側にも `includedPackages` 付きで宣言する」形のほうが標準手順** として紹介されています。当時のコミットを読み返してみても、Intent routing の修正・`@Dependency` パターンへの統一・重複 Intent の削除をまとめてやった大きな PR の中の出来事で、重複宣言だけを切り出して再現させた記録は残っていませんでした。当時のデバッグログで疑っていたのも「Widget Extension が `TodoAppIntents` を import しているせいで Shortcuts が Widget Extension を intent の提供元として選んでしまった」の方で、これは 2/N で書いた実行プロセス選択の話であって、宣言の書き方とは別軸です。

「壊れた記憶」をそのまま制約として書き残すと、何と何を切り分けたのかが後から辿れなくなるんだな、というのが反省点でした。

### 公式手順どおりに宣言する形へ切り替えた

しばらく「重複宣言しない」まま様子を見ていたんですが、追い込みきったので **公式手順の側へ切り替えました**。アプリ / Widget / Live Activity / watchOS App の 4 ターゲットそれぞれに `includedPackages` 付きの `AppIntentsPackage` を宣言しています。2026-04 に外して以来の方針転換です。

判断できるところまで持っていけたのは、10/N に書いた検証の梯子 (AppIntentsTesting → Shortcuts → Spotlight → Siri) をそのまま当てたからでした。根拠は 3 つあります。

1. **クリーンビルドで metadata の件数が一致**。4 バンドルすべての `Metadata.appintents` の `actions` / `entities` / `enums` / `queries` / `autoShortcuts` が、宣言前の baseline と完全一致しました。しかも `actions` の 23 件は `Intents/` に置いた intent の型数 23 とちょうど一致していて、重複していないことが二重に確かめられます
2. **AppIntentsTesting の全 22 テストがグリーン**。Siri / Shortcuts / Spotlight と同じインフラを通る経路で、intent の実行・entity の id 解決・Spotlight クエリ・view annotation が成立しました
3. **Shortcuts アプリでの実機確認**。アクション一覧とパラメータ表示が壊れていないことを目で見ました

残った未確認は **App Shortcut の「フレーズ」ルーティングだけ** です。AppIntentsTesting は型名で intent を引くのでフレーズ経路を通りません。ここは 10/N に書いたとおり Apple も手動確認を想定している領域なので、実機の Siri で登録フレーズを 1 つ言えば済みますし、壊れていたら 4 つの宣言ファイルを消せば元に戻せます。

「実機でしか確かめられないから保留」で止めていたものが、**梯子の下 3 段を全部登ってみたら判断できる材料が揃っていた**、というのがここでの学びでした。実機検証が要るからと丸ごと寝かせるのではなくて、自動で確かめられるところまで先に登っておくと、残りの手動確認の範囲がぐっと小さくなります。

一方で、上の `AppShortcutsProvider` の制約の方は **この話とは独立していて、そのまま生きています**。アプリと Extension に `AppIntentsPackage` を足した状態でも、`AppShortcutsProvider` がパッケージ内にある限り `autoShortcuts` は 0 のままで、アプリターゲットへ移した瞬間だけ 0 → 8 になりました。2 つが絡んでいる可能性も疑っていたんですが、別々の話でした。

### 統合メタデータでは「情報が少ない方」が勝つ

`autoShortcuts` が集約されない話には続きがあって、**統合メタデータでもっと分かりにくい壊れ方** をもう 1 つ踏みました。7/N で書く `@AppEntity(schema: .reminders.list)` の適合が、**iOS アプリの出荷メタデータからだけ消えていた** というやつです。

発端は「`CategoryAppEntity` のプロパティが 0 件で、スキーマも空になっている」という観測でした。最初は「`@Property` を書き忘れたか、マクロが面倒を見てくれる前提が間違っていたか」を疑ったんですが、全バンドルを並べたらどちらでもありませんでした。

```
Debug-iphonesimulator/TodoAppIntents.appintents   プロパティ2件 schema=['ListEntity']
Debug-iphonesimulator/IntentTodoWidgetExtension   プロパティ2件 schema=['ListEntity']
Debug-iphonesimulator/IntentTodo.app              プロパティ0件 schema=[]        ← ここだけ
Debug-xrsimulator/IntentTodo.app                  プロパティ2件 schema=['ListEntity']
Debug/IntentTodo.app                              プロパティ2件 schema=['ListEntity']
```

マクロはちゃんと仕事をしていて、パッケージ側の `.appintents` には `@Property` もスキーマ登録も出ています。落ちているのは **iOS アプリバンドルの統合メタデータだけ** で、macOS と visionOS のアプリバンドルは無事でした。自分が最初に見ていたのが iOS のバンドル 1 つだけだったので、「マクロが動いていない」ように見えていたわけです。

iOS だけに効く違いとして残るのは「iOS アプリは watchOS アプリを `IntentTodo.app/Watch/` に埋め込む」ことでした。7/N に書くとおり watchOS では reminders スキーマが使えないので、`#if os(watchOS)` で素の `AppEntity` にフォールバックしています。**同じ型名にスキーマ付きの形とスキーマ無しの形が両方あると、統合の結果はスキーマ無しの側になる** ということでした。決め手はたまたま中途半端に stale だったビルド成果物で、片方だけ再生成された状態のときに 2 props と 0 props が混ざって、結果が 0 props になるのが見えました。「情報が少ない方が勝つ」というマージ規則です。

対処は **フォールバック側の型名を分ける** ことでした。`WatchCategoryAppEntity` / `WatchTodoListType` に改名して、呼出側には `public typealias CategoryAppEntity = WatchCategoryAppEntity` で同じ名前を見せています。mangled type name が別物になるので衝突せず、2 つのエントリが共存してスキーマが残ります。代償は iOS 側のメタデータに `WatchCategoryAppEntity` が 1 件増えることですが、スキーマ適合が出荷メタデータに届かない方がよっぽど重いので、そちらを取りました。

ついでに、フォールバック側にも `@Property(title:)` を明示しています。スキーマ版はマクロが `name` / `type` の `@Property` を生成してくれますが、素の `AppEntity` は自分で書かないと **プロパティ 0 件の entity** になります (渡せるけど何も読めない)。

この 2 つ、`autoShortcuts` の件と同じで **コンパイラにもビルド緑にも一切現れません**。パッケージ単体の `.appintents` は正常なので、アプリバンドルの統合メタデータを直接見るまで分からないやつでした。なので今は「linked package にはあるのにアプリバンドルに無いスキーマ」を検出するスクリプトを回しています。ハマったのが nested バンドルで、`IntentTodo.app/Watch/IntentTodoWatchApp.app` は iOS の products ディレクトリに居るのに中身は watchOS ビルドなので、隣の iOS パッケージと比べると誤検出します。ここは比較対象から外しました。

教訓としては、**統合メタデータは「1 つのバンドルを見て正常だった」を根拠にしてはいけない** ということかなと思っています。自分は 2 回とも「アプリ側 1 つ」か「パッケージ側 1 つ」しか見ていなくて、並べた瞬間に答えが出ました。

ついでに年代の整理も 1 つ。「Intent や Entity を Swift Package に置ける」ようになった時期を、自分はなんとなく WWDC 2024 (セッション 10134) 頃だと思っていたんですが、10134 が言っているのはむしろ逆で "Only frameworks are supported at this time. Libraries outside of a framework are not." でした。あの時点で対応していたのは Framework 形態だけで、SPM パッケージや static library に広がったのは 2025 のセッション 244 / 275 です。この記事で書いている「Intent をパッケージに置く」構成は、そんなに昔から成立していたわけではなかったんだなというのは、ちょっと意外でした。

## パッケージに View を置くと、UI コピーのローカライズで 2 回転ぶ

View を SPM パッケージに移したことで踏んだ罠も書いておきます。ローカライズの話なんですが、**どちらも英語しか無いうちは何も起きません**。翻訳に着手した時点で初めて「一部の文言だけ英語のまま残る」という形で出てきます。

**1 つ目は、パッケージ自身に String Catalog が無いと文言がどこにも抽出されないこと**でした。`xcodebuild -exportLocalizations` で確認できます。`UI` パッケージに catalog を置く前は、`Text("Todos")` のような直書きのリテラルが xcloc に **1 件も** 出てきません (アプリターゲット側の catalog にも入りません)。抽出はターゲット単位で、受け皿の catalog を持つターゲットの分しか出てこない、ということでした。

```swift
// Package.swift
let package = Package(
    name: "UI",
    defaultLocalization: "en",   // これが無いと catalog がローカライズ資源として扱われない
    ...
    targets: [
        .target(name: "UI", resources: [.process("Resources")])
    ]
)
```

ややこしいのが、`AppIntents` の `LocalizedStringResource` (Intent の title など) **だけは例外** で、catalog が無くてもアプリの統合メタデータ経由でアプリ側の catalog に出てくることです。これがあるせいで「パッケージの文言も抽出されている」と誤読しました。実際、自分は Intent のタイトルが xcloc に並んでいるのを見て、抽出は効いていると思い込んでいます。

**2 つ目は、`Text("...")` が実行時に `Bundle.main` を引くこと**でした。`LocalizedStringKey` の既定の bundle はメインバンドルなので、パッケージ同梱の catalog (`Bundle.module`) には当たりません。つまり 1 つ目を直して catalog に翻訳を入れても、引かれないままです。各パッケージにこういう口を 1 つ置いて、UI コピーは必ずここを通すようにしました。

```swift
extension LocalizedStringResource {
    static func copy(_ key: String.LocalizationValue) -> LocalizedStringResource {
        LocalizedStringResource(key, bundle: .atURL(Bundle.module.bundleURL))
    }
}

Text(.copy("Cancel"))
Label(.copy("Completed"), systemImage: "checkmark.circle.fill")
Section(.copy("Due Date")) { ... }
```

SwiftUI 側は `Text` / `Label` / `Button` / `Toggle` / `Section` / `Picker` / `TextField` / `navigationTitle` / `searchable(prompt:)` あたりに `LocalizedStringResource` のオーバーロードが揃っているので、ViewBuilder 版に書き換える必要はありませんでした。この宣言は internal にしています (`UI` は `LiveActivity` を import するので、両方が `public static func copy` を持つと同名メンバで曖昧になります)。

細かい例外も 2 つあって、`\(date, style: .relative)` や `\(timerInterval:)` は `LocalizedStringKey` 専用の補間なので `.copy` では組めません。ここだけ `Text("...", bundle: .module)` と bundle を明示します。あと数値だけを見せる `Text("\(count)")` を `.copy` に通すと、キーが `"%lld"` という翻訳不能なエントリになるので `Text(count, format: .number)` に置き換えました。

もう 1 つ、**UI コピーを `String` 型で運ばない** というのも同じ話でした。`Text` / `Label` は `String` を渡すと verbatim 初期化子が選ばれます。コンパイルは通って表示も変わらないのに、リテラルは catalog に載りません。

```swift
// ❌ 呼出側のリテラルが抽出されない
StatusBadge(title: "Completed", ...)   // private let title: String

// ✅
StatusBadge(title: .copy("Completed"), ...)   // private let title: LocalizedStringResource
```

読み上げ用のラベルを `label += ", completed"` みたいに連結するのも同じ理由で不可です (区切りと語順がロケール依存なので)。要素ごとに `String(localized:)` してから `parts.formatted(.list(type:width:))` で並べる形にしました。

回帰は SwiftLint のカスタムルールで見張っています。`Text("...")` の直書きを検出するだけの雑なルールですが、**この壊れ方はビルドでもテストでも検出できない** ので、静的に引っかけるしかありませんでした。確認は結局 export の件数比較で、`UI` パッケージが 71 → 97 件になって、増えたのがまさに漏れていた文言 (`Completed` / `No Results` / `Newest First` など) でした。

## まとめ

- Extension target は薄いスキャフォルドに留めて、View / 状態管理 / データ取得は SPM パッケージに移送する
- macOS native 対応は `#if` で Delegate 分岐 + 共通実体クラスへ委譲
- pbxproj の `platformFilter = ios;` を見落とすと macOS ビルドで Embed エラーが出る
- ターゲット依存をなるべく minimum に保つため、`TodoService.swiftDataBacked(container:)` のような薄いファクトリを TodoAppIntents 側に置く
- `AppShortcutsProvider` をアプリ本体に置く制約は健在。一方「アプリ側に `includedPackages` 付きの `AppIntentsPackage` を書いてはいけない」の方は誤りで、**公式手順どおり各ターゲットで宣言する形に切り替えた**
- 統合メタデータは **同じ型名に 2 つの形があると情報が少ない方が勝つ**。iOS アプリは watch アプリを埋め込むので、watchOS 用フォールバックの型名は分けておく
- コンテナ生成の失敗は `try!` にしない。落とすかどうかは「そのプロセスで表示できるものが残っているか」で決める
- パッケージに View を置いたら、`defaultLocalization` + String Catalog + `Bundle.module` を通す口 (`LocalizedStringResource.copy(_:)`) をセットで用意する

次回は [SwiftData + CloudKit 同期で踏んだスキーマ要件と落とし穴の話 (4/N)](https://zenn.dev/touyou/articles/intenttodo_04_swiftdata_cloudkit) を書きます。

## 更新履歴

本文は常に最新の理解に直しています。何をいつ直したかはここに残しておきます。

- **2026-08-28**: 統合メタデータで watchOS フォールバックがスキーマを消していた話 (型名を分けて解消) を追加。コンテナ生成失敗の扱い (`try!` を使わない / コンプリケーションだけ落とさない) と、SPM パッケージの UI コピーと String Catalog の節を追加。App Shortcut のフレーズをパラメータ化するときの候補件数の注意を追加
- **2026-08-12**: 日付つきの追記見出しを本文から外し、記述は常に現在形へ統一 (いつ何を直したかはこの更新履歴に一本化)
- **2026-08-12**: `includedPackages` 付き `AppIntentsPackage` を 4 ターゲットで宣言する公式手順へ切り替え。metadata 件数の一致 / AppIntentsTesting 22 テスト / Shortcuts 実機確認の 3 つを根拠にした
- **2026-08-11**: 「`AppIntentsPackage` をどこに宣言するか」の節を追加。重複宣言の禁止という断定を取り下げ、`AppShortcutsProvider` の制約とは独立であることを確認。SwiftData Group Lab の出典 (セッション 8017) が一次資料で確認できなかったため、伝聞である旨に書き換え
- **2026-07-08**: `AppShortcutsProvider` を SPM パッケージに置くと `autoShortcuts` が集約されない、という節を追加
- **2026-06-24**: 別プロセス前提とマイグレーションの責務をアプリ本体に寄せる、という節を追加

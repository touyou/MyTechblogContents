---
title: "WWDC 2026: Todo を「システムが理解できる名詞」にする — ネイティブ型とプロパティマクロ (6/N)"
emoji: "🧩"
type: "tech"
topics: ["AppIntents", "SwiftData", "iOS", "WWDC2026"]
published: true
---

:::message
このシリーズは随時更新中です。IntentTodo の実装と検証が進むたびに、内容を追記・修正していこうと思っています。
:::

[App Intents 中心設計シリーズ](https://zenn.dev/touyou/articles/intenttodo_01_design_philosophy) の 6 回目です。

ここから数本は、WWDC 2026 で増えた App Intents まわりの新要素を IntentTodo で実際に試してみて分かったことを書いていきます。
作業は `xcode27` という別ブランチ (ベータ SDK 検証用、`main` には未マージ) でやっているので、本編 1〜5 とは少し毛色が変わります。

最初に断っておくと、この WWDC 2026 編は本編より **検証の深さが浅い** です。
本編は「実機で詰まった話」に絞っていましたが、新 API は実機 (Siri / Visual Intelligence) まで通すのに端末や手動確認が必要なものが多くて、自分の手元だとビルド成立 (型レベル) と SPM / テストでの単体実行までしか到達できていないものが結構あります。
なので、この編は「実機でこう動いた」ではなく **「やってみて、この API は採用していいのか / どう設計に効くのか」という設計判断** を軸に書きます。各記事の末尾に、どこまで検証できたかを正直に書いておきます。

1 本目は Phase 1 としてやった、**Todo というモデルを「システムが理解できる名詞」に育てる** 話です。

## なぜ Todo を「ただの文字列の集合」にしないか

シリーズ 1/N で「Entity (名詞) と Intent (動詞) が設計の原子単位」と書きました。
ただ、本編を書いた時点での `TodoAppEntity` は、正直なところ `title` / `isCompleted` / `dueDate` くらいしか持っていない、わりと痩せた Entity でした。

WWDC 2026 のセッションを見ていて思ったのは、App Schema や Visual Intelligence、cross-app 連携みたいな「外向き」の機能を意味のあるものにするには、Todo がもっと **システム共通の型で語れる名詞** になっていないといけない、ということでした。
「担当者」を `String` で持っているうちは Siri から見れば単なる文字列ですが、`PersonNameComponents` で持てば「人」として解決できる。「所要時間」を秒数の `Double` で持つか `Duration` で持つかで、Shortcuts が出すピッカーも変わってきます。

そこで Phase 1 では、後続の WWDC 2026 要素を載せる土台として、Todo に「場所 / 担当者 / 所要時間」を足しつつ、それらを **システムのネイティブ型として公開する** ところから始めました。

## @Property でモデルの属性をシステムに公開する

まず地味ですが効くのが `@Property` です。
`AppEntity` のプロパティに `@Property(title:)` を付けると、その属性が Shortcuts のアクション出力や Siri の参照対象としてシステムに見えるようになります。

```swift
public struct TodoAppEntity: AppEntity, Hashable, SyncableEntity {
    public var id: String

    @Property(title: "Title")
    public var title: String

    @Property(title: "Completed")
    public var isCompleted: Bool

    @Property(title: "Due Date")
    public var dueDate: Date?

    /// Todo が属するカテゴリ。関連 Entity として公開しておくと、
    /// Siri / Shortcuts からカテゴリで絞り込んだり辿ったりできる。
    @Property(title: "Category")
    public var category: CategoryAppEntity?
    // ...
}
```

ポイントは、`category` のように **別の `AppEntity` を `@Property` で持てる** ことです。
これで「あるカテゴリに属する Todo」みたいな辿り方が Shortcuts 側で組めるようになります。名詞と名詞を関連でつなぐ、というのを App Intents の語彙でやっている感じです。

## ネイティブ型で受ける: Duration / PersonNameComponents / PlaceDescriptor

ここが Phase 1 でいちばん設計判断が要ったところでした。

WWDC 2026 で、`@Parameter` や `@Property` に `Duration` / `PersonNameComponents` / `PlaceDescriptor` (GeoToolbox) といった **システム共通のネイティブ型** をそのまま使えるようになりました。
これらを使うと、Siri / Shortcuts が型に応じた入力 UI (期間ピッカー、連絡先からの人名解決、場所の解決) を出してくれます。

ただ、ここで CloudKit と正面衝突します。
本編 4/N で書いたとおり、SwiftData + CloudKit 互換にするには **全属性が optional か default value 付きの primitive** でないといけません。`Duration` や `PlaceDescriptor` をそのまま `@Model` に持たせるのは無理があります。

そこで採った設計が、**保存層は CloudKit 互換の primitive、App Intents の境界でネイティブ型に変換する** という二重表現です。

モデル (`TodoItem`) 側は、あくまで primitive で持ちます。

```swift
@Model
public final class TodoItem {
    /// 所要時間は TimeInterval (秒) で保存。境界で Duration に橋渡し。
    public var estimatedDuration: TimeInterval?

    /// 担当者は整形済みの String で保存 (CloudKit-safe)。
    /// 入力は PersonNameComponents で受けて、ここで文字列に整形する。
    public var assigneeName: String?

    /// 場所は name + 緯度経度の primitive に分解して保存。
    public var locationName: String?
    public var locationLatitude: Double?
    public var locationLongitude: Double?
    // ...
}
```

Entity (`TodoAppEntity`) 側は、ネイティブ型で公開します。

```swift
/// 所要時間。App Intents ネイティブの Duration で公開する。
@Property(title: "Estimated Duration")
public var estimatedDuration: Duration?

/// 担当者名。
@Property(title: "Assignee")
public var assigneeName: String?

/// 関連する場所。GeoToolbox の PlaceDescriptor で公開する。
@Property(title: "Location")
public var location: PlaceDescriptor?
```

そして、入力を受ける `AddTodoIntent` の `@Parameter` はネイティブ型で受けて、`perform()` の中で primitive に落とします。

```swift
@Parameter(title: "Estimated Duration")
public var estimatedDuration: Duration?

@Parameter(title: "Assignee")
public var assignee: PersonNameComponents?

@Parameter(title: "Location")
public var location: PlaceDescriptor?

@MainActor
public func perform() async throws -> some IntentResult & ... {
    let entity = try todoService.create(
        title: title,
        // Duration → TimeInterval
        estimatedDuration: estimatedDuration.map { Double($0.components.seconds) },
        // PersonNameComponents → String
        assigneeName: assignee.map { PersonNameComponentsFormatter().string(from: $0) },
        // PlaceDescriptor → name + 緯度経度
        locationName: location.flatMap { TodoPlace.decompose($0).name },
        locationLatitude: location.flatMap { TodoPlace.decompose($0).latitude },
        locationLongitude: location.flatMap { TodoPlace.decompose($0).longitude }
    )
    // ...
}
```

場所の変換は、`PlaceDescriptor` まわりが少しややこしいので `TodoPlace` という enum に橋渡しを切り出しました。

```swift
enum TodoPlace {
    static func descriptor(name: String?, latitude: Double?, longitude: Double?) -> PlaceDescriptor? {
        if let latitude, let longitude {
            return PlaceDescriptor(
                representations: [.coordinate(CLLocationCoordinate2D(latitude: latitude, longitude: longitude))],
                commonName: name
            )
        }
        if let name {
            return PlaceDescriptor(representations: [.address(name)], commonName: name)
        }
        return nil
    }

    static func decompose(_ place: PlaceDescriptor) -> (name: String?, latitude: Double?, longitude: Double?) {
        (place.commonName, place.coordinate?.latitude, place.coordinate?.longitude)
    }
}
```

「入力と公開はシステム型、保存は primitive、境界で変換」というのは、書く前は二度手間っぽくて気が進まなかったんですが、やってみると役割がきれいに分かれて結構気持ちよかったです。
Siri に見せる顔 (リッチな型) と、CloudKit に保存する都合 (枯れた primitive) は、そもそも要求が別物なので、無理に 1 つの表現に寄せない方が素直だなと思いました。

## @ComputedProperty と @DeferredProperty

WWDC 2026 のプロパティマクロで、もう 1 つ試したのが `@ComputedProperty` と `@DeferredProperty` です。
どちらも「スナップショットに持っていない値を、導出 / 取得してシステムに公開する」ためのものですが、性格が違います。

`@ComputedProperty` は同期 getter で、スナップショットが持っている値から軽く導出できるもの向け。
IntentTodo では「期限切れかどうか」を `dueDate` と `isCompleted` から計算しています。

```swift
@ComputedProperty(title: "Is Overdue")
public var isOverdue: Bool {
    guard !isCompleted, let dueDate else { return false }
    return dueDate < Date()
}
```

`@DeferredProperty` は非同期 getter (`get async throws`) で、**要求されたときだけ取りに行く** もの向け。
サブタスクの進捗 (「2/5 completed」みたいな文字列) は SwiftData のリレーションを引かないと作れず、軽いスナップショットには載せたくないので、こちらにしました。

```swift
@DeferredProperty(title: "Subtask Progress")
public var subtaskProgress: String {
    get async throws {
        try await Self.loadSubtaskProgress(forID: id)
    }
}
```

`@DeferredProperty` は **Spotlight の index には含まれず、Siri / Shortcuts にも自動送出されない** という契約になっていて、要求時のフェッチを前提にしています。リレーション越しの重い値をうっかり全件 index に載せてしまう事故を防げるので、棲み分けとしては納得感がありました。

ここで 2 つハマりどころがありました。

### ハマりどころ 1: Entity は @Dependency を使えない

`subtaskProgress` の getter の中でサブタスクをフェッチしたいわけですが、`AppEntity` の中では `@Dependency` が使えません。
Apple のドキュメントいわく、dependency injection は「メインアプリから *Intent* へデータを渡すためだけ」のもので、`EntityQuery` では使えても `AppEntity` 本体では `Unknown attribute 'Dependency'` になります。

そこで、共有 `ModelContainer` をアプリ起動時に `TodoEntityStore` という `@MainActor enum` の static に登録しておいて、deferred getter からはそこを参照する形にしました。
Apple のサンプルコードにある ambient な `modelData` アクセサと同じ発想です。

```swift
@MainActor
public enum TodoEntityStore {
    public static var container: ModelContainer?

    public static func register(container: ModelContainer) {
        self.container = container
    }
}
```

```swift
private static func loadSubtaskProgress(forID id: String) async throws -> String {
    try await MainActor.run {
        guard let container = TodoEntityStore.container else {
            return String(localized: "No subtasks")
        }
        let repository = SwiftDataTodoRepository(modelContext: container.mainContext)
        // ... サブタスクを引いて "completed/total completed" を組む ...
    }
}
```

deferred property が走るのはメインアプリプロセス (Siri / Shortcuts / Spotlight の follow-up) だけなので、`App.init()` で 1 回登録しておけば足ります。
プレビューや SPM テストみたいに未登録の場面では、空の結果に degrade させて落ちないようにしています。

### ハマりどころ 2: プロパティマクロで Hashable の自動合成が壊れる

これは実装してはじめて気付いたやつです。
`@ComputedProperty` / `@DeferredProperty` (あるいは後述する App Schema のマクロ) を付けると、マクロが内部に `EntityProperty` という **非 `Hashable` な backing storage** を生やします。
その結果、`Hashable` / `Equatable` の自動合成が効かなくなって、`TodoAppEntity` を `Set` や `NavigationPath` に入れているところでビルドが通らなくなりました。

対処は `==` と `hash(into:)` を明示実装するだけです。
等価判定はスナップショットの値で、hash は安定した `id` だけで取る、という形にしました。

```swift
public static func == (lhs: TodoAppEntity, rhs: TodoAppEntity) -> Bool {
    lhs.id == rhs.id
        && lhs.title == rhs.title
        && lhs.isCompleted == rhs.isCompleted
        // ... 他のスナップショット属性も比較 ...
}

public func hash(into hasher: inout Hasher) {
    hasher.combine(id)
}
```

ちなみに `location` (`PlaceDescriptor`) は `Equatable` が保証されていないので等価比較からは外しています。保存している name / 緯度経度はモデル経由で結局反映されるので、実害は無いと判断しました。

## 関連を Entity 化する: Category / SubTask

痩せた Todo を太らせるついでに、`Category` と `SubTask` も `AppEntity` 化して、それぞれ `EntityQuery` を付けました。
これで Siri / Shortcuts から「カテゴリ」を名詞として扱えるようになり、Todo → Category の関連も辿れます。

`CategoryAppEntity` は後の記事 (7/N) で書く App Schema 適合と絡むので深入りはしませんが、こんな見た目です。

```swift
@AppEntity(schema: .reminders.list)
public struct CategoryAppEntity: Hashable {
    public var id: String
    public var name: String
    public var type: TodoListType
    // ...
}
```

## ついでに足せた SyncableEntity

WWDC 2026 の `SyncableEntity` (セッション 345) も、Phase 1 のついでに適合できました。
これは「デバイスをまたいで同じ Entity を一貫して参照できる」ためのプロトコルですが、`TodoAppEntity` の `id` が SwiftData + CloudKit のレコード id をそのまま文字列化したもので、もともとデバイス間で一致しているので、**プロトコル適合を書き足すだけ** で済みました。

```swift
public struct TodoAppEntity: AppEntity, Hashable, SyncableEntity {
    public var id: String  // CloudKit レコード id と同一。デバイス間で一貫。
    // ... 追加の変更なしで適合 ...
}
```

ローカル id と安定 id が別々のアプリだと `id` を `SyncableEntityIdentifier<Local, Stable>` 型にする必要があるみたいですが、IntentTodo はそもそも別 id を持っていないので、`String` id のまま適合できました。
「すでに正しく設計されていると、新 API への適合がタダで済む」のは結構気持ちのいい瞬間で、CloudKit の id 設計をサボらずにやっておいてよかったなと思いました。

## 検証できた深さ

正直に書いておくと、この回の内容は以下の深さです。

- **ビルド成立 (型レベル)**: 全部 OK。`Duration` / `PersonNameComponents` / `PlaceDescriptor` / 各プロパティマクロ / `SyncableEntity` はコンパイルが通り、API 採用としては妥当だと判断しています。
- **単体 (SPM / テスト)**: Entity 変換まわりは確認済み。
- **実機 (Siri が実際にネイティブ型ピッカーを出すか、deferred property がいつ呼ばれるか)**: 未確認です。ここは端末での手動確認が要るので、できたら追記します。

なので本記事は「これらの API を採用して設計に組み込むと、こういう構造になる」という設計判断の記録として読んでもらえればと思います。

## まとめ

- WWDC 2026 編は `xcode27` ブランチでの検証で、本編より浅い (主に型レベル + 単体)。実機可否より「採用していいか / 設計にどう効くか」を書く
- `@Property` でモデル属性をシステムに公開し、関連 (`category`) も Entity として持てる
- `Duration` / `PersonNameComponents` / `PlaceDescriptor` はネイティブ型で入力・公開し、保存は CloudKit 互換 primitive に落とす「二重表現」にする。境界で変換する
- `@ComputedProperty` (同期・軽い導出) と `@DeferredProperty` (非同期・要求時フェッチ、Spotlight 非 index) を使い分ける
- Entity は `@Dependency` を使えないので、共有コンテナは `TodoEntityStore` に置いて参照する
- プロパティマクロは `Hashable` 自動合成を壊すので `==` / `hash(into:)` を明示実装する
- `SyncableEntity` は CloudKit id をそのまま使っていれば適合を書き足すだけで済む

次回は、[ここで Entity 化した `Category` を `@AppEntity(schema: .reminders.list)` に適合させた話と、Todo 本体を reminder スキーマに適合させようとして保留した話 (7/N)](https://zenn.dev/touyou/articles/intenttodo_07_app_schema_system_intents) を書きます。

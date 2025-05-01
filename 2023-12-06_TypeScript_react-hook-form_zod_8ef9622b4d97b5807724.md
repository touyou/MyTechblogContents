<!--
title:   zod + react-hook-form + TypeScriptでつくるフォームのナレッジ3選
tags:    TypeScript,react-hook-form,zod
id:      8ef9622b4d97b5807724
private: false
-->
この記事はGoodpatch Advent Calendar 2023、9日目の記事です。
こんにちは！Goodpatchでエンジニアをしているとうようです。

今回は直近のWebフロントエンドの技術剪定だと選ばれがちな[zod](https://zod.dev/)と[react-hook-form](https://react-hook-form.com/)で複雑なフォームを実装しようとなった時に役立つナレッジ３つをご紹介しようと思います。

軽すぎずかつ重すぎない、絶妙なボリュームのナレッジなので逆引きに使うでも一気に読み切るでも、自分にあったスタイルで読んでいただければ幸いです。

## ナレッジ①：zodで条件分岐フォームを作る

一つ目はzodを使って条件分岐するようなフォームのスキーマを作る方法です。例えば以下のようなフォームを考えます。

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/10943/e5d7d3a2-dcc5-93f5-da39-735a7b372ac6.png)

実際このような仕組みにできるかは一旦おいておき、たとえばマイナンバーカードの有無によって個人情報の入力を省略できるかどうかが変わるフォームがあるとします。

このようなフォームがある場合、まず基本系としてzodの[discriminatedUnion](https://zod.dev/?id=discriminated-unions)を使って次のように書けます。

```ts
const yesSchema = z.object({
  hasMyNumber: z.literal(true),
  myNumber: z.string(),
});

const noSchema = z.object({
  hasMyNumber: z.literal(false),
  name: z.string(),
  birthdate: z.string()
});

const schema = z.discriminatedUnion('hasMyNumber', [yesSchema, noSchema]);
```

これはその名の通りユニオン型のschemaを作るものなのですが、単純な[union](https://zod.dev/?id=unions)と異なり区別するためのkeyを指定することで値によってのスキーマの切り替えを高速に行ってくれます。

実際のフォームを考えた時にはもう少し工夫があるといいと思います。たとえばさっきのフォームが実は次のようなフォームの一部だったとしたらどうでしょうか？

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/10943/77ae0263-598b-cafb-1e22-1982107fdf68.png)

暗黙の前提にしていましたが、全部必須入力だとしてください。
さてこの時両方のスキーマに同じ項目が増えてしまいます。これをいちいち両方書くのは面倒ですよね。今回はメールアドレスなどですが、より複雑な判定が必要なバリデーションが出てくると毎回書くのはさすがに億劫です。

そこで今度登場するのが[merge](https://zod.dev/?id=merge)です。これは文字通り二つのschemaを結合するものなので、画像のフォームのスキーマは結果的に以下のように書けます（※全てstringの判定しかしない簡易版です。）

```ts
const commonSchema = z.object({
  email: z.string(),
  username: z.string()
});

const yesSchema = z.object({
  hasMyNumber: z.literal(true),
  myNumber: z.string(),
});

const noSchema = z.object({
  hasMyNumber: z.literal(false),
  name: z.string(),
  birthdate: z.string()
});

const mergedYesSchema = commonSchema.merge(yesSchema);
const mergedNoSchema = commonSchema.merge(noSchema);

const schema = z.discriminatedUnion('hasMyNumber', [mergedYesSchema, mergedNoSchema]);
```

これによってメールアドレスとユーザー名は必須入力で、選択肢に応じて氏名・誕生日かマイナンバーの入力のどちらかが必須になるバリデーションを作ることができました。

## ナレッジ②：react-hook-formで巨大フォームをコンポーネント分割する

react-hook-formを使っているとどうしてもフォームをコンポーネント分割しにくいという問題があります。
プロパティで伝搬する形を取ると特にTypeScriptでは内部の型を一個一個つけていかなくてはならず、あまりいい方法とはいえません。

そこで使えるのが[useFormContext](https://react-hook-form.com/docs/useformcontext)です。これは公式のドキュメントにも[Advanced Usage](https://react-hook-form.com/advanced-usage#ConnectForm)として紹介されている機能になります。

この機能はその名に「Context」とついていることからも推察できますが、React Contextを用いた専用の機構を使って高速に子要素でコンポーネントから取り出すことができます。
公式ドキュメントに載っている使い方はこんな感じ。

```jsx
import { FormProvider, useForm, useFormContext } from "react-hook-form"


export const ConnectForm = ({ children }) => {
  const methods = useFormContext()


  return children({ ...methods })
}


export const DeepNest = () => (
  <ConnectForm>
    {({ register }) => <input {...register("deepNestedInput")} />}
  </ConnectForm>
)


export const App = () => {
  const methods = useForm()


  return (
    <FormProvider {...methods}>
      <form>
        <DeepNest />
      </form>
    </FormProvider>
  )
}
```

これはjsxでの使い方ですが、TypeScriptとzodを組み合わせると注意しなければいけないことがあったのでそちらを紹介します。
基本的にコンポーネントごとにこの機能を活用するためにはなるべく関心を分離したいので以下のように作ります。

1. コンポーネントごとにフォルダを切る
2. そこにそのコンポーネントで使うzodスキーマを定義する
3. それを親側のzodスキーマでimportし、全体のスキーマを構築する

この時useFormContextに渡すジェネリクスの型はビルドだけだと以下のどちらで書いても通ります。

```ts
// 子供のコンポーネントのzodスキーマの型
type ChildSchemaType = z.infer<childSchema>;
// 親のコンポーネントのzodスキーマの型
type SchemaType = z.infer<schema>;

const methodsBasedChildSchema = useFormContext<ChildSchemaType>();
const methodsBasedAllSchema = useFormContext<SchemaType>();
```

mergeなどでschemaを作っている場合は問題ないのですが、これが必要なぐらい巨大なフォームだと別々の子コンポーネントで同じkeyを使いたくなることがあると思います。その場合このように書くと思います。

```ts
const childSchema = z.object({
  hoge: z.string()
});
const schema = z.object({
  child: childSchema
});
```
この時、methodsBasedChildSchemaを使うとhogeのみでフォームを指定でき、methodsBasedAllSchemaだとchild.hogeで指定しなければならなくなります。

一見前者の方が記述量も減ってよさそうに見えるのですが、useFormContextはuseFormと同じ型でないとバリデーションが正しく実行されないということがわかりました。つまり以下のような形になっていた時

```ts
const methods = useForm<A>({ ... });
const methods = useFormContext<B>();
```

AとBは一致しないとうまく動きません。なので最終的には以下のような形になります。


```ts
const childSchema = z.object({
  hoge: z.string()
});
const child2Schema = z.object({
  fuga: z.number()
});
const schema = z.object({
  child: childSchema,
  child2: child2Schema
});

type SchemaType = z.infer<schema>;

const methods = useForm<SchemaType>({ ... });

const methods = useFormContext<SchemaType>();
```

もちろんナレッジ①を活用すればより複雑なスキーマもスッキリ作ることができると思います。

## ナレッジ③：zodのpathの挙動を理解する

最後はzodでrefineなどを使った時のpathの挙動に関してです。
基本的に普段意識することはなかなかないと思うのですが、複雑なバリデーションを作りたい時には意識できるといいと思うのでご紹介します。

今回考えるのは次のようなフォームです。

![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/10943/a1296ee3-2aab-3b22-d8bf-e3dcd213640f.png)

この有効期限の開始日は必須、終了日は設定なしでもOKで前後判定をバリデーション時点でかけたいというシチュエーションを考えます。
これをrefineを使って表現すると次のようになります。

```ts
const schema = z.object({
  count: z.number(),
  validPeriod: z
    .object({
      startDate: z.string(),
      endDate: z.string().optional(),
     })
    .refine((value) => {
      if (value.endDate) {
        return new Date(value.startDate) < new Date(value.endDate);
      }
      return true;
    }),
});
```

さて、これをreact-hook-formに渡した時、どのようなタイミングでバリデーションの判定が発火するでしょうか？
ここで登場する概念がpathというものです。

react-hook-formはバリデーションをかけるタイミングによってバリデーションをかける範囲を変えています。
まず一番機会が多いのはsubmitする時、この時はもちろん全てのバリデーションが発火されます。

一方inputのonChangeイベントなどでバリデーションがかかる時、この時は基本的に該当のフォームでしかバリデーションを発火させたくないので特定のフォームに関するバリデーションだけが実行されるようになっています。内部的にこの「どれを実行するべきか」の基準になっているのがpathです。

上記の場合pathは次のようになっています。

バリデーション|path
:--:|:--:
上限回数が数字であること|["count"]
開始日が入力されていること|["validPeriod", "startDate"]
終了日が文字列であること|["validPeriod", "endDate"]
開始日と終了日の前後判定|["validPeriod"]

ここで着目して欲しいのが最後の「開始日と終了日の前後判定」です。
react-hook-formは基本的にpathが完全一致する時だけバリデーションを実行するようになっています。
つまり開始日inputの変更で実行されるバリデーションはpathが["validPeriod", "startDate"]の時、終了日inputでも同様に["validPeriod", "endDate"]のみとなるためrefineのバリデーションはsubmitでしか実行されないのです。

ちょっと厄介ですよね。そこでrefineには次のようなオプションが提供されています。

```ts
  const schema = z.object({
    number: z.number(),
    date: z
      .object({
        startDate: z.string(),
        endDate: z.string().optional(),
      })
      .refine(
        (value) => {
          if (value.endDate) {
            return new Date(value.startDate) < new Date(value.endDate);
          }
          return true;
        },
        {
          path: ['endDate'],
        },
      ),
  });
```

こうするとrefineの前後判定のpathは["validPeriod", "endDate"]となり、終了日のフォームの変化でバリデーションを発火するようになります。
引数で指定しているのが['validPeriod', 'endDate']ではなく['endDate']であることに注意してください。

使い方としてはこれでいいのですが、これでもやはり理想の挙動とはいえません。エラーが出た後開始日を修正して直してもバリデーションが発火しないのでエラーが残ったままになってしまうんですよね。

つまりまとめるとこのようなpathの挙動を理解した上で、今回のお題のフォームを作るときは自分でpathをいじらず、意図的に発火させたいタイミングで「validPeriodのバリデーションを発火する」という関数を呼んであげるのが正攻法となってきます。

## まとめ

以上三つのナレッジはいかがだったでしょうか？
かなりニッチなテクニックが多かったとは思いますが、使いこなすことでDevXもUXも両方向上するということも可能だと思っています。
また実際に使ってみないとわかりにくいところもあると思うので、ぜひ実装して試してみてください。
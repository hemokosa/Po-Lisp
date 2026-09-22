# Po-Lisp

**Poetic / Poetry / Poem / Poiesis Lisp** ── 詩のための Lisp。

McCarthy の Pure Lisp を、ひとつの機能に1文字の記号で書きます。構文はすべて11個の記号が
引き受けるので、英数字とかなと漢字は、まるごと詩のために空いています。
依存なしの Python 3 スクリプトです。

```bash
python3 polisp.py
python3 polisp.py examples/polisp/hajimari.lisp
```

```lisp
> (+'雪'(が 降る))
(雪 が 降る)
> ((\(x)(+x(+x())))'木)
(木 木)
> (!'(<'(雪 が 降る)))
雪
```

| ファイル | 中身 |
|---|---|
| [`polisp.py`](polisp.py) | **Po-Lisp の本体**。11文字 |
| [`polisp_min.py`](polisp_min.py) | Po-Lisp の核。7つの公理の7文字だけ |

## 11の記号

| 記号 | | 記号 | | 記号 | |
|---|---|---|---|---|---|
| `@` | atom | `?` | cond | `!` | eval |
| `=` | eq | `'` | quote | `$` | apply |
| `<` | car | `\` | lambda | | |
| `>` | cdr | `*` | label | | |
| `+` | cons | | | | |

- **7つの公理** ── 核（`polisp_min.py`）はこれだけでできている
  - **5つの基本関数** `@ = < > +` ── 引数を評価してから働く。値なので、渡すことも `:def` で覆うこともできる
  - **2つの特殊形式** `? '` ── 引数を評価しない。条件の節と、評価しないデータ
- **さらにふたつの特殊形式** `\` `*` ── 名前のない関数と、再帰のための自己命名
- **ふたつの橋** `!` `$` ── 公理ではない関数。データを式として評価する／関数を適用する

| 式 | 返すもの |
|---|---|
| `(@ x)` | `x` がアトム（記号・`()`・関数）なら `t`、リストなら `()` |
| `(= x y)` | ふたつのアトムが同じなら `t`、ちがえば `()` |
| `(< xs)` | リストの先頭 |
| `(> xs)` | 先頭を除いた残り |
| `(+ x xs)` | `x` を先頭に足した新しいリスト |
| `(? (p e) ...)` | `p` を順に試し、最初に真になった節の `e` を返す |
| `'x` | `x` を評価せず、そのまま返す |
| `(\ (x y) 本体)` | 名前のない関数。値なので、渡すことも返すこともできる |
| `(* 名 式)` | 式の中から、自分自身を名前で呼べるようにする |
| `(! e a)` | データ `e` を式として評価する。`a` は `((名前 値) ...)` の連想リスト（省略可） |
| `($ f xs)` | 関数 `f` を、評価済みの引数リスト `xs` に適用する |

記号の由来: `\` は λ の ASCII での定番の代役、`*` は Kleene 閉包の星（自己命名＝繰り返し）、
`!` は「これを、いま、やる」、`$` は Haskell の関数適用。

## 決めごと

- **11の記号と `(` `)` は、それぞれ1文字でひとつのトークン。** だから空白は要らない。
  `(+'雪(+'が(+'降る())))` と書ける。記号の名前に、この11文字は使えない。
- **`'` はいつでも前置。** うしろに何も取れないとき（`''` や `)` の直前）だけ、記号 `'`
  そのものとして読む。だから `''` は「記号 `'`」を指し、評価器を書くときの
  `(=(<e)'')`（先頭が quote か？）が素直に書ける。書き出すときも `'雪` と縮める。
- **真偽**は `()` が偽、それ以外はすべて真。`t` は自分自身に評価される。`nil` はない
  （空リストは `()` と書く）。
- **関数は値。** `<` 単体も `#<公理 <>` という値で、引数として渡せる。
  `\` はレキシカルスコープで、末尾呼び出しは積み上がらない。
- **純粋さを保つ。** `(<'())`、`(='(a)'(a))`、`(+'a'b)`、どの条件も真にならない `?`、
  束縛のない記号は、黙って `()` を返さずエラーになる。
- **`=` はアトムしか比べない。** 空リストの判定は `@` で守る
  （`(\(x)(?((@x)(=x()))(t())))`）。
- **`:def 名 式`** で名前を覚えさせる。言語ではなくセッションの機能なので、語のまま。
  特殊形式（`' ? \ *`）は覆えないが、値である `@ = < > + ! $` は覆える ──
  だから自分で書いた評価器で `!` を上書きできる。
- `;` から行末はコメント。

## 例

- [`examples/polisp/hajimari.lisp`](examples/polisp/hajimari.lisp) ── **詩「はじまり」**。
  `()` から読み手（eval）まで、十二の段で積み上げる。走らせると、出力そのものがもう一篇になる
- [`examples/polisp/quine.lisp`](examples/polisp/quine.lisp) ── **クワイン**。自分を書き出す式と、
  `(雪 が 降る)` を抱えたまま自分を書き出す式
- [`examples/polisp/eval.lisp`](examples/polisp/eval.lisp) ── eval を Po-Lisp で書く。
  最後に、詩をデータとして書き換えてから走らせる
- [`examples/polisp/kotoba.lisp`](examples/polisp/kotoba.lisp) ── 7文字だけの小片（`polisp_min.py` でも動く）

## 対話モード

- 括弧が閉じるまで複数行にわたって入力できる（継続行は `..`）。
- `:help` 説明　`:def 名 式` 名前を覚えさせる　`:env` 覚えた名前　`:load ファイル名` 読み込み　`:quit` 終了
- 行編集と履歴が使える（履歴は `~/.polisp_history`）。
- シェルからパイプで渡すときは、`\` と `!` がシェルに解釈されないよう、
  シングルクォートかヒアドキュメント（`<<'EOF'`）を使う。

---

## 語の版 ── 段階的な実装

Po-Lisp と同じ言語を、語で書いたものです。7つの公理から始めて、一段ずつ足していきます。
どの段も単体で動き、前の段はそのまま残してあります。

| 段 | ファイル | 中身 | 記号版 |
|---|---|---|---|
| 一 | [`polisp_word.py`](polisp_word.py) | 7つの公理だけ。名前も再帰もない | `polisp_min.py` と同じ言語 |
| 二 | [`polisp_word_lambda.py`](polisp_word_lambda.py) | + `lambda` / `label` | |
| 三 | [`polisp_word_eval.py`](polisp_word_eval.py) | + `eval` / `apply` の橋 | `polisp.py` と同じ言語 |

```bash
python3 polisp_word.py
python3 polisp_word_lambda.py examples/polisp_word/uta.lisp
python3 polisp_word_eval.py examples/polisp_word/eval.lisp
```

| 語 | 記号 | 語 | 記号 |
|---|---|---|---|
| `atom` | `@` | `cond` | `?` |
| `eq` | `=` | `quote` | `'` |
| `car` | `<` | `lambda` | `\` |
| `cdr` | `>` | `label` | `*` |
| `cons` | `+` | `eval` / `apply` | `!` / `$` |

語の版との違いは表記だけではありません。

- 語の版では `(quote x)` と `'x` のどちらも書ける。書き出しは `(quote x)`。
- 語の版の第二段・第三段には `nil`（`()` の別名）がある。
- 記号の名前に使えない文字が、語の版では `( ) ' ;` だけ。

### 第一段 ── 7つの公理

```lisp
(car '(雪 が 降る))                 ; 雪
(cons '雪 '(が 降る))               ; (雪 が 降る)
(cond ((atom '(a)) '複) (t '単))    ; 単
```

### 第二段 ── lambda と label

```lisp
((lambda (x) (cons x (cons x nil))) '木)        ; (木 木)
((label ap (lambda (xs ys)
   (cond ((atom xs) ys)
         (t (cons (car xs) (ap (cdr xs) ys))))))
 '(雪 が) '(降る))                              ; (雪 が 降る)
```

`define` は言語に入れず、セッションの機能 `:def` で名前を覚えさせます。`:def` は大域環境に
書き込み、クロージャは呼ばれた時点で名前を引くので、トップレベルなら `label` なしでも
再帰・相互再帰が書けます。`label` が要るのは、名前を外に置かずに式の中で再帰するときです。

### 第三段 ── eval と apply

**eval は第二段のままでも書けます。** 公理7つと `lambda` / `label` で足りていて、実際に書いた
ものが [`examples/polisp_word/eval.lisp`](examples/polisp_word/eval.lisp) です（第二段でも走ります）。
第三段で足したのは言語の中身ではなく、**書いた評価器と言語じたいの評価器を、
同じ土俵で呼び比べるための橋**です。

```lisp
(eval '(car x) '((x (雪 が 降る))))   ; 雪
(apply car '((雪 が 降る)))           ; 雪
```

表示は `#<公理 car>` に対して `#<橋 eval>`。連想リストの対は、ドット対がないので
`(名前 値)` という2要素のリストです。自作の eval と引数の形が同じなので、そのまま
入れ替えて呼べます。

### 例

- [`examples/polisp_word/kotoba.lisp`](examples/polisp_word/kotoba.lisp) ── 7公理だけの小片。
  `examples/polisp/kotoba.lisp` と出力が1行も違わず一致する
- [`examples/polisp_word/uta.lisp`](examples/polisp_word/uta.lisp) ── `null` `append` `reverse`
  `member` `mapcar` `挟む` `置く` を lambda と label で組み上げる
- [`examples/polisp_word/eval.lisp`](examples/polisp_word/eval.lisp) ── eval を語の版じたいで書く。
  `examples/polisp/eval.lisp` と同じ結果になる

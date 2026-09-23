#!/usr/bin/env python3
"""Po-Lisp 語の版 — 7つの基本公理だけでできた対話環境.

Po-Lisp 語の版の段階的な実装の第一段。記号で書く Po-Lisp の核（polisp_min.py）と
同じ言語を、語で書いたもの。

    5つの基本関数  atom  eq  car  cdr  cons     引数を評価してから働く
    2つの特殊形式  quote  cond                  引数を評価しない

データは2種類しかない。
  アトム : shiro, 雪, t のような記号。それと空リスト ()
  リスト : (a b c) のような、括弧でくくられた列

使い方:
    python3 polisp_word.py            対話モード
    python3 polisp_word.py poem.lisp  ファイルを読んで評価
    echo "(car '(雪 が 降る))" | python3 polisp_word.py
"""

import sys

# ---------------------------------------------------------------- データ表現
#   アトム   -> Python の str（空リストを除く）
#   リスト   -> Python の tuple。空リスト NIL は ()
NIL = ()
T = "t"


def is_symbol(x):
    return isinstance(x, str)


def is_list(x):
    return isinstance(x, tuple)


def truthy(x):
    """() だけが偽。それ以外はすべて真。"""
    return x != NIL


class LispError(Exception):
    pass


class Incomplete(LispError):
    """括弧が閉じていない。対話モードでは次の行を待つ合図になる。"""


# -------------------------------------------------------------------- 読み込み
DELIMS = "()';"


def tokenize(src):
    tokens, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == ";":
            while i < n and src[i] != "\n":
                i += 1
        elif c.isspace():
            i += 1
        elif c in "()'":
            tokens.append(c)
            i += 1
        else:
            j = i
            while j < n and not src[j].isspace() and src[j] not in DELIMS:
                j += 1
            tokens.append(src[i:j])
            i = j
    return tokens


def parse(tokens, pos=0):
    """tokens[pos] から式をひとつ読む -> (式, 次の位置)"""
    if pos >= len(tokens):
        raise Incomplete("式が途中で終わっています")
    tok = tokens[pos]
    if tok == "(":
        items, pos = [], pos + 1
        while True:
            if pos >= len(tokens):
                raise Incomplete("閉じ括弧がありません")
            if tokens[pos] == ")":
                return tuple(items), pos + 1
            item, pos = parse(tokens, pos)
            items.append(item)
    if tok == ")":
        raise LispError("対応する開き括弧のない ) があります")
    if tok == "'":
        quoted, pos = parse(tokens, pos + 1)
        return ("quote", quoted), pos
    return tok, pos + 1


def read_one(src):
    tokens = tokenize(src)
    if not tokens:
        return None
    expr, pos = parse(tokens)
    if pos != len(tokens):
        raise LispError("1行に式がふたつ以上あります")
    return expr


def read_all(src):
    tokens, pos, forms = tokenize(src), 0, []
    while pos < len(tokens):
        expr, pos = parse(tokens, pos)
        forms.append(expr)
    return forms


# -------------------------------------------------------------------- 書き出し
def write(x):
    if is_symbol(x):
        return x
    return "(" + " ".join(write(e) for e in x) + ")"


# 第一段にない語を見かけたら、あとの段の場所を教える
LATER = {
    "lambda": "polisp_word_lambda.py", "label": "polisp_word_lambda.py",
    "eval": "polisp_word_eval.py", "apply": "polisp_word_eval.py",
}


def hint(name):
    """lambda / label / eval / apply や :def は、あとの段の機能。"""
    if name in LATER:
        return "。%s は第二段以降（%s）にあります" % (name, LATER[name])
    if name.startswith(":"):
        return "。第二段以降にあります"
    return ""


# ---------------------------------------------------------------------- 評価器
def seval(x):
    if is_symbol(x):
        if x.startswith(":"):
            raise LispError("%s は、ここにはありません%s" % (x, hint(x)))
        if x == T:                       # t と () だけは自分自身に評価される
            return T
        raise LispError(
            "%s には値がありません。データとして使うなら '%s と書きます%s" % (x, x, hint(x))
        )
    if x == NIL:
        return NIL

    op = x[0]
    args = x[1:]

    if not is_symbol(op):
        raise LispError(
            "%s は関数ではありません。先頭に置けるのは7つの公理だけです" % write(op)
        )

    # --- quote と cond は引数を評価しない（特殊形式）
    if op == "quote":
        need(op, args, 1)
        return args[0]

    if op == "cond":
        for clause in args:
            if not is_list(clause) or len(clause) != 2:
                raise LispError(
                    "cond の節は (条件 結果) の形にします: %s" % write(clause)
                )
            if truthy(seval(clause[0])):
                return seval(clause[1])
        raise LispError("cond: 真になる条件がひとつもありませんでした")

    # --- 残る5つは引数を評価してから適用する
    if op in ("atom", "eq", "car", "cdr", "cons"):
        vals = [seval(a) for a in args]

        if op == "atom":
            need(op, args, 1)
            return T if (is_symbol(vals[0]) or vals[0] == NIL) else NIL

        if op == "eq":
            need(op, args, 2)
            a, b = vals
            for v in (a, b):
                if not (is_symbol(v) or v == NIL):
                    raise LispError("eq が比べられるのはアトムだけです: %s" % write(v))
            return T if a == b else NIL

        if op == "car":
            need(op, args, 1)
            if not is_list(vals[0]) or vals[0] == NIL:
                raise LispError("car: 空でないリストが必要です: %s" % write(vals[0]))
            return vals[0][0]

        if op == "cdr":
            need(op, args, 1)
            if not is_list(vals[0]) or vals[0] == NIL:
                raise LispError("cdr: 空でないリストが必要です: %s" % write(vals[0]))
            return vals[0][1:]

        if op == "cons":
            need(op, args, 2)
            if not is_list(vals[1]):
                raise LispError(
                    "cons の第2引数はリストでなければなりません: %s" % write(vals[1])
                )
            return (vals[0],) + vals[1]

    raise LispError(
        "%s という公理はありません。使えるのは atom eq car cdr cons quote cond の7つです%s"
        % (op, hint(op))
    )


def need(op, args, n):
    if len(args) != n:
        raise LispError("%s は引数を%d個とります（%d個ありました）" % (op, n, len(args)))


# ------------------------------------------------------------------------ REPL
HELP = """\
7つの公理 = 5つの基本関数 + 2つの特殊形式

5つの基本関数（引数を評価してから働く）:
  (atom x)          x がアトム（記号か ()）なら t、そうでなければ ()
  (eq x y)          ふたつのアトムが同じなら t、ちがえば ()
  (car xs)          リストの先頭
  (cdr xs)          リストの先頭を除いた残り
  (cons x xs)       x を先頭に足した新しいリスト

2つの特殊形式（引数を評価しない）:
  (quote x)  'x     x を評価せずそのまま返す
  (cond (p e) ...)  p を順に試し、最初に真になった節の e を返す

真偽:  () が偽。それ以外はすべて真。t は自分自身に評価される。

例:
  (car '(雪 が 降る))                -> 雪
  (cdr '(雪 が 降る))                -> (が 降る)
  (cons '雪 '(が 降る))              -> (雪 が 降る)
  (atom '())                         -> t
  (eq (car '(夜 明け)) '夜)          -> t
  (cond ((atom '(a)) '複) (t '単))   -> 単

コマンド:  :help  :quit  :load ファイル名
複数行にまたがる式は、括弧が閉じるまで入力を続けられます（.. が出ます）。
"""


def run_source(src, show=False):
    for form in read_all(src):
        try:
            val = seval(form)
        except LispError as e:
            print("error: %s" % e, file=sys.stderr)
            continue
        if show:
            print(write(val))


def repl():
    try:
        import readline  # noqa: F401  行編集と履歴
        import os
        histfile = os.path.expanduser("~/.polisp_word_history")
        try:
            readline.read_history_file(histfile)
        except OSError:
            pass
        import atexit
        atexit.register(lambda: _save_history(readline, histfile))
    except ImportError:
        pass

    print("Po-Lisp 語の版 — atom eq car cdr cons quote cond の7つだけ。:help で説明、:quit で終了。")
    buf = ""
    while True:
        try:
            line = input(".. " if buf else "> ")
        except EOFError:
            print()
            return
        except KeyboardInterrupt:
            print("^C")
            buf = ""
            continue

        if not buf:
            cmd = line.strip()
            if cmd in (":quit", ":q"):
                return
            if cmd in (":help", ":h", "?"):
                print(HELP, end="")
                continue
            if cmd.startswith(":load "):
                path = cmd[len(":load "):].strip()
                try:
                    with open(path, encoding="utf-8") as f:
                        run_source(f.read(), show=True)
                except OSError as e:
                    print("error: %s" % e, file=sys.stderr)
                except LispError as e:
                    print("error: %s" % e, file=sys.stderr)
                continue

        buf = buf + "\n" + line if buf else line
        if not buf.strip():
            buf = ""
            continue

        try:
            expr = read_one(buf)
        except Incomplete:
            continue          # 括弧が閉じるまで待つ
        except LispError as e:
            print("error: %s" % e, file=sys.stderr)
            buf = ""
            continue
        buf = ""

        if expr is None:
            continue
        try:
            print(write(seval(expr)))
        except LispError as e:
            print("error: %s" % e, file=sys.stderr)
        except RecursionError:
            print("error: 式が深すぎます", file=sys.stderr)


def _save_history(readline, histfile):
    try:
        readline.write_history_file(histfile)
    except OSError:
        pass


def main(argv):
    if len(argv) > 1:
        with open(argv[1], encoding="utf-8") as f:
            run_source(f.read(), show=True)
    elif sys.stdin.isatty():
        repl()
    else:
        run_source(sys.stdin.read(), show=True)


if __name__ == "__main__":
    main(sys.argv)

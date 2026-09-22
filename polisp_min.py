#!/usr/bin/env python3
"""Po-Lisp の核 — 7つの公理に、それぞれ1文字。

5つの基本関数（引数を評価してから働く）と、2つの特殊形式（引数を評価しない）。

    @  atom    アトムか
    =  eq      アトムが等しいか
    <  car     先頭
    >  cdr     残り
    +  cons    つなぐ

    ?  cond    えらぶ
    '  quote   そのまま

この7文字と ( ) は、それぞれが1文字でひとつのトークン。だから空白は要らない。

    (<'(雪 が 降る))          -> 雪
    (+'雪'(が 降る))          -> (雪 が 降る)
    (?((@'())'空)(t'なにか))  -> 空

英数字やかなは記号（データ）のためだけに空いている。

lambda / label / eval / apply まで入った Po-Lisp の本体は polisp.py にある。
同じ7公理を語で書いたもの（語の版の段階的な実装の第一段）は polisp_word.py。

使い方:
    python3 polisp_min.py                              対話モード
    python3 polisp_min.py examples/polisp/kotoba.lisp  ファイルを読んで評価
"""

import sys

# ---------------------------------------------------------------- データ表現
#   アトム   -> str（記号）
#   リスト   -> tuple。空リスト NIL は ()
NIL = ()
T = "t"

ATOM, EQ, CAR, CDR, CONS, COND, QUOTE = "@", "=", "<", ">", "+", "?", "'"
OPS = ATOM + EQ + CAR + CDR + CONS + COND + QUOTE


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
DELIMS = "()" + OPS + ";"


def tokenize(src):
    tokens, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == ";":
            while i < n and src[i] != "\n":
                i += 1
        elif c.isspace():
            i += 1
        elif c in "()" or c in OPS:       # 7つの記号と括弧は、1文字で1トークン
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
    """tokens[pos] から式をひとつ読む -> (式, 次の位置)

    ' はいつでも前置。'x が quote。うしろに何も取れないとき（'' や、) の直前）
    だけは、記号 ' そのものとして読む。だから '' は「記号 ' 」を指す。
    ( の直後の ' も略記なので、('a b) は ((' a) b) というデータになる。
    """
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
    if tok == QUOTE:
        if pos + 1 >= len(tokens) or tokens[pos + 1] == ")":
            return QUOTE, pos + 1          # 続きが取れないときは記号そのもの
        if tokens[pos + 1] == QUOTE:
            return (QUOTE, QUOTE), pos + 2  # '' は「記号 ' 」を指す
        quoted, pos = parse(tokens, pos + 1)
        return (QUOTE, quoted), pos
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
    if len(x) == 2 and x[0] == QUOTE:     # quote は 'x と縮めて書く
        return QUOTE + write(x[1])
    return "(" + " ".join(write(e) for e in x) + ")"


# ---------------------------------------------------------------------- 評価器
def seval(x):
    if is_symbol(x):
        if x == T:                        # t と () だけは自分自身に評価される
            return T
        raise LispError(
            "%s には値がありません。データとして使うなら '%s と書きます" % (x, x)
        )
    if x == NIL:
        return NIL

    op = x[0]
    args = x[1:]

    if not is_symbol(op):
        raise LispError(
            "%s は関数ではありません。先頭に置けるのは7つの記号だけです" % write(op)
        )

    # --- ' と ? は引数を評価しない（特殊形式）
    if op == QUOTE:
        need(op, args, 1)
        return args[0]

    if op == COND:
        for clause in args:
            if not is_list(clause) or len(clause) != 2:
                raise LispError(
                    "? の節は (条件 結果) の形にします: %s" % write(clause)
                )
            if truthy(seval(clause[0])):
                return seval(clause[1])
        raise LispError("?: 真になる条件がひとつもありませんでした")

    # --- 残る5つは引数を評価してから適用する
    if op in (ATOM, EQ, CAR, CDR, CONS):
        vals = [seval(a) for a in args]

        if op == ATOM:
            need(op, args, 1)
            return T if (is_symbol(vals[0]) or vals[0] == NIL) else NIL

        if op == EQ:
            need(op, args, 2)
            a, b = vals
            for v in (a, b):
                if not (is_symbol(v) or v == NIL):
                    raise LispError(
                        "= が比べられるのはアトムだけです: %s"
                        "（リストが空かどうかを見るなら (@ x) を使います）" % write(v)
                    )
            return T if a == b else NIL

        if op == CAR:
            need(op, args, 1)
            if not is_list(vals[0]) or vals[0] == NIL:
                raise LispError("<: 空でないリストが必要です: %s" % write(vals[0]))
            return vals[0][0]

        if op == CDR:
            need(op, args, 1)
            if not is_list(vals[0]) or vals[0] == NIL:
                raise LispError(">: 空でないリストが必要です: %s" % write(vals[0]))
            return vals[0][1:]

        if op == CONS:
            need(op, args, 2)
            if not is_list(vals[1]):
                raise LispError(
                    "+ の第2引数はリストでなければなりません: %s" % write(vals[1])
                )
            return (vals[0],) + vals[1]

    raise LispError(
        "%s という公理はありません。使えるのは @ = < > + ? ' の7つです" % op
    )


def need(op, args, n):
    if len(args) != n:
        raise LispError("%s は引数を%d個とります（%d個ありました）" % (op, n, len(args)))


# ------------------------------------------------------------------------ REPL
HELP = """\
7つの公理 = 5つの基本関数 + 2つの特殊形式

5つの基本関数（引数を評価してから働く）:
  (@ x)             x がアトム（記号か ()）なら t、リストなら ()
  (= x y)           ふたつのアトムが同じなら t、ちがえば ()
  (< xs)            リストの先頭
  (> xs)            リストの先頭を除いた残り
  (+ x xs)          x を先頭に足した新しいリスト

2つの特殊形式（引数を評価しない）:
  (? (p e) ...)     p を順に試し、最初に真になった節の e を返す
  'x                x を評価せずそのまま返す（'' は記号 ' そのもの）

7つの記号と ( ) はそれぞれ1文字で1トークン。空白はあってもなくてもいい。
真偽:  () が偽。それ以外はすべて真。t は自分自身に評価される。

例:
  (<'(雪 が 降る))                 -> 雪
  (>'(雪 が 降る))                 -> (が 降る)
  (+'雪'(が 降る))                 -> (雪 が 降る)
  (+'雪(+'が(+'降る())))           -> (雪 が 降る)
  (@'())                           -> t
  (=(<'(夜 明け))'夜)              -> t
  (?((@'(a))'複)(t'単))            -> 単

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
        import atexit
        import os
        import readline                    # 行編集と履歴

        histfile = os.path.expanduser("~/.polisp_history")
        try:
            readline.read_history_file(histfile)
        except OSError:
            pass
        atexit.register(lambda: _save_history(readline, histfile))
    except ImportError:
        pass

    print("Po-Lisp の核 — @ = < > + ? ' の7文字だけ。:help で説明、:quit で終了。")
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
            if cmd in (":help", ":h"):   # ? は cond なので別名にしない
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
            continue                       # 括弧が閉じるまで待つ
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
